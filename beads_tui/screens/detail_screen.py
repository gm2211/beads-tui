"""Detail screen for viewing a single issue."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, Static
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
        Binding("numbersign", "noop", "#Columns", show=False),
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
        if issue.dependencies:
            dep_parts.append(Text("\n Dependencies (blocks)\n", style="bold underline"))
            dep_parts.append("\n")
            for dep in issue.dependencies:
                dep_parts.append(f"  \u2192 {dep.id or dep.depends_on_id}  {dep.title}\n")
        if issue.dependents:
            dep_parts.append(Text("\n Blocked by\n", style="bold underline"))
            dep_parts.append("\n")
            for dep in issue.dependents:
                dep_parts.append(f"  \u2190 {dep.id or dep.issue_id}  {dep.title}\n")
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
