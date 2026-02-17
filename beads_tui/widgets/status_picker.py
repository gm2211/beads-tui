"""Status picker modal screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option
from rich.text import Text


_STATUSES: list[tuple[str, str, str]] = [
    ("open", "\u25cb Open", "green"),
    ("in_progress", "\u25d0 In Progress", "cyan"),
    ("blocked", "\u25cf Blocked", "bold red"),
    ("deferred", "\u2744 Deferred", "blue"),
    ("closed", "\u2713 Closed", "dim"),
]


class StatusPicker(ModalScreen[str | None]):
    """Small centered modal for selecting an issue status."""

    DEFAULT_CSS = """
    StatusPicker {
        align: center middle;
    }
    StatusPicker > Vertical {
        width: 24;
        height: auto;
        max-height: 14;
        border: solid $accent;
        background: $surface;
        padding: 0 1;
    }
    StatusPicker > Vertical > #picker-title {
        text-align: center;
        text-style: bold;
        padding: 0 0 1 0;
        color: $text;
    }
    StatusPicker OptionList {
        height: auto;
        max-height: 7;
        border: none;
        padding: 0;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
    ]

    def __init__(self, current: str = "open") -> None:
        super().__init__()
        self._current = current

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Status", id="picker-title")
            option_list = OptionList(id="status-options")
            for value, label, style in _STATUSES:
                option_list.add_option(Option(Text(label, style=style), id=value))
            yield option_list

    def on_mount(self) -> None:
        ol = self.query_one("#status-options", OptionList)
        # Find the index of the current status
        for idx, (value, _, _) in enumerate(_STATUSES):
            if value == self._current:
                ol.highlighted = idx
                break
        ol.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option_id))

    def action_cancel(self) -> None:
        self.dismiss(None)
