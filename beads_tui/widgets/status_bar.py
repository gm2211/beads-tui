"""Bottom status bar widget with contextual information."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from beads_tui import __version__


class StatusBar(Widget):
    """Bottom status bar showing worktree name, selected count, and refresh time."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
    }

    StatusBar #status-bar {
        width: 1fr;
        height: 1;
    }

    StatusBar #status-left {
        width: 1fr;
        content-align-horizontal: left;
    }

    StatusBar #status-center {
        width: 1fr;
        content-align-horizontal: center;
        text-align: center;
    }

    StatusBar #status-right {
        width: 1fr;
        content-align-horizontal: right;
        text-align: right;
    }
    """

    issue_count: reactive[int] = reactive(0)
    total_count: reactive[int] = reactive(0)
    last_refresh: reactive[str] = reactive("")
    selected_count: reactive[int] = reactive(0)
    worktree_name: reactive[str] = reactive("")

    def compose(self) -> ComposeResult:
        with Horizontal(id="status-bar"):
            yield Static("", id="status-left")
            yield Static("", id="status-center")
            yield Static("", id="status-right")

    def _update_left(self) -> None:
        label = self.worktree_name if self.worktree_name else ""
        if self.selected_count > 0:
            sel = f"{self.selected_count} selected"
            label = f"{label} | {sel}" if label else sel
        self.query_one("#status-left", Static).update(label)

    def _update_center(self) -> None:
        if self.total_count and self.issue_count != self.total_count:
            text = f"Showing {self.issue_count} of {self.total_count} issues"
        else:
            text = f"{self.issue_count} issues"
        self.query_one("#status-center", Static).update(text)

    def _update_right(self) -> None:
        version = f"v{__version__}"
        if self.last_refresh:
            text = f"{version} | {self.last_refresh}"
        else:
            text = version
        self.query_one("#status-right", Static).update(text)

    def watch_issue_count(self, value: int) -> None:
        self._update_center()

    def watch_total_count(self, value: int) -> None:
        self._update_center()

    def watch_last_refresh(self, value: str) -> None:
        self._update_right()

    def watch_selected_count(self, value: int) -> None:
        self._update_left()

    def watch_worktree_name(self, value: str) -> None:
        self._update_left()

    def set_refreshing(self) -> None:
        """Show a refreshing indicator in the right section."""
        self.last_refresh = "Refreshing..."

    def set_refresh_time(self, time_str: str) -> None:
        """Set the last refresh time display (e.g. 'Last refresh: 14:32:05')."""
        self.last_refresh = f"Last refresh: {time_str}"
