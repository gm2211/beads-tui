"""Modal screen for creating a new issue."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, TextArea


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

    CreateScreen > #dialog Select {
        margin-bottom: 0;
    }

    CreateScreen > #dialog TextArea {
        height: 8;
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

            yield Label("Description", classes="field-label")
            yield TextArea(id="description-area")

            yield Label("", id="error-label")

            with Horizontal(id="button-row"):
                yield Button("Cancel", variant="default", id="btn-cancel")
                yield Button("Create", variant="primary", id="btn-create")

    def action_cancel(self) -> None:
        """Dismiss the modal without creating an issue."""
        self.dismiss(None)

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
        description_area = self.query_one("#description-area", TextArea)

        assignee = assignee_input.value.strip() or None
        labels_raw = labels_input.value.strip()
        labels = [l.strip() for l in labels_raw.split(",") if l.strip()] if labels_raw else None
        description = description_area.text.strip() or None

        result = {
            "title": title,
            "type_": str(type_select.value),
            "priority": str(priority_select.value),
            "assignee": assignee,
            "labels": labels,
            "description": description,
        }
        self.dismiss(result)

    @on(Button.Pressed, "#btn-cancel")
    def handle_cancel(self) -> None:
        self.action_cancel()

    @on(Button.Pressed, "#btn-create")
    def handle_create(self) -> None:
        self.action_submit()
