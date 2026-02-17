"""Help overlay screen showing all keyboard shortcuts."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

HELP_TEXT = """\
[bold]Keyboard Shortcuts[/bold]

[bold underline]Global[/bold underline]
  [bold]?[/bold]           Show this help
  [bold]q[/bold]           Quit application
  [bold]/[/bold]           Focus search / filter bar
  [bold]r[/bold]           Refresh issues
  [bold]c[/bold]           Create new issue
  [bold]A[/bold]           Toggle show all / open only

[bold underline]Issue List[/bold underline]
  [bold]j / Down[/bold]    Move down
  [bold]k / Up[/bold]      Move up
  [bold]Enter[/bold]       Open issue detail
  [bold]Click header[/bold] Sort by column (click again to reverse)

[bold underline]Columns & Sorting[/bold underline]
  [bold]o[/bold]           Sort picker
  [bold]#[/bold]           Column visibility

[bold underline]Detail View[/bold underline]
  [bold]Escape[/bold]      Back to list
  [bold]p[/bold]           Change priority
  [bold]s[/bold]           Change status
  [bold]a[/bold]           Change assignee
  [bold]e[/bold]           Edit title
  [bold]d[/bold]           Edit description
  [bold]C[/bold]           Add comment

[dim]Press Escape to close[/dim]"""


class HelpScreen(ModalScreen[None]):
    """Modal overlay displaying keyboard shortcuts."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }

    HelpScreen #help-dialog {
        width: 54;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    HelpScreen #help-content {
        width: 1fr;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("question_mark", "dismiss", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="help-dialog"):
                yield Static(HELP_TEXT, id="help-content")

    def action_dismiss(self) -> None:
        self.dismiss(None)
