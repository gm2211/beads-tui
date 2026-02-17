"""Main Textual application."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Callable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Header
from textual import on, work
from rich.text import Text

from .bd_client import BdClient, BdError
from .mixins.live_reload import LiveReloadMixin, diff_issues
from .models import Issue
from .screens.create_screen import CreateScreen
from .screens.help_screen import HelpScreen
from .widgets.filter_bar import FilterBar
from .widgets.status_bar import StatusBar


# ---------------------------------------------------------------------------
# Priority / status display helpers
# ---------------------------------------------------------------------------

_PRIORITY_STYLES: dict[int, tuple[str, str]] = {
    0: ("P0", "bold red"),
    1: ("P1", "dark_orange"),
    2: ("P2", "yellow"),
    3: ("P3", "dodger_blue"),
    4: ("P4", "dim"),
}

_STATUS_SYMBOLS: dict[str, str] = {
    "open": "\u25cb",          # open circle
    "in_progress": "\u25d0",   # half circle
    "blocked": "\u25cf",       # filled circle
    "deferred": "\u2744",      # snowflake
    "closed": "\u2713",        # checkmark
}


def _styled(value: str, style: str) -> Text:
    return Text(value, style=style)


def _priority_cell(priority: int) -> Text:
    label, style = _PRIORITY_STYLES.get(priority, ("P?", ""))
    return _styled(label, style)


def _status_cell(status: str) -> Text:
    symbol = _STATUS_SYMBOLS.get(status, status)
    style_map = {
        "open": "green",
        "in_progress": "cyan",
        "blocked": "bold red",
        "deferred": "blue",
        "closed": "dim",
    }
    return _styled(symbol, style_map.get(status, ""))


def _title_cell(title: str, priority: int) -> Text:
    _, style = _PRIORITY_STYLES.get(priority, ("", ""))
    return _styled(title, style)


def _short_date(dt: str) -> str:
    if not dt:
        return ""
    return dt[:10]


def _deps_cell(issue: Issue) -> Text:
    """Show dependency counts with directional indicators."""
    parts = []
    if issue.dependency_count > 0:
        parts.append(Text(f"\u2192{issue.dependency_count}", style="dodger_blue"))
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
    "id": ColumnDef(key="id", label="ID", getter=lambda i: _styled(i.id, "bold"), width=12),
    "priority": ColumnDef(key="priority", label="P", getter=lambda i: _priority_cell(i.priority), width=4),
    "status": ColumnDef(key="status", label="Status", getter=lambda i: _status_cell(i.status), width=8),
    "type": ColumnDef(key="type", label="Type", getter=lambda i: Text(i.issue_type or ""), width=10),
    "title": ColumnDef(key="title", label="Title", getter=lambda i: _title_cell(i.title, i.priority), width=None),
    "assignee": ColumnDef(key="assignee", label="Assignee", getter=lambda i: Text(i.owner or i.assignee or ""), width=12),
    "updated": ColumnDef(key="updated", label="Updated", getter=lambda i: Text(_short_date(i.updated_at)), width=12),
    "created": ColumnDef(key="created", label="Created", getter=lambda i: Text(_short_date(i.created_at)), width=12),
    "labels": ColumnDef(key="labels", label="Labels", getter=lambda i: Text(", ".join(i.labels)), width=15),
    "deps": ColumnDef(key="deps", label="Deps", getter=_deps_cell, width=8),
}

DEFAULT_COLUMNS = ["id", "priority", "status", "type", "title", "updated"]


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
        return (issue.owner or issue.assignee or "").lower()
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
        Binding("enter", "select_issue", "Open", show=False),
        Binding("A", "toggle_all", "Toggle All", key_display="A"),
        Binding("o", "sort_picker", "Sort"),
        Binding("numbersign", "column_menu", "Columns", key_display="#"),
        Binding("p", "quick_priority", "Priority", show=False),
        Binding("s", "quick_status", "Status", show=False),
        Binding("x", "quick_close", "Close", show=False),
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
        self._current_filters: dict = {
            "search": None,
            "statuses": {"open", "in_progress"} if not show_all else None,
            "priority": None,
            "type": None,
        }

    def compose(self) -> ComposeResult:
        yield Header()
        yield FilterBar()
        yield DataTable(id="issue-table", cursor_type="row")
        yield StatusBar()

    def on_mount(self) -> None:
        try:
            self.client = BdClient(bd_path=self._bd_path, db_path=self._db_path)
        except BdError:
            self.client = None
        self._rebuild_columns()
        self._load_issues()
        self.start_live_reload()

    # ------------------------------------------------------------------
    # Column management
    # ------------------------------------------------------------------

    def _rebuild_columns(self) -> None:
        """Rebuild DataTable columns from active column list + sort indicators."""
        table = self.query_one("#issue-table", DataTable)
        table.clear(columns=True)
        for col_key in self._active_columns:
            col_def = AVAILABLE_COLUMNS.get(col_key)
            if not col_def:
                continue
            label = col_def.label
            if col_key == self._sort_column:
                arrow = "\u25b2" if not self._sort_reverse else "\u25bc"
                label = f"{label} {arrow}"
            if col_def.width:
                table.add_column(label, key=col_key, width=col_def.width)
            else:
                table.add_column(label, key=col_key)

    def _get_row_cells(self, issue: Issue) -> list[Text | str]:
        """Build row cells based on active columns."""
        cells: list[Text | str] = []
        for col_key in self._active_columns:
            col_def = AVAILABLE_COLUMNS.get(col_key)
            if col_def:
                cells.append(col_def.getter(issue))
            else:
                cells.append("")
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
        self._issues = issues
        self._apply_filters_and_sort()
        self._populate_table()
        self._update_status_bar()

    async def refresh_data(self) -> None:
        """LiveReloadMixin callback: incremental refresh with diff."""
        if self.client is None:
            return
        try:
            new_issues = await self.client.list_issues(all_=True)
        except BdError:
            return

        added, changed, removed_ids = diff_issues(self._issues, new_issues)
        if not added and not changed and not removed_ids:
            return

        self._issues = new_issues
        self._apply_filters_and_sort()

        table = self.query_one("#issue-table", DataTable)

        # Remove deleted rows
        for rid in removed_ids:
            try:
                table.remove_row(rid)
            except Exception:
                pass

        # Update changed rows
        changed_ids = {i.id for i in changed}
        for issue in self._filtered_issues:
            if issue.id in changed_ids:
                cells = self._get_row_cells(issue)
                for idx, col_key in enumerate(self._active_columns):
                    try:
                        table.update_cell(issue.id, col_key, cells[idx])
                    except Exception:
                        pass

        # For added rows, or if sort order changed, rebuild
        if added:
            self._populate_table()

        self._update_status_bar()

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
                or q in (i.owner or "").lower()
                or q in (i.assignee or "").lower()
                or q in (i.issue_type or "").lower()
            ]

        # Priority filter
        priority = f.get("priority")
        if priority is not None:
            try:
                pval = int(priority)
                filtered = [i for i in filtered if i.priority == pval]
            except (ValueError, TypeError):
                pass

        # Type filter
        type_ = f.get("type")
        if type_:
            filtered = [i for i in filtered if i.issue_type == type_]

        # Sort
        filtered.sort(
            key=lambda i: _sort_key_for_column(self._sort_column, i),
            reverse=self._sort_reverse,
        )

        self._filtered_issues = filtered

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
        has_filter = any(
            v for k, v in self._current_filters.items()
            if k == "statuses" and v is not None or k != "statuses" and v
        )
        status_bar.filter_active = has_filter
        statuses = self._current_filters.get("statuses")
        if statuses is None:
            view = "All Issues"
        else:
            view = "Filtered"
        status_bar.view_name = view

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    @on(FilterBar.FiltersChanged)
    def _on_filters_changed(self, event: FilterBar.FiltersChanged) -> None:
        self._current_filters = {
            "search": event.search or None,
            "statuses": event.statuses,
            "priority": event.priority,
            "type": event.type_,
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
        self.push_screen(DetailScreen(issue_id))

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
        self.push_screen(DetailScreen(issue_id))

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

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

        def _on_dismiss(result: tuple[str, bool] | None) -> None:
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

    @work
    async def action_quick_priority(self) -> None:
        issue = self._get_selected_issue()
        if not issue or not self.client:
            return
        from .widgets.priority_picker import PriorityPicker
        result = await self.push_screen_wait(PriorityPicker(current=issue.priority))
        if result is not None:
            try:
                await self.client.update_issue(issue.id, priority=result)
                self.notify(f"P{result} set on {issue.id}")
                self._load_issues()
            except BdError as e:
                self.notify(f"Error: {e}", severity="error")

    @work
    async def action_quick_status(self) -> None:
        issue = self._get_selected_issue()
        if not issue or not self.client:
            return
        from .widgets.status_picker import StatusPicker
        result = await self.push_screen_wait(StatusPicker(current=issue.status))
        if result is not None:
            try:
                if result == "closed":
                    await self.client.close_issue(issue.id)
                else:
                    await self.client.update_issue(issue.id, status=result)
                self.notify(f"{result} set on {issue.id}")
                self._load_issues()
            except BdError as e:
                self.notify(f"Error: {e}", severity="error")

    async def action_quick_close(self) -> None:
        issue = self._get_selected_issue()
        if not issue or not self.client:
            return
        try:
            await self.client.close_issue(issue.id)
            self.notify(f"Closed {issue.id}")
            self._load_issues()
        except BdError as e:
            self.notify(f"Error: {e}", severity="error")
