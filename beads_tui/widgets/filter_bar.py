"""Search and filter bar widget for the issue list."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Button, Input, Select


class FilterBar(Widget):
    """Search and filter bar for issue list.

    Layout:
        [search text here___________] | Status: [All] | Priority: [All] | Type: [All] | Clear
    """

    DEFAULT_CSS = """
    FilterBar {
        dock: top;
        height: 3;
        padding: 0 1;
    }

    FilterBar #filter-bar {
        height: 3;
        width: 100%;
    }

    FilterBar #search-input {
        width: 1fr;
        min-width: 20;
    }

    FilterBar Select {
        width: 18;
    }

    FilterBar #clear-filters {
        min-width: 10;
    }
    """

    class FiltersChanged(Message):
        """Posted when any filter value changes."""

        def __init__(
            self,
            search: str,
            status: str | None,
            priority: str | None,
            type_: str | None,
        ) -> None:
            super().__init__()
            self.search = search
            self.status = status
            self.priority = priority
            self.type_ = type_

    _search_timer: Timer

    STATUS_OPTIONS: list[tuple[str, str]] = [
        ("All", ""),
        ("Open", "open"),
        ("In Progress", "in_progress"),
        ("Blocked", "blocked"),
        ("Closed", "closed"),
        ("Deferred", "deferred"),
    ]

    PRIORITY_OPTIONS: list[tuple[str, str]] = [
        ("All", ""),
        ("P0 Critical", "0"),
        ("P1 High", "1"),
        ("P2 Normal", "2"),
        ("P3 Low", "3"),
        ("P4 Backlog", "4"),
    ]

    TYPE_OPTIONS: list[tuple[str, str]] = [
        ("All", ""),
        ("Task", "task"),
        ("Bug", "bug"),
        ("Feature", "feature"),
        ("Epic", "epic"),
        ("Chore", "chore"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal(id="filter-bar"):
            yield Input(placeholder="Search issues...", id="search-input")
            yield Select(
                [(text, val) for text, val in self.STATUS_OPTIONS],
                id="status-filter",
                prompt="Status",
            )
            yield Select(
                [(text, val) for text, val in self.PRIORITY_OPTIONS],
                id="priority-filter",
                prompt="Priority",
            )
            yield Select(
                [(text, val) for text, val in self.TYPE_OPTIONS],
                id="type-filter",
                prompt="Type",
            )
            yield Button("Clear", id="clear-filters", variant="default")

    def on_mount(self) -> None:
        self._search_timer = self.set_timer(
            0.3, self._on_search_timer, pause=True
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self._search_timer.reset()

    def on_select_changed(self, event: Select.Changed) -> None:
        self._post_filters_changed()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "clear-filters":
            self.clear_all()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _on_search_timer(self) -> None:
        self._search_timer.pause()
        self._post_filters_changed()

    def _post_filters_changed(self) -> None:
        filters = self.get_filters()
        self.post_message(
            self.FiltersChanged(
                search=filters["search"],
                status=filters["status"],
                priority=filters["priority"],
                type_=filters["type"],
            )
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def focus_search(self) -> None:
        """Focus the search input."""
        self.query_one("#search-input", Input).focus()

    def clear_all(self) -> None:
        """Reset all filters to their defaults and post FiltersChanged."""
        self.query_one("#search-input", Input).value = ""
        self.query_one("#status-filter", Select).value = Select.BLANK
        self.query_one("#priority-filter", Select).value = Select.BLANK
        self.query_one("#type-filter", Select).value = Select.BLANK
        self._post_filters_changed()

    def get_filters(self) -> dict[str, str | None]:
        """Return the current filter state.

        Returns a dict with keys: search, status, priority, type.
        Values are None when set to the default / "All" position.
        """
        search_val = self.query_one("#search-input", Input).value.strip()

        status_sel = self.query_one("#status-filter", Select)
        status_val = status_sel.value if status_sel.value != Select.BLANK else ""

        priority_sel = self.query_one("#priority-filter", Select)
        priority_val = priority_sel.value if priority_sel.value != Select.BLANK else ""

        type_sel = self.query_one("#type-filter", Select)
        type_val = type_sel.value if type_sel.value != Select.BLANK else ""

        return {
            "search": search_val,
            "status": status_val or None,
            "priority": priority_val or None,
            "type": type_val or None,
        }
