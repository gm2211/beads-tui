"""Main Textual application."""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static


class BeadsTuiApp(App):
    """Interactive TUI for beads (bd) issue tracker."""

    TITLE = "Beads TUI"
    CSS_PATH = "styles/app.tcss"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Welcome to Beads TUI", id="placeholder")
        yield Footer()
