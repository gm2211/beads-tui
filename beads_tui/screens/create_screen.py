"""Modal screen for creating a new issue."""

from __future__ import annotations

from textual import on
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Select, TextArea
from textual.widgets.option_list import Option

from ..bd_client import BdClient, BdError


# Options for the Type selector
TYPE_OPTIONS: list[tuple[str, str]] = [
    ("task", "task"),
    ("bug", "bug"),
    ("feature", "feature"),
    ("epic", "epic"),
    ("chore", "chore"),
]

# Options for the Priority selector
PRIORITY_OPTIONS: list[tuple[str, str]] = [
    ("P0 - Critical", "0"),
    ("P1 - High", "1"),
    ("P2 - Normal", "2"),
    ("P3 - Low", "3"),
    ("P4 - Backlog", "4"),
]

MAX_PARENT_SUGGESTIONS = 8


class CreateScreen(ModalScreen[dict | None]):
    """Modal dialog for creating a new issue."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("ctrl+s", "submit", "Create", show=True),
    ]

    DEFAULT_CSS = """\
    CreateScreen {
        align: center middle;
    }

    CreateScreen > #dialog {
        width: 72;
        max-width: 90%;
        height: auto;
        max-height: 85%;
        overflow-y: auto;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }

    CreateScreen > #dialog > #dialog-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        margin-bottom: 1;
        color: $text;
    }

    CreateScreen > #dialog .field-label {
        margin-top: 1;
        margin-bottom: 0;
        color: $text-muted;
        text-style: bold;
    }

    CreateScreen > #dialog .field-label-first {
        margin-top: 0;
        margin-bottom: 0;
        color: $text-muted;
        text-style: bold;
    }

    CreateScreen > #dialog Input {
        margin-bottom: 0;
    }

    CreateScreen > #dialog #parent-suggestions {
        height: 6;
        margin-bottom: 1;
    }

    CreateScreen > #dialog Select {
        margin-bottom: 0;
    }

    CreateScreen > #dialog TextArea {
        height: 5;
        margin-bottom: 1;
    }

    CreateScreen > #dialog #button-row {
        width: 100%;
        height: auto;
        align-horizontal: center;
        margin-top: 1;
    }

    CreateScreen > #dialog #button-row Button {
        margin: 0 2;
        min-width: 14;
    }

    CreateScreen > #dialog #btn-create {
        background: $primary;
    }

    CreateScreen > #dialog #error-label {
        color: $error;
        text-align: center;
        width: 100%;
        height: auto;
        display: none;
    }

    CreateScreen > #dialog #error-label.visible {
        display: block;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Create Issue", id="dialog-title")

            yield Label("Title", classes="field-label-first")
            yield Input(placeholder="Issue title (required)", id="title-input")

            yield Label("Type", classes="field-label")
            yield Select(TYPE_OPTIONS, value="task", id="type-select", allow_blank=False)

            yield Label("Priority", classes="field-label")
            yield Select(PRIORITY_OPTIONS, value="2", id="priority-select", allow_blank=False)

            yield Label("Assignee", classes="field-label")
            yield Input(placeholder="Assignee (optional)", id="assignee-input")

            yield Label("Labels", classes="field-label")
            yield Input(placeholder="Comma-separated labels (optional)", id="labels-input")

            yield Label("Parent (will be blocked by new issue)", classes="field-label")
            yield Input(placeholder="Parent issue ID or title (optional)", id="parent-input")
            yield OptionList(id="parent-suggestions")

            yield Label("Description", classes="field-label")
            yield TextArea(id="description-area")

            yield Label("", id="error-label")

            with Horizontal(id="button-row"):
                yield Button("Cancel", variant="default", id="btn-cancel")
                yield Button("Create", variant="primary", id="btn-create")

    def action_cancel(self) -> None:
        """Dismiss the modal without creating an issue."""
        self.dismiss(None)

    def on_mount(self) -> None:
        self._parent_issues: list[tuple[str, str]] = []
        self._parent_ids: set[str] = set()
        parent_suggestions = self.query_one("#parent-suggestions", OptionList)
        parent_suggestions.display = False
        self._load_parent_issues()

    @work(exclusive=True, group="parent-choices")
    async def _load_parent_issues(self) -> None:
        client: BdClient | None = getattr(self.app, "client", None)
        if client is None:
            return
        try:
            issues = await client.list_issues(all_=True)
        except BdError:
            return
        self._parent_issues = [
            (issue.id, issue.title or "")
            for issue in issues
            if issue.status != "closed"
        ]
        self._parent_ids = {issue_id for issue_id, _ in self._parent_issues}
        self._update_parent_suggestions()

    def _matching_parent_issues(self, query: str) -> list[tuple[str, str]]:
        needle = query.lower()
        ranked: list[tuple[int, str, str]] = []
        for issue_id, title in self._parent_issues:
            issue_l = issue_id.lower()
            title_l = title.lower()
            if needle not in issue_l and needle not in title_l:
                continue

            score = 100
            if issue_l == needle:
                score = 0
            elif issue_l.startswith(needle):
                score = 10
            elif title_l.startswith(needle):
                score = 20
            elif needle in title_l:
                score = 30
            else:
                score = 40
            ranked.append((score, issue_id, title))

        ranked.sort(key=lambda item: (item[0], item[1]))
        return [(issue_id, title) for _, issue_id, title in ranked[:MAX_PARENT_SUGGESTIONS]]

    def _hide_parent_suggestions(self) -> None:
        suggestions = self.query_one("#parent-suggestions", OptionList)
        suggestions.clear_options()
        suggestions.display = False

    def _update_parent_suggestions(self) -> None:
        parent_input = self.query_one("#parent-input", Input)
        query = parent_input.value.strip()
        suggestions = self.query_one("#parent-suggestions", OptionList)

        if not query:
            self._hide_parent_suggestions()
            return

        matches = self._matching_parent_issues(query)
        suggestions.clear_options()
        for issue_id, title in matches:
            label = f"{issue_id}  {title}" if title else issue_id
            suggestions.add_option(Option(label, id=issue_id))

        suggestions.display = bool(matches)
        if matches:
            suggestions.highlighted = 0

    def _apply_highlighted_parent_suggestion(self) -> bool:
        suggestions = self.query_one("#parent-suggestions", OptionList)
        if not suggestions.display or suggestions.option_count <= 0:
            return False

        highlighted = suggestions.highlighted if suggestions.highlighted is not None else 0
        if highlighted >= suggestions.option_count:
            highlighted = 0
        option = suggestions.get_option_at_index(highlighted)
        if option.id is None:
            return False

        parent_input = self.query_one("#parent-input", Input)
        parent_input.value = str(option.id)
        parent_input.cursor_position = len(parent_input.value)
        self._hide_parent_suggestions()
        return True

    @on(Input.Changed, "#parent-input")
    def _on_parent_changed(self) -> None:
        self._update_parent_suggestions()

    @on(OptionList.OptionSelected, "#parent-suggestions")
    def _on_parent_suggestion_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id is None:
            return
        parent_input = self.query_one("#parent-input", Input)
        parent_input.value = str(event.option.id)
        parent_input.cursor_position = len(parent_input.value)
        self._hide_parent_suggestions()
        parent_input.focus()

    def action_submit(self) -> None:
        """Validate and submit the form."""
        title_input = self.query_one("#title-input", Input)
        title = title_input.value.strip()

        error_label = self.query_one("#error-label", Label)

        if not title:
            error_label.update("Title is required")
            error_label.add_class("visible")
            title_input.focus()
            return

        error_label.remove_class("visible")

        type_select = self.query_one("#type-select", Select)
        priority_select = self.query_one("#priority-select", Select)
        assignee_input = self.query_one("#assignee-input", Input)
        labels_input = self.query_one("#labels-input", Input)
        parent_input = self.query_one("#parent-input", Input)
        description_area = self.query_one("#description-area", TextArea)

        assignee = assignee_input.value.strip() or None
        labels_raw = labels_input.value.strip()
        labels = [l.strip() for l in labels_raw.split(",") if l.strip()] if labels_raw else None
        parent = parent_input.value.strip() or None
        description = description_area.text.strip() or None

        result = {
            "title": title,
            "type_": str(type_select.value),
            "priority": str(priority_select.value),
            "assignee": assignee,
            "labels": labels,
            "parent": parent,
            "description": description,
        }
        self.dismiss(result)

    def on_key(self, event: Key) -> None:
        """Submit on Enter unless focus is on the description TextArea."""
        focused = self.focused
        parent_input = self.query_one("#parent-input", Input)
        suggestions = self.query_one("#parent-suggestions", OptionList)

        if focused is parent_input:
            if event.key in ("down", "j") and suggestions.display and suggestions.option_count > 0:
                suggestions.action_cursor_down()
                event.prevent_default()
                event.stop()
                return
            if event.key in ("up", "k") and suggestions.display and suggestions.option_count > 0:
                suggestions.action_cursor_up()
                event.prevent_default()
                event.stop()
                return
            if (
                event.key == "enter"
                and suggestions.display
                and suggestions.option_count > 0
                and parent_input.value.strip() not in self._parent_ids
            ):
                if self._apply_highlighted_parent_suggestion():
                    event.prevent_default()
                    event.stop()
                    return

        if event.key == "enter" and not isinstance(focused, (TextArea, Button, Select, OptionList)):
            event.prevent_default()
            event.stop()
            self.action_submit()

    @on(Button.Pressed, "#btn-cancel")
    def handle_cancel(self) -> None:
        self.action_cancel()

    @on(Button.Pressed, "#btn-create")
    def handle_create(self) -> None:
        self.action_submit()
