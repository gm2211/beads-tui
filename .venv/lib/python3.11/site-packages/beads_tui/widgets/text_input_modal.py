"""Generic text input modal screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static, TextArea


class TextInputModal(ModalScreen[str | None]):
    """Modal for editing a text value (single-line or multi-line)."""

    DEFAULT_CSS = """
    TextInputModal {
        align: center middle;
    }
    TextInputModal > Vertical {
        width: 60;
        height: auto;
        max-height: 24;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    TextInputModal > Vertical > #modal-title {
        text-align: center;
        text-style: bold;
        padding: 0 0 1 0;
        color: $text;
    }
    TextInputModal Input {
        margin: 1 0;
    }
    TextInputModal TextArea {
        height: 10;
        margin: 1 0;
    }
    TextInputModal #button-bar {
        height: 3;
        align: right middle;
        padding: 1 0 0 0;
    }
    TextInputModal Button {
        margin: 0 1;
        min-width: 10;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
    ]

    def __init__(
        self,
        title: str,
        current_value: str = "",
        multiline: bool = False,
    ) -> None:
        super().__init__()
        self._title = title
        self._current_value = current_value
        self._multiline = multiline

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"Edit {self._title}", id="modal-title")
            if self._multiline:
                yield TextArea(self._current_value, id="text-editor")
            else:
                yield Input(
                    value=self._current_value,
                    placeholder=self._title,
                    id="text-input",
                )
            with Horizontal(id="button-bar"):
                yield Button("Cancel", variant="default", id="btn-cancel")
                yield Button("Save", variant="primary", id="btn-save")

    def on_mount(self) -> None:
        if self._multiline:
            self.query_one("#text-editor", TextArea).focus()
        else:
            self.query_one("#text-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self._save()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._save()

    def key_ctrl_s(self) -> None:
        self._save()

    def _save(self) -> None:
        if self._multiline:
            value = self.query_one("#text-editor", TextArea).text
        else:
            value = self.query_one("#text-input", Input).value
        self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(None)
