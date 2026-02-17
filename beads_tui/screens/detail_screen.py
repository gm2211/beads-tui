"""Detail screen for viewing a single issue."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Footer, Header, Label, OptionList, Static
from textual.widgets.option_list import Option
from textual import work
from rich.text import Text

from ..bd_client import BdClient, BdError
from ..models import Issue


_PRIORITY_LABELS: dict[int, tuple[str, str]] = {
    0: ("CRITICAL", "white on red"),
    1: ("HIGH", "white on dark_orange"),
    2: ("MEDIUM", "black on yellow"),
    3: ("LOW", "white on dodger_blue"),
    4: ("MINIMAL", "white on grey37"),
}

_STATUS_LABELS: dict[str, tuple[str, str]] = {
    "open": ("\u25cb Open", "white on green"),
    "in_progress": ("\u25d0 In Progress", "white on cyan"),
    "blocked": ("\u25cf Blocked", "white on red"),
    "deferred": ("\u2744 Deferred", "white on blue"),
    "closed": ("\u2713 Closed", "white on grey37"),
}


class DependencyPicker(ModalScreen[str | None]):
    """Pick a dependency to navigate to."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    DependencyPicker {
        align: center middle;
    }
    DependencyPicker > #dep-picker-dialog {
        width: 70;
        max-width: 90%;
        height: auto;
        max-height: 70%;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }
    DependencyPicker > #dep-picker-dialog > #dep-picker-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        margin-bottom: 1;
    }
    """

    def __init__(self, deps: list[tuple[str, str, str]]):
        # deps = list of (direction_arrow, issue_id, display_text)
        super().__init__()
        self._deps = deps

    def compose(self) -> ComposeResult:
        from textual.containers import Vertical
        with Vertical(id="dep-picker-dialog"):
            yield Label("Linked Issues", id="dep-picker-title")
            option_list = OptionList(id="dep-options")
            for _arrow, issue_id, display in self._deps:
                option_list.add_option(Option(display, id=issue_id))
            yield option_list

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.id))

    def action_cancel(self) -> None:
        self.dismiss(None)


class Badge(Static):
    """A small styled chip/badge."""

    DEFAULT_CSS = """
    Badge {
        padding: 0 1;
        margin: 0 1 0 0;
        height: 1;
    }
    """


class DetailScreen(Screen):
    """Show full details of a single issue."""

    BINDINGS = [
        Binding("escape", "go_back", "Back", priority=True),
        Binding("q", "go_back", "Back"),
        Binding("p", "change_priority", "Priority"),
        Binding("s", "change_status", "Status"),
        Binding("a", "change_assignee", "Assignee"),
        Binding("e", "edit_title", "Edit title"),
        Binding("d", "edit_description", "Description"),
        Binding("g", "goto_dep", "Go to dep"),
        Binding("numbersign", "noop", "#Columns", show=False),
        Binding("r", "noop", "Refresh", show=False),
        Binding("slash", "noop", "Search", show=False),
        Binding("c", "noop", "Create", show=False),
        Binding("A", "noop", "Toggle All", show=False),
        Binding("question_mark", "noop", "Help", show=False),
    ]

    def __init__(self, issue_id: str):
        super().__init__()
        self.issue_id = issue_id
        self._issue: Issue | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="detail-scroll"):
            yield Label("Loading...", id="detail-title")
            with Horizontal(id="badges"):
                yield Badge("", id="badge-priority")
                yield Badge("", id="badge-status")
                yield Badge("", id="badge-type")
                yield Badge("", id="badge-assignee")
            yield Static("", id="detail-description")
            yield Static("", id="detail-notes")
            yield Static("", id="detail-labels")
            yield Static("", id="detail-deps")
            yield Static("", id="detail-meta")
        yield Footer()

    def on_mount(self) -> None:
        self._load_issue()

    @work(exclusive=True)
    async def _load_issue(self) -> None:
        client: BdClient | None = self.app.client  # type: ignore[attr-defined]
        if client is None:
            return
        try:
            issue = await client.show_issue(self.issue_id)
        except BdError:
            self._show_error()
            return
        self._issue = issue
        self._render_issue()

    def _show_error(self) -> None:
        title_w = self.query_one("#detail-title", Label)
        title_w.update(f"Error loading issue {self.issue_id}")

    def _render_issue(self) -> None:
        issue = self._issue
        if issue is None:
            return

        # Title
        title_w = self.query_one("#detail-title", Label)
        title_w.update(Text(f"{issue.id}  {issue.title}", style="bold"))

        # Badges
        pri_label, pri_style = _PRIORITY_LABELS.get(
            issue.priority, (f"P{issue.priority}", "")
        )
        self.query_one("#badge-priority", Badge).update(
            Text(f" {pri_label} ", style=pri_style)
        )

        status_label, status_style = _STATUS_LABELS.get(
            issue.status, (issue.status, "")
        )
        self.query_one("#badge-status", Badge).update(
            Text(f" {status_label} ", style=status_style)
        )

        if issue.issue_type:
            self.query_one("#badge-type", Badge).update(
                Text(f" {issue.issue_type} ", style="white on dark_magenta")
            )

        assignee = issue.owner or issue.assignee
        if assignee:
            self.query_one("#badge-assignee", Badge).update(
                Text(f" @{assignee} ", style="white on grey23")
            )

        # Description
        desc_w = self.query_one("#detail-description", Static)
        if issue.description:
            desc_w.update(
                Text.assemble(
                    Text("\n Description\n", style="bold underline"),
                    "\n",
                    issue.description,
                    "\n",
                )
            )
        else:
            desc_w.update("")

        # Notes
        notes_w = self.query_one("#detail-notes", Static)
        if issue.notes:
            notes_w.update(
                Text.assemble(
                    Text("\n Notes\n", style="bold underline"),
                    "\n",
                    issue.notes,
                    "\n",
                )
            )
        else:
            notes_w.update("")

        # Labels
        labels_w = self.query_one("#detail-labels", Static)
        if issue.labels:
            parts: list[Text | str] = [Text("\n Labels\n", style="bold underline"), "\n"]
            for lbl in issue.labels:
                parts.append(Text(f" {lbl} ", style="black on dark_cyan"))
                parts.append("  ")
            parts.append("\n")
            labels_w.update(Text.assemble(*parts))
        else:
            labels_w.update("")

        # Dependencies
        deps_w = self.query_one("#detail-deps", Static)
        dep_parts: list[Text | str] = []

        _STATUS_SYMBOLS: dict[str, tuple[str, str]] = {
            "open": ("\u25cb", "green"),
            "in_progress": ("\u25d0", "cyan"),
            "blocked": ("\u25cf", "bold red"),
            "deferred": ("\u2744", "blue"),
            "closed": ("\u2713", "dim"),
        }

        _PRIORITY_SHORT: dict[int, tuple[str, str]] = {
            0: ("P0", "bold red"),
            1: ("P1", "dark_orange"),
            2: ("P2", "yellow"),
            3: ("P3", "dodger_blue"),
            4: ("P4", "dim"),
        }

        def _dep_line(arrow: str, dep) -> Text:  # type: ignore[no-untyped-def]
            dep_id = dep.id or dep.depends_on_id if hasattr(dep, "depends_on_id") else dep.id or dep.issue_id
            is_closed = dep.status == "closed"
            dim = "dim " if is_closed else ""

            sym, sym_style = _STATUS_SYMBOLS.get(dep.status, ("?", ""))
            pri_label, pri_style = _PRIORITY_SHORT.get(dep.priority, ("P?", ""))

            return Text.assemble(
                Text(f"  {arrow} ", style=dim + "default"),
                Text(sym, style=dim + sym_style),
                Text(" "),
                Text(pri_label, style=dim + pri_style),
                Text(" "),
                Text(dep_id, style=dim + "bold #89b4fa"),
                Text("  "),
                Text(dep.title or "", style=dim + "default"),
                Text("\n"),
            )

        if issue.dependencies:
            dep_parts.append(Text("\n Dependencies (blocks)\n", style="bold underline"))
            dep_parts.append("\n")
            for dep in issue.dependencies:
                dep_parts.append(_dep_line("\u2192", dep))
        if issue.dependents:
            dep_parts.append(Text("\n Blocked by\n", style="bold underline"))
            dep_parts.append("\n")
            for dep in issue.dependents:
                dep_parts.append(_dep_line("\u2190", dep))
        if dep_parts:
            deps_w.update(Text.assemble(*dep_parts))
        else:
            deps_w.update("")

        # Metadata
        meta_parts = [
            Text("\n Info\n", style="bold underline"),
            "\n",
            f"  Created:   {issue.created_at or 'unknown'}\n",
            f"  Updated:   {issue.updated_at or 'unknown'}\n",
            f"  Comments:  {issue.comment_count}\n",
        ]
        if issue.due_at:
            meta_parts.append(f"  Due:       {issue.due_at}\n")
        if issue.external_ref:
            meta_parts.append(f"  Ref:       {issue.external_ref}\n")
        meta_w = self.query_one("#detail-meta", Static)
        meta_w.update(Text.assemble(*meta_parts))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_noop(self) -> None:
        pass

    @work
    async def action_change_priority(self) -> None:
        if self._issue is None:
            return
        from ..widgets.priority_picker import PriorityPicker
        result = await self.app.push_screen_wait(PriorityPicker(current=self._issue.priority))
        if result is not None:
            client: BdClient = self.app.client  # type: ignore[attr-defined]
            await client.update_issue(self._issue.id, priority=result)
            self.notify(f"Priority updated to P{result}")
            self._load_issue()

    @work
    async def action_change_status(self) -> None:
        if self._issue is None:
            return
        from ..widgets.status_picker import StatusPicker
        result = await self.app.push_screen_wait(StatusPicker(current=self._issue.status))
        if result is not None:
            client: BdClient = self.app.client  # type: ignore[attr-defined]
            if result == "closed":
                await client.close_issue(self._issue.id)
            else:
                await client.update_issue(self._issue.id, status=result)
            self.notify(f"Status updated to {result}")
            self._load_issue()

    @work
    async def action_change_assignee(self) -> None:
        if self._issue is None:
            return
        from ..widgets.text_input_modal import TextInputModal
        result = await self.app.push_screen_wait(
            TextInputModal("Assignee", self._issue.assignee)
        )
        if result is not None:
            client: BdClient = self.app.client  # type: ignore[attr-defined]
            await client.update_issue(self._issue.id, assignee=result)
            self.notify("Assignee updated")
            self._load_issue()

    @work
    async def action_edit_title(self) -> None:
        if self._issue is None:
            return
        from ..widgets.text_input_modal import TextInputModal
        result = await self.app.push_screen_wait(
            TextInputModal("Title", self._issue.title)
        )
        if result is not None:
            client: BdClient = self.app.client  # type: ignore[attr-defined]
            await client.update_issue(self._issue.id, title=result)
            self.notify("Title updated")
            self._load_issue()

    @work
    async def action_edit_description(self) -> None:
        if self._issue is None:
            return
        from ..widgets.text_input_modal import TextInputModal
        result = await self.app.push_screen_wait(
            TextInputModal("Description", self._issue.description, multiline=True)
        )
        if result is not None:
            client: BdClient = self.app.client  # type: ignore[attr-defined]
            await client.update_issue(self._issue.id, description=result)
            self.notify("Description updated")
            self._load_issue()

    @work
    async def action_goto_dep(self) -> None:
        if self._issue is None:
            return
        deps_list: list[tuple[str, str, str]] = []
        for dep in (self._issue.dependencies or []):
            dep_id = (dep.id or dep.depends_on_id) if hasattr(dep, "depends_on_id") else dep.id
            if dep_id:
                deps_list.append(("→", dep_id, f"→ {dep_id}  {dep.title or ''}"))
        for dep in (self._issue.dependents or []):
            dep_id = (dep.id or dep.issue_id) if hasattr(dep, "issue_id") else dep.id
            if dep_id:
                deps_list.append(("←", dep_id, f"← {dep_id}  {dep.title or ''}"))
        if not deps_list:
            self.notify("No linked issues")
            return
        if len(deps_list) == 1:
            target_id = deps_list[0][1]
        else:
            target_id = await self.app.push_screen_wait(DependencyPicker(deps_list))
        if target_id:
            self.app.push_screen(DetailScreen(target_id))
