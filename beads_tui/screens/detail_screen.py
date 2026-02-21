"""Detail screen for viewing a single issue."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Footer, Header, Label, OptionList, Static
from textual.widgets.option_list import Option
from textual import work
from rich.text import Text

from ..bd_client import BdClient, BdError
from ..models import Comment, Issue


_PRIORITY_LABELS: dict[int, tuple[str, str]] = {
    0: ("CRITICAL", "white on red"),
    1: ("HIGH", "white on dark_orange"),
    2: ("MEDIUM", "black on yellow"),
    3: ("LOW", "white on dodger_blue"),
    4: ("MINIMAL", "white on grey37"),
}

_STATUS_LABELS: dict[str, tuple[str, str]] = {
    "open": ("\u25cb Open", "bold white on #2d6a2d"),
    "in_progress": ("\u25d0 In Progress", "bold white on #1a6a6a"),
    "blocked": ("\u25cf Blocked", "bold white on #8b2020"),
    "deferred": ("\u2744 Deferred", "bold white on #2d2d8b"),
    "closed": ("\u2713 Closed", "white on grey37"),
}

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
        super().__init__()
        self._deps = deps

    def compose(self) -> ComposeResult:
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


class DetailScreen(Screen):
    """Show full details of a single issue."""

    BINDINGS = [
        Binding("escape", "go_back", "Back", priority=True),
        Binding("q", "go_back", "Back"),
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
        Binding("p", "change_priority", "Priority"),
        Binding("s", "change_status", "Status"),
        Binding("a", "change_assignee", "Assignee"),
        Binding("e", "edit_title", "Edit title"),
        Binding("d", "edit_description", "Description"),
        Binding("g", "goto_dep", "Go to dep"),
        Binding("o", "noop", "Sort", show=False),
        Binding("numbersign", "noop", "#Columns", show=False),
        Binding("r", "noop", "Refresh", show=False),
        Binding("slash", "noop", "Search", show=False),
        Binding("c", "noop", "Create", show=False),
        Binding("A", "noop", "Toggle All", show=False),
        Binding("question_mark", "noop", "Help", show=False),
    ]

    DEFAULT_CSS = """
    DetailScreen {
        background: #1e1e2e;
    }

    #detail-scroll {
        width: 100%;
        height: 1fr;
        background: #1e1e2e;
    }

    /* --- Header block --- */
    #issue-header {
        width: 100%;
        height: auto;
        background: #181825;
        padding: 1 2;
        border-bottom: solid #333350;
    }

    #issue-id-label {
        color: #6c7086;
        text-style: bold;
        width: 100%;
        height: 1;
    }

    #issue-title-label {
        color: #cdd6f4;
        text-style: bold;
        width: 100%;
        height: auto;
        padding: 0 0 1 0;
    }

    #badge-row {
        width: 100%;
        height: auto;
        layout: horizontal;
    }

    .detail-badge {
        height: 1;
        padding: 0 1;
        margin: 0 1 0 0;
    }

    /* --- Fields panel --- */
    #fields-panel {
        width: 100%;
        height: auto;
        padding: 1 2;
        border-bottom: solid #333350;
    }

    .field-row {
        width: 100%;
        height: 1;
        layout: horizontal;
        padding: 0;
    }

    .field-label {
        width: 14;
        height: 1;
        color: #6c7086;
        text-style: bold;
    }

    .field-value {
        width: 1fr;
        height: 1;
        color: #cdd6f4;
    }

    /* --- Content sections --- */
    .section {
        width: 100%;
        height: auto;
        padding: 1 2;
        border-bottom: solid #333350;
    }

    .section-title {
        color: #89b4fa;
        text-style: bold;
        width: 100%;
        height: 1;
        padding: 0 0 1 0;
    }

    .section-body {
        width: 100%;
        height: auto;
        color: #cdd6f4;
        padding: 0 0 0 1;
    }

    /* --- Comments --- */
    .comment-item {
        width: 100%;
        height: auto;
        padding: 1 1;
        margin: 0 0 1 0;
        background: #21213a;
        border-left: tall #44447a;
    }

    .comment-header {
        width: 100%;
        height: 1;
        layout: horizontal;
    }

    .comment-author {
        color: #89b4fa;
        text-style: bold;
        width: auto;
    }

    .comment-date {
        color: #6c7086;
        width: auto;
        padding: 0 0 0 2;
    }

    .comment-body {
        width: 100%;
        height: auto;
        color: #cdd6f4;
        padding: 1 0 0 0;
    }

    /* --- Dependencies --- */
    .dep-line {
        width: 100%;
        height: 1;
        padding: 0 0 0 1;
    }
    """

    def __init__(self, issue_id: str, prefetch: Issue | None = None):
        super().__init__()
        self.issue_id = issue_id
        self._issue: Issue | None = prefetch
        self._comments: list[Comment] = []

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        with VerticalScroll(id="detail-scroll"):
            # Header block
            with Vertical(id="issue-header"):
                yield Static("", id="issue-id-label")
                yield Static("Loading...", id="issue-title-label")
                with Horizontal(id="badge-row"):
                    yield Static("", id="badge-status", classes="detail-badge")
                    yield Static("", id="badge-priority", classes="detail-badge")
                    yield Static("", id="badge-type", classes="detail-badge")
                    yield Static("", id="badge-assignee", classes="detail-badge")

            # Fields panel
            with Vertical(id="fields-panel"):
                for field_key in ("assignee", "type", "created", "updated", "labels", "due", "ref"):
                    with Horizontal(classes="field-row"):
                        yield Static("", classes="field-label", id=f"fl-{field_key}")
                        yield Static("", classes="field-value", id=f"fv-{field_key}")

            # Description
            with Vertical(classes="section", id="section-description"):
                yield Static("Description", classes="section-title")
                yield Static("", classes="section-body", id="desc-body")

            # Notes
            with Vertical(classes="section", id="section-notes"):
                yield Static("Notes", classes="section-title")
                yield Static("", classes="section-body", id="notes-body")

            # Dependencies
            with Vertical(classes="section", id="section-deps"):
                yield Static("Dependencies", classes="section-title")
                yield Static("", classes="section-body", id="deps-body")

            # Comments
            with Vertical(classes="section", id="section-comments"):
                yield Static("Comments", classes="section-title")
                yield Static("", classes="section-body", id="comments-body")

        yield Footer()

    def on_mount(self) -> None:
        # If we have prefetched list data, render it instantly
        if self._issue is not None:
            self._render_issue()
        # Then load full details (description, comments, deps) in background
        self._load_issue()

    @work(exclusive=True)
    async def _load_issue(self) -> None:
        import asyncio

        client: BdClient | None = self.app.client  # type: ignore[attr-defined]
        if client is None:
            return

        # Load issue details (sequential to avoid Dolt locking conflicts)
        issue: Issue | None = None
        for attempt in range(2):
            try:
                issue = await client.show_issue(self.issue_id)
                break
            except BdError:
                if attempt == 0:
                    await asyncio.sleep(0.3)

        if issue is None:
            if self._issue is None:
                self.query_one("#issue-title-label", Static).update(
                    f"Error loading issue {self.issue_id}"
                )
            return

        self._issue = issue
        self._render_issue()

        # Load comments after issue (separate bd call)
        try:
            self._comments = await client.list_comments(self.issue_id)
        except BdError:
            self._comments = []

        self._render_issue()

    def _render_issue(self) -> None:
        issue = self._issue
        if issue is None:
            return

        # -- Header --
        self.query_one("#issue-id-label", Static).update(
            Text(issue.id, style="bold #6c7086")
        )
        self.query_one("#issue-title-label", Static).update(
            Text(issue.title, style="bold")
        )

        # Badges
        status_label, status_style = _STATUS_LABELS.get(
            issue.status, (issue.status, "")
        )
        self.query_one("#badge-status", Static).update(
            Text(f" {status_label} ", style=status_style)
        )

        pri_label, pri_style = _PRIORITY_LABELS.get(
            issue.priority, (f"P{issue.priority}", "")
        )
        self.query_one("#badge-priority", Static).update(
            Text(f" {pri_label} ", style=pri_style)
        )

        if issue.issue_type:
            self.query_one("#badge-type", Static).update(
                Text(f" {issue.issue_type} ", style="white on dark_magenta")
            )

        assignee = issue.owner or issue.assignee
        if assignee:
            self.query_one("#badge-assignee", Static).update(
                Text(f" @{assignee} ", style="white on grey23")
            )

        # -- Fields panel --
        assignee_val = issue.owner or issue.assignee or "\u2014"
        fields = {
            "assignee": ("Assignee", assignee_val),
            "type": ("Type", issue.issue_type or "\u2014"),
            "created": ("Created", issue.created_at or "\u2014"),
            "updated": ("Updated", issue.updated_at or "\u2014"),
            "labels": ("Labels", ", ".join(issue.labels) if issue.labels else "\u2014"),
            "due": ("Due", issue.due_at or "\u2014"),
            "ref": ("External Ref", issue.external_ref or "\u2014"),
        }
        for key, (label, value) in fields.items():
            self.query_one(f"#fl-{key}", Static).update(
                Text(label, style="bold #6c7086")
            )
            self.query_one(f"#fv-{key}", Static).update(value)

        # -- Description --
        desc_section = self.query_one("#section-description")
        if issue.description:
            self.query_one("#desc-body", Static).update(issue.description)
            desc_section.display = True
        else:
            desc_section.display = False

        # -- Notes --
        notes_section = self.query_one("#section-notes")
        if issue.notes:
            self.query_one("#notes-body", Static).update(issue.notes)
            notes_section.display = True
        else:
            notes_section.display = False

        # -- Dependencies --
        deps_section = self.query_one("#section-deps")
        has_deps = bool(issue.dependencies or issue.dependents)
        if has_deps:
            parts: list[Text | str] = []
            if issue.dependencies:
                parts.append(Text("Blocks:\n", style="bold #6c7086"))
                for dep in issue.dependencies:
                    parts.append(self._dep_line("\u2192", dep))
            if issue.dependents:
                if issue.dependencies:
                    parts.append("\n")
                parts.append(Text("Blocked by:\n", style="bold #6c7086"))
                for dep in issue.dependents:
                    parts.append(self._dep_line("\u2190", dep))
            self.query_one("#deps-body", Static).update(Text.assemble(*parts))
            deps_section.display = True
        else:
            deps_section.display = False

        # -- Comments --
        comments_section = self.query_one("#section-comments")
        if self._comments:
            parts: list[Text | str] = []
            for i, comment in enumerate(self._comments):
                if i > 0:
                    parts.append(Text("\n\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n", style="#333350"))
                ts = comment.created_at[:16] if comment.created_at else ""
                parts.append(Text(comment.author or "unknown", style="bold #89b4fa"))
                parts.append(Text(f"  {ts}\n", style="#6c7086"))
                # Wrap comment text at 80 chars
                raw = comment.text or ""
                wrapped_lines = []
                for raw_line in raw.splitlines():
                    while len(raw_line) > 80:
                        wrapped_lines.append(raw_line[:80])
                        raw_line = raw_line[80:]
                    wrapped_lines.append(raw_line)
                parts.append(Text("\n".join(wrapped_lines) + "\n", style="#cdd6f4"))
            self.query_one("#comments-body", Static).update(Text.assemble(*parts))
            comments_section.display = True
        else:
            comments_section.display = False

    def _dep_line(self, arrow: str, dep) -> Text:
        dep_id = dep.id or (dep.depends_on_id if hasattr(dep, "depends_on_id") else dep.issue_id)
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

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_scroll_down(self) -> None:
        self.query_one("#detail-scroll", VerticalScroll).scroll_down(animate=False)

    def action_scroll_up(self) -> None:
        self.query_one("#detail-scroll", VerticalScroll).scroll_up(animate=False)

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
                deps_list.append(("\u2192", dep_id, f"\u2192 {dep_id}  {dep.title or ''}"))
        for dep in (self._issue.dependents or []):
            dep_id = (dep.id or dep.issue_id) if hasattr(dep, "issue_id") else dep.id
            if dep_id:
                deps_list.append(("\u2190", dep_id, f"\u2190 {dep_id}  {dep.title or ''}"))
        if not deps_list:
            self.notify("No linked issues")
            return
        if len(deps_list) == 1:
            target_id = deps_list[0][1]
        else:
            target_id = await self.app.push_screen_wait(DependencyPicker(deps_list))
        if target_id:
            self.app.push_screen(DetailScreen(target_id))
