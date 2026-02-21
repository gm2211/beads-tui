"""Search and filter bar widget for the issue list."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Click
from textual.message import Message
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Button, Checkbox, Input, Label, OptionList
from textual.widgets.option_list import Option


# ---------------------------------------------------------------------------
# Generic single-select picker modal
# ---------------------------------------------------------------------------

class SinglePickerModal(ModalScreen[str | None]):
    """Modal that lets the user pick one value from a list."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    SinglePickerModal {
        align: center middle;
    }
    """

    def __init__(self, title: str, options: list[tuple[str, str]], current: str) -> None:
        super().__init__()
        self._title = title
        self._options = options  # (label, value) pairs
        self._current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-modal"):
            yield Label(self._title, id="picker-modal-title")
            ol = OptionList(id="picker-options")
            for label, value in self._options:
                display = f"{label}  \u2713" if value == self._current else label
                ol.add_option(Option(display, id=value))
            yield ol
            with Horizontal(id="picker-modal-buttons"):
                yield Button("Cancel", id="picker-cancel-btn")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.id))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "picker-cancel-btn":
            self.dismiss(None)

    def on_click(self, event: Click) -> None:
        if self is event.widget:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Status filter modal (multi-select)
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

    def on_click(self, event: Click) -> None:
        if self is event.widget:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Filter bar
# ---------------------------------------------------------------------------

_PRIORITY_OPTIONS: list[tuple[str, str]] = [
    ("All Priorities", ""),
    ("P0 Critical", "0"),
    ("P1 High", "1"),
    ("P2 Normal", "2"),
    ("P3 Low", "3"),
    ("P4 Backlog", "4"),
]

_PRIORITY_LABELS: dict[str, str] = {v: l for l, v in _PRIORITY_OPTIONS}

_TYPE_OPTIONS: list[tuple[str, str]] = [
    ("All Types", ""),
    ("Task", "task"),
    ("Bug", "bug"),
    ("Feature", "feature"),
    ("Epic", "epic"),
    ("Chore", "chore"),
]

_TYPE_LABELS: dict[str, str] = {v: l for l, v in _TYPE_OPTIONS}


class FilterBar(Widget):
    """Search and filter bar for issue list.

    Layout:
        [search text here___________] | [Status] | [Priority] | [Type] | Clear
    """

    DEFAULT_CSS = """
    FilterBar {
        dock: top;
        height: auto;
        padding: 0 1;
    }

    FilterBar #filter-bar {
        height: auto;
        width: 100%;
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
    _selected_priority: str  # "" = All
    _selected_type: str  # "" = All

    def compose(self) -> ComposeResult:
        self._selected_statuses = set(_DEFAULT_STATUSES)
        self._selected_priority = ""
        self._selected_type = ""
        with Horizontal(id="filter-bar"):
            yield Input(placeholder="Search issues...", id="search-input")
            yield Button(
                _status_button_label(self._selected_statuses),
                id="status-filter-btn",
                classes="filter-btn",
            )
            yield Button(
                "All Priorities",
                id="priority-filter-btn",
                classes="filter-btn",
            )
            yield Button(
                "All Types",
                id="type-filter-btn",
                classes="filter-btn",
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

    def on_key(self, event) -> None:
        """Handle Escape to unfocus search bar."""
        if event.key == "escape":
            focused = self.screen.focused
            if focused is not None and focused.id == "search-input":
                try:
                    self.screen.query_one("#issue-table").focus()
                except Exception:
                    self.screen.focus_next()
                event.stop()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "clear-filters":
            self.clear_all()
        elif bid == "status-filter-btn":
            self._open_status_modal()
        elif bid == "priority-filter-btn":
            self._open_priority_modal()
        elif bid == "type-filter-btn":
            self._open_type_modal()

    # ------------------------------------------------------------------
    # Modal openers
    # ------------------------------------------------------------------

    def _open_status_modal(self) -> None:
        def _on_dismiss(result: set[str] | None) -> None:
            if result is not None:
                self._selected_statuses = result
                self.query_one("#status-filter-btn", Button).label = _status_button_label(result)
                self._post_filters_changed()

        self.app.push_screen(StatusFilterModal(self._selected_statuses), callback=_on_dismiss)

    def _open_priority_modal(self) -> None:
        def _on_dismiss(result: str | None) -> None:
            if result is not None:
                self._selected_priority = result
                self.query_one("#priority-filter-btn", Button).label = _PRIORITY_LABELS.get(result, "All Priorities")
                self._post_filters_changed()

        self.app.push_screen(
            SinglePickerModal("Priority", _PRIORITY_OPTIONS, self._selected_priority),
            callback=_on_dismiss,
        )

    def _open_type_modal(self) -> None:
        def _on_dismiss(result: str | None) -> None:
            if result is not None:
                self._selected_type = result
                self.query_one("#type-filter-btn", Button).label = _TYPE_LABELS.get(result, "All Types")
                self._post_filters_changed()

        self.app.push_screen(
            SinglePickerModal("Type", _TYPE_OPTIONS, self._selected_type),
            callback=_on_dismiss,
        )

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
        self._selected_priority = ""
        self._selected_type = ""
        self.query_one("#status-filter-btn", Button).label = _status_button_label(self._selected_statuses)
        self.query_one("#priority-filter-btn", Button).label = "All Priorities"
        self.query_one("#type-filter-btn", Button).label = "All Types"
        self._post_filters_changed()

    def get_filters(self) -> dict:
        """Return the current filter state.

        Returns a dict with keys: search, statuses, priority, type.
        statuses is a set[str] (may be empty meaning none selected).
        priority and type are None when set to "All".
        """
        search_val = self.query_one("#search-input", Input).value.strip()

        # If all statuses are selected, return None meaning "show all"
        all_selected = len(self._selected_statuses) == len(_STATUS_CHOICES)
        statuses: set[str] | None = None if all_selected else set(self._selected_statuses)

        return {
            "search": search_val or None,
            "statuses": statuses,
            "priority": self._selected_priority or None,
            "type": self._selected_type or None,
        }
