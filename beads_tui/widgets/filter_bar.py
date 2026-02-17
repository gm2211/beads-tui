"""Search and filter bar widget for the issue list."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Button, Checkbox, Input, Label, Select


# ---------------------------------------------------------------------------
# Status filter modal
# ---------------------------------------------------------------------------

_STATUS_CHOICES: list[tuple[str, str]] = [
    ("Open", "open"),
    ("In Progress", "in_progress"),
    ("Blocked", "blocked"),
    ("Deferred", "deferred"),
    ("Closed", "closed"),
]

_DEFAULT_STATUSES: frozenset[str] = frozenset({"open", "in_progress"})

_ABBREV: dict[str, str] = {
    "open": "Open",
    "in_progress": "In Prog",
    "blocked": "Blocked",
    "deferred": "Deferred",
    "closed": "Closed",
}


def _status_button_label(statuses: set[str]) -> str:
    """Build a short label summarising the selected statuses."""
    if len(statuses) == len(_STATUS_CHOICES):
        return "All Statuses"
    if not statuses:
        return "None"
    ordered = [v for _, v in _STATUS_CHOICES if v in statuses]
    return ", ".join(_ABBREV.get(s, s) for s in ordered)


class StatusFilterModal(ModalScreen[set[str] | None]):
    """Modal with checkboxes for picking one or more statuses."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    StatusFilterModal {
        align: center middle;
    }
    StatusFilterModal > #status-modal {
        width: 40;
        max-width: 90%;
        height: auto;
        max-height: 70%;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }
    StatusFilterModal > #status-modal > #status-modal-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        margin-bottom: 1;
    }
    StatusFilterModal > #status-modal > #status-modal-buttons {
        width: 100%;
        height: auto;
        align-horizontal: center;
        margin-top: 1;
    }
    StatusFilterModal > #status-modal > #status-modal-buttons Button {
        margin: 0 1;
        min-width: 10;
    }
    """

    def __init__(self, current: set[str]) -> None:
        super().__init__()
        self._current = set(current)

    def compose(self) -> ComposeResult:
        with Vertical(id="status-modal"):
            yield Label("Status Filter", id="status-modal-title")
            for label, value in _STATUS_CHOICES:
                yield Checkbox(label, value=(value in self._current), id=f"status-chk-{value}")
            with Horizontal(id="status-modal-buttons"):
                yield Button("All", id="status-all-btn")
                yield Button("None", id="status-none-btn")
                yield Button("Apply", variant="primary", id="status-apply-btn")
                yield Button("Cancel", id="status-cancel-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "status-all-btn":
            for _, value in _STATUS_CHOICES:
                self.query_one(f"#status-chk-{value}", Checkbox).value = True
        elif bid == "status-none-btn":
            for _, value in _STATUS_CHOICES:
                self.query_one(f"#status-chk-{value}", Checkbox).value = False
        elif bid == "status-apply-btn":
            selected: set[str] = set()
            for _, value in _STATUS_CHOICES:
                if self.query_one(f"#status-chk-{value}", Checkbox).value:
                    selected.add(value)
            self.dismiss(selected)
        elif bid == "status-cancel-btn":
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Filter bar
# ---------------------------------------------------------------------------

class FilterBar(Widget):
    """Search and filter bar for issue list.

    Layout:
        [search text here___________] | [Status: Open, In Prog] | Priority: [All] | Type: [All] | Clear
    """

    DEFAULT_CSS = """
    FilterBar {
        dock: top;
        height: 5;
        padding: 0 1;
    }

    FilterBar #filter-bar {
        height: 100%;
        width: 100%;
    }

    FilterBar #search-input {
        width: 1fr;
        min-width: 20;
        height: 3;
    }

    FilterBar Select {
        width: 18;
        height: 3;
        margin: 0 0 0 1;
        border: none;
    }

    FilterBar #status-filter-btn {
        min-width: 18;
        max-width: 30;
        height: 3;
        margin: 0 0 0 1;
        background: #282840;
        color: #cdd6f4;
        border: none;
        text-align: center;
        content-align: center middle;
    }

    FilterBar #status-filter-btn:hover {
        background: #333350;
    }

    FilterBar #clear-filters {
        min-width: 10;
        height: 3;
        border: solid #44447a;
        margin: 0 0 0 1;
        content-align: center middle;
        text-align: center;
    }
    """

    class FiltersChanged(Message):
        """Posted when any filter value changes."""

        def __init__(
            self,
            search: str,
            statuses: set[str] | None,
            priority: str | None,
            type_: str | None,
        ) -> None:
            super().__init__()
            self.search = search
            self.statuses = statuses
            self.priority = priority
            self.type_ = type_

    _search_timer: Timer
    _selected_statuses: set[str]

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
        self._selected_statuses = set(_DEFAULT_STATUSES)
        with Horizontal(id="filter-bar"):
            yield Input(placeholder="Search issues...", id="search-input")
            yield Button(
                _status_button_label(self._selected_statuses),
                id="status-filter-btn",
                variant="default",
            )
            yield Select(
                [(text, val) for text, val in self.PRIORITY_OPTIONS],
                id="priority-filter",
                prompt="Priority",
                value="",
            )
            yield Select(
                [(text, val) for text, val in self.TYPE_OPTIONS],
                id="type-filter",
                prompt="Type",
                value="",
            )
            yield Button("Clear", id="clear-filters", variant="default")

    def on_mount(self) -> None:
        self._search_timer = self.set_interval(
            0.3, self._on_search_timer, pause=True
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self._search_timer.reset()
            self._search_timer.resume()

    def on_select_changed(self, event: Select.Changed) -> None:
        self._post_filters_changed()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "clear-filters":
            self.clear_all()
        elif event.button.id == "status-filter-btn":
            self._open_status_modal()

    def _open_status_modal(self) -> None:
        def _on_dismiss(result: set[str] | None) -> None:
            if result is not None:
                self._selected_statuses = result
                self.query_one("#status-filter-btn", Button).label = _status_button_label(result)
                self._post_filters_changed()

        self.app.push_screen(StatusFilterModal(self._selected_statuses), callback=_on_dismiss)

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
                statuses=filters["statuses"],
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

    def set_statuses(self, statuses: set[str]) -> None:
        """Programmatically set the status filter (e.g. from the A toggle)."""
        self._selected_statuses = set(statuses)
        self.query_one("#status-filter-btn", Button).label = _status_button_label(statuses)
        self._post_filters_changed()

    def clear_all(self) -> None:
        """Reset all filters to their defaults and post FiltersChanged."""
        self.query_one("#search-input", Input).value = ""
        self._selected_statuses = set(_DEFAULT_STATUSES)
        self.query_one("#status-filter-btn", Button).label = _status_button_label(self._selected_statuses)
        self.query_one("#priority-filter", Select).value = ""
        self.query_one("#type-filter", Select).value = ""
        self._post_filters_changed()

    def get_filters(self) -> dict:
        """Return the current filter state.

        Returns a dict with keys: search, statuses, priority, type.
        statuses is a set[str] (may be empty meaning none selected).
        priority and type are None when set to "All".
        """
        search_val = self.query_one("#search-input", Input).value.strip()
        priority_val = self.query_one("#priority-filter", Select).value
        type_val = self.query_one("#type-filter", Select).value

        # If all statuses are selected, return None meaning "show all"
        all_selected = len(self._selected_statuses) == len(_STATUS_CHOICES)
        statuses: set[str] | None = None if all_selected else set(self._selected_statuses)

        return {
            "search": search_val or None,
            "statuses": statuses,
            "priority": priority_val or None,
            "type": type_val or None,
        }
