"""Confirmation modal screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmModal(ModalScreen[bool | None]):
    """Modal asking the user to confirm or cancel a destructive action."""

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }
    ConfirmModal > #confirm-dialog {
        width: 50;
        max-width: 80%;
        height: auto;
        max-height: 10;
        padding: 1 2;
        background: #1e1e2e;
        border: double #ff8c00;
    }
    ConfirmModal > #confirm-dialog > #confirm-title {
        width: 100%;
        text-style: bold;
        color: #ff8c00;
        text-align: center;
    }
    ConfirmModal > #confirm-dialog > #confirm-body {
        width: 100%;
        color: #cdd6f4;
    }
    ConfirmModal > #confirm-dialog > #confirm-buttons {
        width: 100%;
        layout: horizontal;
        content-align: center middle;
    }
    ConfirmModal > #confirm-dialog > #confirm-buttons > Button {
        margin: 0 1;
        min-width: 12;
    }
    """

    BINDINGS = [
        Binding("y", "confirm", "Confirm", priority=True),
        Binding("n", "cancel", "Cancel", priority=True),
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("enter", "press_focused", "Enter", show=False, priority=True),
        Binding("h", "focus_previous", "Left", show=False, priority=True),
        Binding("l", "focus_next", "Right", show=False, priority=True),
        Binding("j", "focus_next", "Down", show=False, priority=True),
        Binding("k", "focus_previous", "Up", show=False, priority=True),
    ]

    def __init__(self, title: str, body: str) -> None:
        super().__init__()
        self._title = title
        self._body = body

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Static(self._title, id="confirm-title")
            yield Static(self._body, id="confirm-body", markup=True)
            with Horizontal(id="confirm-buttons"):
                yield Button("Cancel", variant="default", id="btn-cancel")
                yield Button("Confirm", variant="error", id="btn-confirm")

    def on_mount(self) -> None:
        self.query_one("#btn-cancel", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm":
            self.dismiss(True)
        else:
            self.dismiss(None)

    def action_press_focused(self) -> None:
        focused = self.focused
        if isinstance(focused, Button):
            focused.press()

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(None)
