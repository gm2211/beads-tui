"""Main Textual application."""

from __future__ import annotations

import datetime
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Header
from textual import on, work
from rich.text import Text

from .bd_client import BdClient, BdError
from .mixins.live_reload import LiveReloadMixin
from .models import Issue
from .screens.create_screen import CreateScreen
from .screens.help_screen import HelpScreen
from .widgets.filter_bar import FilterBar
from .widgets.status_bar import StatusBar


# ---------------------------------------------------------------------------
# Priority / status display helpers
# ---------------------------------------------------------------------------

_PRIORITY_STYLES: dict[int, tuple[str, str]] = {
    0: ("P0", "bold #ff4444"),
    1: ("P1", "#e08614"),
    2: ("P2", "#c4a000"),
    3: ("P3", "#5b9bd5"),
    4: ("P4", "dim"),
}

_STATUS_DISPLAY: dict[str, tuple[str, str]] = {
    "open": ("OPEN", "bold white on #2d6a2d"),
    "in_progress": ("PROG", "bold white on #1a6a6a"),
    "blocked": ("BLOCK", "bold white on #8b2020"),
    "deferred": ("DEFER", "bold white on #2d2d8b"),
    "closed": ("CLOSE", "white on grey37"),
}

_TYPE_STYLES: dict[str, str] = {
    "bug": "#ff6b6b",
    "feature": "#89b4fa",
    "task": "#a6e3a1",
    "epic": "#cba6f7",
    "chore": "#f9e2af",
}

_TYPE_LABELS: dict[str, str] = {
    "bug": "bug",
    "feature": "feat",
    "task": "task",
    "epic": "epic",
    "chore": "chore",
}


def _styled(value: str, style: str) -> Text:
    return Text(value, style=style)


def _priority_cell(priority: int) -> Text:
    label, style = _PRIORITY_STYLES.get(priority, ("P?", ""))
    return _styled(label, style)


def _status_cell(status: str) -> Text:
    label, style = _STATUS_DISPLAY.get(status, (status, ""))
    return _styled(label, style)


def _type_cell(issue_type: str) -> Text:
    if not issue_type:
        return Text("")
    key = issue_type.lower()
    color = _TYPE_STYLES.get(key, "#6c7086")
    label = _TYPE_LABELS.get(key, issue_type)
    return Text(label, style=f"bold {color}")


def _title_cell(title: str, priority: int) -> Text:
    _, style = _PRIORITY_STYLES.get(priority, ("", ""))
    return _styled(title, style)


def _short_date(dt: str) -> str:
    if not dt:
        return ""
    return dt[:10]


def _short_id(issue_id: str) -> str:
    """Strip the project prefix from an issue ID (e.g. 'proj-abc' -> 'abc')."""
    if "-" in issue_id:
        return issue_id.rsplit("-", 1)[-1]
    return issue_id


def _deps_cell(issue: Issue) -> Text:
    """Show dependency counts with directional indicators."""
    parts = []
    if issue.dependency_count > 0:
        parts.append(Text(f"\u2192{issue.dependency_count}", style="dodger_blue1"))
    if issue.dependent_count > 0:
        if parts:
            parts.append(Text(" "))
        parts.append(Text(f"\u2190{issue.dependent_count}", style="dark_orange"))
    if not parts:
        return Text("")
    return Text.assemble(*parts)


# ---------------------------------------------------------------------------
# Column registry (data-driven)
# ---------------------------------------------------------------------------

@dataclass
class ColumnDef:
    key: str
    label: str
    getter: Callable[[Issue], Text | str]
    width: int | None = None


AVAILABLE_COLUMNS: dict[str, ColumnDef] = {
    "id": ColumnDef(key="id", label="ID", getter=lambda i: _styled(i.id, "bold"), width=11),
    "priority": ColumnDef(key="priority", label="P", getter=lambda i: _priority_cell(i.priority), width=4),
    "status": ColumnDef(key="status", label="Status", getter=lambda i: _status_cell(i.status), width=8),
    "type": ColumnDef(key="type", label="Type", getter=lambda i: _type_cell(i.issue_type), width=7),
    "title": ColumnDef(key="title", label="Title", getter=lambda i: _title_cell(i.title, i.priority), width=None),
    "assignee": ColumnDef(key="assignee", label="Assignee", getter=lambda i: _styled(i.assignee or "", "bold"), width=10),
    "updated": ColumnDef(key="updated", label="Updated", getter=lambda i: _styled(_short_date(i.updated_at), "bold"), width=12),
    "created": ColumnDef(key="created", label="Created", getter=lambda i: _styled(_short_date(i.created_at), "bold"), width=12),
    "labels": ColumnDef(key="labels", label="Labels", getter=lambda i: Text(", ".join(i.labels)), width=15),
    "deps": ColumnDef(key="deps", label="Deps", getter=_deps_cell, width=8),
    "last_comment": ColumnDef(key="last_comment", label="Latest Update", getter=lambda i: Text(""), width=None),
}

DEFAULT_COLUMNS = ["id", "priority", "status", "type", "assignee", "title", "last_comment"]


# ---------------------------------------------------------------------------
# Tree-view helpers
# ---------------------------------------------------------------------------

def _build_tree_order(
    issues: list[Issue],
    graph_data: list[dict],
) -> list[tuple[Issue, str]]:
    """Build tree-ordered issue list with ASCII prefix strings.

    Returns list of (issue, prefix) tuples where prefix contains
    tree-drawing characters (e.g. "├── ", "│   └── ").
    """
    children_map: dict[str, list[str]] = {}
    has_parent: set[str] = set()

    for entry in graph_data:
        deps = entry.get("Dependencies") or []
        for dep in deps:
            parent_id = dep.get("depends_on_id", "")
            child_id = dep.get("issue_id", "")
            if parent_id and child_id:
                children_map.setdefault(parent_id, []).append(child_id)
                has_parent.add(child_id)

    issue_map: dict[str, Issue] = {i.id: i for i in issues}
    visible_ids = set(issue_map.keys())

    roots = [i for i in issues if i.id not in has_parent]
    roots.sort(key=lambda i: i.priority)

    result: list[tuple[Issue, str]] = []
    visited: set[str] = set()

    def dfs(issue_id: str, prefix: str, is_last: bool, depth: int) -> None:
        if issue_id in visited or issue_id not in issue_map:
            return
        visited.add(issue_id)

        issue = issue_map[issue_id]

        if depth == 0:
            tree_prefix = ""
            next_prefix = ""
        else:
            connector = "└── " if is_last else "├── "
            tree_prefix = prefix + connector
            next_prefix = prefix + ("    " if is_last else "│   ")

        result.append((issue, tree_prefix))

        child_ids = [c for c in children_map.get(issue_id, []) if c in visible_ids]
        child_ids.sort(key=lambda cid: issue_map[cid].priority if cid in issue_map else 99)

        for i, child_id in enumerate(child_ids):
            is_last_child = (i == len(child_ids) - 1)
            dfs(child_id, next_prefix, is_last_child, depth + 1)

    for root in roots:
        dfs(root.id, "", True, 0)

    for issue in issues:
        if issue.id not in visited:
            result.append((issue, ""))

    return result


# ---------------------------------------------------------------------------
# Sort helpers
# ---------------------------------------------------------------------------

def _sort_key_for_column(col_key: str, issue: Issue) -> object:
    """Return a sortable value for the given column key."""
    if col_key == "id":
        return issue.id
    if col_key == "priority":
        return issue.priority
    if col_key == "status":
        order = {"open": 0, "in_progress": 1, "blocked": 2, "deferred": 3, "closed": 4}
        return order.get(issue.status, 99)
    if col_key == "type":
        return issue.issue_type or ""
    if col_key == "title":
        return issue.title.lower()
    if col_key == "assignee":
        return (issue.assignee or "").lower()
    if col_key == "updated":
        return issue.updated_at or ""
    if col_key == "created":
        return issue.created_at or ""
    if col_key == "labels":
        return ", ".join(issue.labels)
    if col_key == "deps":
        return issue.dependency_count
    return ""


# ---------------------------------------------------------------------------
# Sort picker & column menu
# ---------------------------------------------------------------------------

from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from textual.widgets import Button, Checkbox, Label, OptionList
from textual.widgets.option_list import Option


class SortPicker(ModalScreen[tuple[str, bool] | None]):
    """Pick sort column and direction."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """\
    SortPicker {
        align: center middle;
    }
    """

    def __init__(
        self,
        columns: dict[str, str],
        current_col: str,
        current_reverse: bool,
    ) -> None:
        super().__init__()
        self._columns = columns
        self._selected_col = current_col
        self._selected_reverse = current_reverse

    def compose(self) -> ComposeResult:
        with Vertical(id="sort-dialog"):
            yield Label("Sort By", id="sort-title")
            option_list = OptionList(id="sort-options")
            for key, label in self._columns.items():
                option_list.add_option(Option(self._option_label(key, label), id=key))
            yield option_list
            with Horizontal(id="sort-buttons"):
                yield Button("Apply", variant="primary", id="sort-apply-btn")
                yield Button("Cancel", id="sort-cancel-btn")

    def _option_label(self, key: str, label: str) -> str:
        if key == self._selected_col:
            arrow = "\u25bc" if self._selected_reverse else "\u25b2"
            return f"{label} {arrow}"
        return label

    def _refresh_options(self) -> None:
        """Re-render option labels to reflect current selection."""
        opt_list = self.query_one("#sort-options", OptionList)
        opt_list.clear_options()
        for key, label in self._columns.items():
            opt_list.add_option(Option(self._option_label(key, label), id=key))

    @on(OptionList.OptionSelected)
    def _on_option_selected(self, event: OptionList.OptionSelected) -> None:
        col_key = str(event.option.id)
        if col_key == self._selected_col:
            self._selected_reverse = not self._selected_reverse
        else:
            self._selected_col = col_key
            self._selected_reverse = False
        self._refresh_options()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sort-apply-btn":
            self.dismiss((self._selected_col, self._selected_reverse))
        elif event.button.id == "sort-cancel-btn":
            self.dismiss(None)

    def on_click(self, event) -> None:
        if self is event.widget:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ColumnMenu(ModalScreen[list[str] | None]):
    """Toggle column visibility."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """\
    ColumnMenu {
        align: center middle;
    }

    ColumnMenu > #col-menu-dialog {
        width: 40;
        max-width: 80%;
        height: auto;
        max-height: 70%;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }

    ColumnMenu > #col-menu-dialog > #col-menu-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        margin-bottom: 1;
    }

    ColumnMenu > #col-menu-dialog #col-menu-buttons {
        width: 100%;
        height: auto;
        align-horizontal: center;
        margin-top: 1;
    }

    ColumnMenu > #col-menu-dialog #col-menu-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self, all_columns: dict[str, str], active: list[str]) -> None:
        super().__init__()
        self._all_columns = all_columns
        self._active = active

    def compose(self) -> ComposeResult:
        with Vertical(id="col-menu-dialog"):
            yield Label("Visible Columns", id="col-menu-title")
            for key in self._active:
                if key in self._all_columns:
                    yield Checkbox(self._all_columns[key], value=True, id=f"colm-{key}")
            for key in self._all_columns:
                if key not in self._active:
                    yield Checkbox(self._all_columns[key], value=False, id=f"colm-{key}")
            with Horizontal(id="col-menu-buttons"):
                yield Button("Apply", variant="primary", id="colm-apply")
                yield Button("Cancel", id="colm-cancel")

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#colm-cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#colm-apply")
    def _on_apply(self) -> None:
        result: list[str] = []
        for key in self._active:
            if key in self._all_columns:
                chk = self.query_one(f"#colm-{key}", Checkbox)
                if chk.value:
                    result.append(key)
        for key in self._all_columns:
            if key not in self._active:
                chk = self.query_one(f"#colm-{key}", Checkbox)
                if chk.value:
                    result.append(key)
        if not result:
            self.notify("At least one column must be selected", severity="error")
            return
        self.dismiss(result)


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

class BeadsTuiApp(LiveReloadMixin, App):
    """Interactive TUI for beads (bd) issue tracker."""

    TITLE = "Beads TUI"
    CSS_PATH = "styles/app.tcss"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        Binding("ctrl+c", "quit_guard", "Quit", show=False, priority=True),
        Binding("q", "quit", "Quit", priority=True),
        Binding("question_mark", "help", "Help", key_display="?"),
        Binding("c", "create", "Create"),
        Binding("slash", "search", "Search", key_display="/"),
        Binding("r", "refresh", "Refresh"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("h", "scroll_left", "Left", show=False),
        Binding("l", "scroll_right", "Right", show=False),
        Binding("enter", "select_issue", "Open", show=False),
        Binding("A", "toggle_all", "Toggle All", key_display="A"),
        Binding("space", "toggle_select", "Select", show=False),
        Binding("V", "select_all_visible", "Select All", show=False),
        Binding("o", "sort_picker", "Sort"),
        Binding("numbersign", "column_menu", "Columns", key_display="#"),
        Binding("p", "quick_priority", "Priority", show=False),
        Binding("s", "quick_status", "Status", show=False),
        Binding("x", "quick_close", "Close", show=False),
        Binding("d", "quick_delete", "Delete", show=False),
        Binding("i", "toggle_id_prefix", "Toggle ID", show=False),
        Binding("t", "toggle_tree", "Tree"),
        Binding("w", "switch_worktree", "Worktrees"),
    ]

    def __init__(
        self,
        bd_path: str | None = None,
        db_path: str | None = None,
        columns: list[str] | None = None,
        show_all: bool = False,
    ):
        super().__init__()
        self._bd_path = bd_path
        self._db_path = db_path
        self.client: BdClient | None = None
        self._issues: list[Issue] = []
        self._filtered_issues: list[Issue] = []
        self._show_all = show_all
        self._active_columns: list[str] = list(columns or DEFAULT_COLUMNS)
        self._sort_column: str = "priority"
        self._sort_reverse: bool = False
        self._quit_pending: bool = False
        self._strip_id_prefix: bool = False
        self._tree_mode: bool = False
        self._tree_prefixes: dict[str, str] = {}
        self._graph_data: list[dict] = []
        self._last_comments: dict[str, str] = {}  # issue_id -> latest comment preview
        self._selected_ids: set[str] = set()
        self._current_filters: dict = {
            "search": None,
            "statuses": {"open", "in_progress"} if not show_all else None,
            "priorities": None,
            "types": None,
        }
        self._worktree_name: str = ""
        self._worktree_path: str = ""

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        all_statuses = {"open", "in_progress", "blocked", "deferred", "closed"}
        yield FilterBar(initial_statuses=all_statuses if self._show_all else None)
        yield DataTable(id="issue-table", cursor_type="row", zebra_stripes=True, cell_padding=1)
        yield StatusBar()

    def on_mount(self) -> None:
        try:
            self.client = BdClient(bd_path=self._bd_path, db_path=self._db_path)
        except BdError:
            self.client = None
        # Detect current worktree
        self._worktree_name, self._worktree_path = self._detect_worktree_info()
        # Discover .beads/ directory for file-watch live reload.
        self.WATCH_PATH = self._discover_watch_path()
        self._rebuild_columns()
        self._load_issues()
        self.start_live_reload()
        self.query_one("#issue-table", DataTable).focus()
        # Set worktree name on status bar after mount
        if self._worktree_name:
            self.query_one(StatusBar).worktree_name = self._worktree_name

    @staticmethod
    def _discover_watch_path() -> Path | None:
        """Walk up from cwd looking for a .beads/ directory."""
        cur = Path.cwd()
        for parent in [cur, *cur.parents]:
            candidate = parent / ".beads"
            if candidate.is_dir():
                return candidate
        return None

    @staticmethod
    def _detect_worktree_info() -> tuple[str, str]:
        """Return (worktree_name, worktree_path) for the current directory.

        The worktree_name is the basename of the toplevel git directory,
        and worktree_path is its absolute path.
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return "", ""
            current_toplevel = result.stdout.strip()
            name = Path(current_toplevel).name
            return name, current_toplevel
        except Exception:
            return "", ""

    @staticmethod
    def _list_all_worktrees() -> list[dict]:
        """Return list of {name, path, branch, is_current} for all worktrees."""
        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return []
        except Exception:
            return []

        worktrees = []
        current_toplevel = ""
        try:
            tl = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, timeout=5
            )
            current_toplevel = tl.stdout.strip()
        except Exception:
            pass

        current_wt: dict = {}
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("worktree "):
                if current_wt:
                    worktrees.append(current_wt)
                path = line[len("worktree "):]
                current_wt = {
                    "name": Path(path).name,
                    "path": path,
                    "branch": "",
                    "is_current": path == current_toplevel,
                }
            elif line.startswith("branch "):
                branch = line[len("branch "):]
                # strip refs/heads/ prefix
                if branch.startswith("refs/heads/"):
                    branch = branch[len("refs/heads/"):]
                current_wt["branch"] = branch
        if current_wt:
            worktrees.append(current_wt)
        return worktrees

    def _on_change_detected(self) -> None:
        """File watcher detected a write — do a full reload."""
        self._load_issues()

    # ------------------------------------------------------------------
    # Column management
    # ------------------------------------------------------------------

    def _col_width(self, col_key: str, computed_widths: dict[str, int] | None = None) -> int | None:
        """Return the effective fixed width for a column, or None for flex.

        If *computed_widths* is provided (from content measurement in
        _rebuild_columns), use the pre-computed value for non-flex columns
        instead of the static ColumnDef.width.
        """
        col_def = AVAILABLE_COLUMNS.get(col_key)
        if not col_def:
            return None
        # Flex columns (title, last_comment) always return None so they absorb
        # remaining space.
        if col_def.width is None:
            return None
        if computed_widths and col_key in computed_widths:
            return computed_widths[col_key]
        if col_key == "id" and self._strip_id_prefix:
            return 6
        return col_def.width

    def _rebuild_columns(self) -> None:
        """Rebuild DataTable columns from active column list + sort indicators."""
        table = self.query_one("#issue-table", DataTable)
        table.clear(columns=True)

        total_width = table.size.width or self.size.width or 120

        # ------------------------------------------------------------------
        # Step 1: Measure actual content widths for each non-flex column.
        # Flex columns (width=None in ColumnDef) are excluded — they absorb
        # leftover space.
        # ------------------------------------------------------------------
        PADDING = 1  # extra chars added to each measured column

        # Determine the first active non-flex column (needs +2 for "✓ " marker)
        first_col_key: str | None = None
        for col_key in self._active_columns:
            col_def = AVAILABLE_COLUMNS.get(col_key)
            if col_def and col_def.width is not None:
                first_col_key = col_key
                break
        # If all columns are flex, the first column still gets the marker
        if first_col_key is None and self._active_columns:
            first_col_key = self._active_columns[0]

        content_widths: dict[str, int] = {}
        for col_key in self._active_columns:
            col_def = AVAILABLE_COLUMNS.get(col_key)
            if not col_def or col_def.width is None:
                continue  # skip flex columns

            # Start from the header label length
            label_len = len(col_def.label)
            # Account for the sort arrow appended to the header
            if col_key == self._sort_column:
                label_len += 2  # " ▲" or " ▼"
            max_content = label_len

            for issue in self._filtered_issues:
                if col_key == "id" and self._strip_id_prefix:
                    cell_len = len(_short_id(issue.id))
                else:
                    cell = col_def.getter(issue)
                    cell_len = len(cell.plain) if isinstance(cell, Text) else len(str(cell))
                max_content = max(max_content, cell_len)

            # Add the selection marker width (2 chars "✓ ") to the first column
            extra = 2 if col_key == first_col_key else 0
            content_widths[col_key] = max_content + PADDING + extra

        # ------------------------------------------------------------------
        # Step 2: Tally fixed column widths; collect flex keys
        # ------------------------------------------------------------------
        # Each non-first column has a 2-char separator prefix (│ )
        num_seps = max(len(self._active_columns) - 1, 0)
        usable = total_width - (num_seps * 2)

        fixed_used = 0
        flex_keys: list[str] = []
        for col_key in self._active_columns:
            w = self._col_width(col_key, content_widths)
            if w:
                fixed_used += w
            else:
                flex_keys.append(col_key)

        remaining = usable - fixed_used

        # ------------------------------------------------------------------
        # Step 3: Distribute remaining space to flex columns (title /
        # last_comment).  Title is sized to the longest visible title;
        # last_comment absorbs the rest.
        # ------------------------------------------------------------------
        max_title = max((len(i.title) for i in self._filtered_issues), default=20)
        # Account for tree-mode prefix in title width measurement
        if self._tree_mode and self._tree_prefixes:
            max_title = max(
                (len(self._tree_prefixes.get(i.id, "")) + len(i.title) for i in self._filtered_issues),
                default=max_title,
            )
        flex_widths: dict[str, int] = {}
        if "title" in flex_keys and "last_comment" in flex_keys:
            title_w = max(max_title, 10)
            comment_w = remaining - title_w
            if comment_w < 10:
                # Not enough room — shrink title to make space for comment
                title_w = max(remaining - 10, 10)
                comment_w = max(remaining - title_w, 5)
            flex_widths["title"] = title_w
            flex_widths["last_comment"] = comment_w
        elif flex_keys:
            even = max(remaining // len(flex_keys), 10)
            for k in flex_keys:
                flex_widths[k] = even

        # ------------------------------------------------------------------
        # Step 4: Add columns to the DataTable
        # ------------------------------------------------------------------
        for idx, col_key in enumerate(self._active_columns):
            col_def = AVAILABLE_COLUMNS.get(col_key)
            if not col_def:
                continue
            label = col_def.label
            if col_key == self._sort_column:
                arrow = "\u25b2" if not self._sort_reverse else "\u25bc"
                label = f"{label} {arrow}"
            # Content width (without separator)
            content_w = self._col_width(col_key, content_widths) or flex_widths.get(col_key, 20)
            if idx > 0:
                label = f"\u2502 {label}"
                content_w += 2  # separator is part of the column width
            else:
                # Center the first column header within its width
                label = label.center(content_w)
            table.add_column(label, key=col_key, width=content_w)

    def _get_row_cells(self, issue: Issue) -> list[Text | str]:
        """Build row cells based on active columns."""
        sep = Text("\u2502 ", style="#44447a")
        cells: list[Text | str] = []
        for idx, col_key in enumerate(self._active_columns):
            if col_key == "last_comment":
                preview = self._last_comments.get(issue.id, "")
                val = Text(preview, style="bold") if preview else Text("")
            elif col_key == "id" and self._strip_id_prefix:
                val = _styled(_short_id(issue.id), "bold")
            elif col_key == "title" and self._tree_mode:
                prefix = self._tree_prefixes.get(issue.id, "")
                _, style = _PRIORITY_STYLES.get(issue.priority, ("", ""))
                if prefix:
                    val = Text.assemble(Text(prefix, style="#666699"), Text(issue.title, style=style))
                else:
                    val = _styled(issue.title, style)
            else:
                col_def = AVAILABLE_COLUMNS.get(col_key)
                val = col_def.getter(issue) if col_def else Text("")
            if idx > 0:
                val = Text.assemble(sep, val) if isinstance(val, Text) else Text.assemble(sep, str(val))
            cells.append(val)
        # Prepend selection marker to first cell
        marker = Text("\u2713 ", style="bold green") if issue.id in self._selected_ids else Text("  ")
        cells[0] = Text.assemble(marker, cells[0]) if isinstance(cells[0], Text) else Text.assemble(marker, str(cells[0]))
        return cells

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    @work(exclusive=True)
    async def _load_issues(self) -> None:
        if self.client is None:
            return
        try:
            issues = await self.client.list_issues(all_=True)
        except BdError:
            issues = []
        if self._tree_mode:
            try:
                self._graph_data = await self.client.graph_all()
            except BdError:
                self._graph_data = []
        self._issues = issues
        self._selected_ids &= {i.id for i in issues}
        self._apply_filters_and_sort()
        self._rebuild_columns()
        self._populate_table()
        self._update_status_bar()
        if "last_comment" in self._active_columns:
            self._load_latest_comments()

    @work(exclusive=True, group="comments")
    async def _load_latest_comments(self) -> None:
        """Fetch latest comment for each visible issue with comments (background)."""
        if self.client is None:
            return
        table = self.query_one("#issue-table", DataTable)
        for issue in list(self._filtered_issues):
            if issue.comment_count <= 0:
                continue
            # Skip if we already have a cached comment for this issue
            if issue.id in self._last_comments:
                continue
            try:
                comments = await self.client.list_comments(issue.id)
                if comments:
                    last = comments[-1]
                    preview = last.text.replace("\n", " ").strip()
                    self._last_comments[issue.id] = preview
                    # Update the cell in the table (include separator)
                    col_idx = self._active_columns.index("last_comment") if "last_comment" in self._active_columns else -1
                    try:
                        cell_val = Text(preview, style="bold")
                        if col_idx > 0:
                            cell_val = Text.assemble(Text("\u2502 ", style="#44447a"), cell_val)
                        table.update_cell(
                            issue.id, "last_comment",
                            cell_val,
                        )
                    except Exception:
                        pass
            except BdError:
                pass

    # ------------------------------------------------------------------
    # Filtering and sorting
    # ------------------------------------------------------------------

    def _apply_filters_and_sort(self) -> None:
        """Filter self._issues into self._filtered_issues and sort."""
        filtered = list(self._issues)
        f = self._current_filters

        # Status filter (multi-select)
        # statuses=None means "All" (show everything)
        # statuses=set(...) means only those statuses
        statuses: set[str] | None = f.get("statuses")
        if statuses is not None:
            filtered = [i for i in filtered if i.status in statuses]

        # Text search
        search = f.get("search")
        if search:
            q = search.lower()
            filtered = [
                i for i in filtered
                if q in i.title.lower()
                or q in i.id.lower()
                or q in (i.assignee or "").lower()
                or q in (i.issue_type or "").lower()
            ]

        # Priority filter (multi-select)
        priorities = f.get("priorities")
        if priorities is not None:
            filtered = [i for i in filtered if str(i.priority) in priorities]

        # Type filter (multi-select)
        types = f.get("types")
        if types is not None:
            filtered = [i for i in filtered if i.issue_type in types]

        # Sort or tree-order
        if self._tree_mode and self._graph_data:
            tree_ordered = _build_tree_order(filtered, self._graph_data)
            self._filtered_issues = [issue for issue, _ in tree_ordered]
            self._tree_prefixes = {issue.id: prefix for issue, prefix in tree_ordered}
        else:
            filtered.sort(
                key=lambda i: _sort_key_for_column(self._sort_column, i),
                reverse=self._sort_reverse,
            )
            self._filtered_issues = filtered
            self._tree_prefixes = {}

    def _populate_table(self) -> None:
        table = self.query_one("#issue-table", DataTable)
        # Save current selection
        selected_id = None
        if table.row_count > 0:
            try:
                row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
                selected_id = str(row_key.value)
            except Exception:
                pass
        table.clear()
        for issue in self._filtered_issues:
            table.add_row(*self._get_row_cells(issue), key=issue.id)
        # Restore cursor to the same issue
        if selected_id:
            for idx, issue in enumerate(self._filtered_issues):
                if issue.id == selected_id:
                    table.move_cursor(row=idx)
                    break

    def _update_status_bar(self) -> None:
        status_bar = self.query_one(StatusBar)
        status_bar.issue_count = len(self._filtered_issues)
        status_bar.total_count = len(self._issues)
        now = datetime.datetime.now().strftime("%H:%M:%S")
        status_bar.set_refresh_time(now)
        has_filter = any(v is not None for v in self._current_filters.values())
        status_bar.filter_active = has_filter
        statuses = self._current_filters.get("statuses")
        if statuses is None:
            view = "All Issues"
        else:
            view = "Filtered"
        status_bar.view_name = view
        if self._selected_ids:
            status_bar.view_name = f"{len(self._selected_ids)} selected"

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_resize(self) -> None:
        """Recalculate flexible column widths on terminal resize."""
        self._rebuild_columns()
        self._populate_table()

    @on(FilterBar.FiltersChanged)
    def _on_filters_changed(self, event: FilterBar.FiltersChanged) -> None:
        self._selected_ids.clear()
        self._current_filters = {
            "search": event.search or None,
            "statuses": event.statuses,
            "priorities": event.priorities,
            "types": event.types,
        }
        self._apply_filters_and_sort()
        self._populate_table()
        self._update_status_bar()

    @on(DataTable.HeaderSelected)
    def _on_header_selected(self, event: DataTable.HeaderSelected) -> None:
        col_key = str(event.column_key)
        if col_key not in AVAILABLE_COLUMNS:
            return
        if self._sort_column == col_key:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = col_key
            self._sort_reverse = False
        self._rebuild_columns()
        self._apply_filters_and_sort()
        self._populate_table()

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        issue_id = str(event.row_key.value)
        if not issue_id:
            return
        from .screens.detail_screen import DetailScreen
        prefetch = self._find_cached_issue(issue_id)
        self.pause_refresh()
        self.push_screen(DetailScreen(issue_id, prefetch=prefetch), callback=lambda _: self.resume_refresh())

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_quit_guard(self) -> None:
        if self._quit_pending:
            self.exit()
        else:
            self._quit_pending = True
            self.notify("Press Ctrl+C again to quit", timeout=2)
            self.set_timer(2.0, self._reset_quit_guard)

    def _reset_quit_guard(self) -> None:
        self._quit_pending = False

    def action_cursor_down(self) -> None:
        self.query_one("#issue-table", DataTable).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#issue-table", DataTable).action_cursor_up()

    def action_scroll_left(self) -> None:
        self.query_one("#issue-table", DataTable).scroll_left(animate=False)

    def action_scroll_right(self) -> None:
        self.query_one("#issue-table", DataTable).scroll_right(animate=False)

    def action_refresh(self) -> None:
        self._load_issues()

    def action_select_issue(self) -> None:
        table = self.query_one("#issue-table", DataTable)
        if table.row_count == 0:
            return
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        issue_id = str(row_key.value)
        if not issue_id:
            return
        from .screens.detail_screen import DetailScreen
        prefetch = self._find_cached_issue(issue_id)
        self.pause_refresh()
        self.push_screen(DetailScreen(issue_id, prefetch=prefetch), callback=lambda _: self.resume_refresh())

    def action_help(self) -> None:
        self.pause_refresh()
        self.push_screen(HelpScreen(), callback=lambda _: self.resume_refresh())

    def action_create(self) -> None:
        self.pause_refresh()

        def _on_dismiss(result: dict | None) -> None:
            self.resume_refresh()
            if result is not None:
                self._do_create_issue(result)

        self.push_screen(CreateScreen(), callback=_on_dismiss)

    @work(exclusive=True)
    async def _do_create_issue(self, data: dict) -> None:
        if self.client is None:
            self.notify("No bd client available", severity="error")
            return
        try:
            new_id = await self.client.create_issue(
                title=data["title"],
                type_=data.get("type_"),
                priority=data.get("priority"),
                assignee=data.get("assignee"),
                labels=data.get("labels"),
                description=data.get("description"),
            )
            self.notify(f"Created issue {new_id}", severity="information")
            self._load_issues()
        except BdError as e:
            self.notify(f"Failed to create issue: {e}", severity="error")

    def action_search(self) -> None:
        self.query_one(FilterBar).focus_search()

    def action_toggle_all(self) -> None:
        self._show_all = not self._show_all
        filter_bar = self.query_one(FilterBar)
        if self._show_all:
            filter_bar.set_statuses({"open", "in_progress", "blocked", "deferred", "closed"})
            self.notify("Showing all issues")
        else:
            filter_bar.set_statuses({"open", "in_progress"})
            self.notify("Showing open issues")

    def action_sort_picker(self) -> None:
        columns = {k: v.label for k, v in AVAILABLE_COLUMNS.items()}
        self.pause_refresh()

        def _on_dismiss(result: tuple[str, bool] | None) -> None:
            self.resume_refresh()
            if result is not None:
                self._sort_column, self._sort_reverse = result
                self._rebuild_columns()
                self._apply_filters_and_sort()
                self._populate_table()

        self.push_screen(
            SortPicker(columns, self._sort_column, self._sort_reverse),
            callback=_on_dismiss,
        )

    def action_column_menu(self) -> None:
        all_columns = {k: v.label for k, v in AVAILABLE_COLUMNS.items()}
        self.pause_refresh()

        def _on_dismiss(result: list[str] | None) -> None:
            self.resume_refresh()
            if result is not None:
                self._active_columns = result
                self._rebuild_columns()
                self._populate_table()

        self.push_screen(
            ColumnMenu(all_columns, self._active_columns),
            callback=_on_dismiss,
        )

    def _find_cached_issue(self, issue_id: str) -> Issue | None:
        """Look up an issue from the already-loaded list data."""
        for issue in self._issues:
            if issue.id == issue_id:
                return issue
        return None

    # ------------------------------------------------------------------
    # Quick-edit actions (from list view)
    # ------------------------------------------------------------------

    def _get_selected_issue(self) -> Issue | None:
        table = self.query_one("#issue-table", DataTable)
        if table.row_count == 0:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        issue_id = str(row_key.value)
        for issue in self._filtered_issues:
            if issue.id == issue_id:
                return issue
        return None

    def _get_action_issues(self) -> list[Issue]:
        """Return selected issues, or just the cursor issue if none selected."""
        if self._selected_ids:
            return [i for i in self._filtered_issues if i.id in self._selected_ids]
        issue = self._get_selected_issue()
        return [issue] if issue else []

    def action_toggle_select(self) -> None:
        issue = self._get_selected_issue()
        if not issue:
            return
        if issue.id in self._selected_ids:
            self._selected_ids.discard(issue.id)
        else:
            self._selected_ids.add(issue.id)
        self._populate_table()
        self._update_status_bar()
        self.query_one("#issue-table", DataTable).action_cursor_down()

    def action_select_all_visible(self) -> None:
        visible_ids = {i.id for i in self._filtered_issues}
        if visible_ids.issubset(self._selected_ids):
            self._selected_ids -= visible_ids
        else:
            self._selected_ids |= visible_ids
        self._populate_table()
        self._update_status_bar()

    @work
    async def action_quick_priority(self) -> None:
        issues = self._get_action_issues()
        if not issues or not self.client:
            return
        from .widgets.priority_picker import PriorityPicker
        current = issues[0].priority if len(issues) == 1 else 2
        self.pause_refresh()
        try:
            result = await self.push_screen_wait(PriorityPicker(current=current))
        finally:
            self.resume_refresh()
        if result is not None:
            try:
                for issue in issues:
                    await self.client.update_issue(issue.id, priority=result)
                label = f"P{result} set on {len(issues)} issues" if len(issues) > 1 else f"P{result} set on {issues[0].id}"
                self.notify(label)
                self._selected_ids.clear()
                self._load_issues()
            except BdError as e:
                self.notify(f"Error: {e}", severity="error")

    @work
    async def action_quick_status(self) -> None:
        issues = self._get_action_issues()
        if not issues or not self.client:
            return
        from .widgets.status_picker import StatusPicker
        current = issues[0].status if len(issues) == 1 else "open"
        self.pause_refresh()
        try:
            result = await self.push_screen_wait(StatusPicker(current=current))
        finally:
            self.resume_refresh()
        if result is not None:
            try:
                if result == "closed":
                    await self.client.close_issue(*(issue.id for issue in issues))
                else:
                    for issue in issues:
                        await self.client.update_issue(issue.id, status=result)
                label = f"{result} set on {len(issues)} issues" if len(issues) > 1 else f"{result} set on {issues[0].id}"
                self.notify(label)
                self._selected_ids.clear()
                self._load_issues()
            except BdError as e:
                self.notify(f"Error: {e}", severity="error")

    @work
    async def action_quick_close(self) -> None:
        issues = self._get_action_issues()
        if not issues or not self.client:
            return
        if len(issues) > 1:
            from beads_tui.widgets.confirm_modal import ConfirmModal
            self.pause_refresh()
            try:
                confirmed = await self.push_screen_wait(
                    ConfirmModal("Bulk Close", f"Close [b]{len(issues)}[/b] issues?")
                )
            finally:
                self.resume_refresh()
            if not confirmed:
                return
        try:
            await self.client.close_issue(*(i.id for i in issues))
            label = f"Closed {len(issues)} issues" if len(issues) > 1 else f"Closed {issues[0].id}"
            self.notify(label)
            self._selected_ids.clear()
            self._load_issues()
        except BdError as e:
            self.notify(f"Error: {e}", severity="error")

    @work
    async def action_quick_delete(self) -> None:
        issues = self._get_action_issues()
        if not issues or not self.client:
            return
        from beads_tui.widgets.confirm_modal import ConfirmModal
        if len(issues) > 1:
            msg = f"Permanently delete [b]{len(issues)}[/b] issues?\nThis cannot be undone."
        else:
            msg = f"Permanently delete [b]{issues[0].id}[/b]?\nThis cannot be undone."
        self.pause_refresh()
        try:
            confirmed = await self.push_screen_wait(ConfirmModal("Delete Issue", msg))
        finally:
            self.resume_refresh()
        if confirmed:
            try:
                await self.client.delete_issue(*(i.id for i in issues))
                label = f"Deleted {len(issues)} issues" if len(issues) > 1 else f"Deleted {issues[0].id}"
                self.notify(label)
                self._selected_ids.clear()
                self._load_issues()
            except BdError as e:
                self.notify(f"Error: {e}", severity="error")

    def action_toggle_id_prefix(self) -> None:
        self._strip_id_prefix = not self._strip_id_prefix
        self._rebuild_columns()
        self._populate_table()
        label = "short" if self._strip_id_prefix else "full"
        self.notify(f"ID format: {label}")

    def action_toggle_tree(self) -> None:
        self._tree_mode = not self._tree_mode
        self.clear_notifications()
        label = "ON" if self._tree_mode else "OFF"
        self.notify(f"Tree view {label}", timeout=1.5)
        if not self._tree_mode:
            self._tree_prefixes = {}
        self._load_issues()

    @work
    async def action_switch_worktree(self) -> None:
        """Open worktree picker and switch to the selected worktree."""
        from .screens.worktree_picker import WorktreePicker

        worktrees = self._list_all_worktrees()
        if not worktrees:
            self.notify("No worktrees found", severity="warning")
            return

        self.pause_refresh()
        selected_path = await self.push_screen_wait(
            WorktreePicker(worktrees, self._worktree_path)
        )
        self.resume_refresh()

        if selected_path is None or selected_path == self._worktree_path:
            return

        # Find the selected worktree entry
        selected_wt = next((wt for wt in worktrees if wt["path"] == selected_path), None)
        if selected_wt is None:
            return

        # Switch to the new worktree context
        self._worktree_path = selected_path
        self._worktree_name = selected_wt["name"]

        # The .beads/ database is shared across worktrees (lives in main repo).
        # Update WATCH_PATH to point at the new worktree's .beads/ if it exists,
        # otherwise fall back to walking up from the new path.
        new_beads = Path(selected_path) / ".beads"
        if new_beads.is_dir():
            new_watch = new_beads
        else:
            # Walk up to find .beads/ from the selected worktree root
            new_watch = None
            for parent in [Path(selected_path), *Path(selected_path).parents]:
                candidate = parent / ".beads"
                if candidate.is_dir():
                    new_watch = candidate
                    break

        # Restart live reload with new watch path
        self.stop_live_reload()
        self.WATCH_PATH = new_watch
        self._last_snapshot = {}
        self.start_live_reload()

        # Reload data and update status bar
        self._load_issues()
        self.query_one(StatusBar).worktree_name = self._worktree_name
        self.notify(f"Switched to worktree: {self._worktree_name}")
