"""Priority picker modal screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList
from textual.widgets.option_list import Option
from rich.text import Text


_PRIORITIES: list[tuple[int, str, str]] = [
    (0, "P0 Critical", "bold red"),
    (1, "P1 High", "dark_orange"),
    (2, "P2 Normal", "yellow"),
    (3, "P3 Low", "dodger_blue1"),
    (4, "P4 Backlog", "dim"),
]


class PriorityPicker(ModalScreen[int | None]):
    """Small centered modal for selecting a priority level."""

    DEFAULT_CSS = """
    PriorityPicker {
        align: center middle;
    }
    PriorityPicker > Vertical {
        width: 22;
        height: auto;
        max-height: 12;
        border: solid $accent;
        background: $surface;
        padding: 0 1;
    }
    PriorityPicker > Vertical > #picker-title {
        text-align: center;
        text-style: bold;
        padding: 0 0 1 0;
        color: $text;
    }
    PriorityPicker OptionList {
        height: auto;
        max-height: 7;
        border: none;
        padding: 0;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
    ]

    def __init__(self, current: int = 2) -> None:
        super().__init__()
        self._current = current

    def compose(self) -> ComposeResult:
        with Vertical():
            from textual.widgets import Static
            yield Static("Priority", id="picker-title")
            option_list = OptionList(id="priority-options")
            for value, label, style in _PRIORITIES:
                option_list.add_option(Option(Text(label, style=style), id=str(value)))
            yield option_list

    def on_mount(self) -> None:
        ol = self.query_one("#priority-options", OptionList)
        ol.highlighted = self._current
        ol.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(int(event.option_id))

    def action_cancel(self) -> None:
        self.dismiss(None)
