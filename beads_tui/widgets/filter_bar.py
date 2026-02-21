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
from textual.widgets import Button, Checkbox, Input, Label


# ---------------------------------------------------------------------------
# Generic checkbox filter modal (multi-select)
# ---------------------------------------------------------------------------

class CheckboxFilterModal(ModalScreen[set[str] | None]):
    """Modal with checkboxes for picking one or more values."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("j", "next_item", "Down", show=False),
        Binding("k", "prev_item", "Up", show=False),
        Binding("down", "next_item", "Down", show=False),
        Binding("up", "prev_item", "Up", show=False),
        Binding("l", "next_item", "Right", show=False),
        Binding("h", "prev_item", "Left", show=False),
        Binding("right", "next_item", "Right", show=False),
        Binding("left", "prev_item", "Left", show=False),
    ]

    DEFAULT_CSS = """
    CheckboxFilterModal {
        align: center middle;
    }
    """

    def __init__(self, title: str, choices: list[tuple[str, str]], current: set[str]) -> None:
        super().__init__()
        self._title = title
        self._choices = choices
        self._current = set(current)

    def compose(self) -> ComposeResult:
        with Vertical(id="status-modal"):
            yield Label(self._title, id="status-modal-title")
            for label, value in self._choices:
                yield Checkbox(label, value=(value in self._current), id=f"chk-{value}")
            with Horizontal(id="status-modal-buttons"):
                yield Button("All", id="status-all-btn")
                yield Button("None", id="status-none-btn")
                yield Button("Apply", id="status-apply-btn")
                yield Button("Cancel", id="status-cancel-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "status-all-btn":
            for _, value in self._choices:
                self.query_one(f"#chk-{value}", Checkbox).value = True
        elif bid == "status-none-btn":
            for _, value in self._choices:
                self.query_one(f"#chk-{value}", Checkbox).value = False
        elif bid == "status-apply-btn":
            selected: set[str] = set()
            for _, value in self._choices:
                if self.query_one(f"#chk-{value}", Checkbox).value:
                    selected.add(value)
            self.dismiss(selected)
        elif bid == "status-cancel-btn":
            self.dismiss(None)

    def _focusable_items(self) -> list:
        items: list = []
        for _, value in self._choices:
            items.append(self.query_one(f"#chk-{value}", Checkbox))
        for btn in self.query("#status-modal-buttons Button"):
            items.append(btn)
        return items

    def action_next_item(self) -> None:
        items = self._focusable_items()
        if not items:
            return
        try:
            idx = items.index(self.focused)
            items[(idx + 1) % len(items)].focus()
        except (ValueError, TypeError):
            items[0].focus()

    def action_prev_item(self) -> None:
        items = self._focusable_items()
        if not items:
            return
        try:
            idx = items.index(self.focused)
            items[(idx - 1) % len(items)].focus()
        except (ValueError, TypeError):
            items[-1].focus()

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


class StatusFilterModal(CheckboxFilterModal):
    """Convenience wrapper for status multi-select."""

    def __init__(self, current: set[str]) -> None:
        super().__init__("Status Filter", _STATUS_CHOICES, current)


# ---------------------------------------------------------------------------
# Filter bar
# ---------------------------------------------------------------------------

_PRIORITY_CHOICES: list[tuple[str, str]] = [
    ("P0 Critical", "0"),
    ("P1 High", "1"),
    ("P2 Normal", "2"),
    ("P3 Low", "3"),
    ("P4 Backlog", "4"),
]

_DEFAULT_PRIORITIES: frozenset[str] = frozenset(v for _, v in _PRIORITY_CHOICES)

_TYPE_CHOICES: list[tuple[str, str]] = [
    ("Task", "task"),
    ("Bug", "bug"),
    ("Feature", "feature"),
    ("Epic", "epic"),
    ("Chore", "chore"),
]

_DEFAULT_TYPES: frozenset[str] = frozenset(v for _, v in _TYPE_CHOICES)


def _priority_button_label(priorities: set[str]) -> str:
    if len(priorities) == len(_PRIORITY_CHOICES):
        return "All Priorities"
    if not priorities:
        return "No Priority"
    ordered = [v for _, v in _PRIORITY_CHOICES if v in priorities]
    return ", ".join(f"P{p}" for p in ordered)


def _type_button_label(types: set[str]) -> str:
    if len(types) == len(_TYPE_CHOICES):
        return "All Types"
    if not types:
        return "No Type"
    ordered = [v for _, v in _TYPE_CHOICES if v in types]
    return ", ".join(t.title() for t in ordered)


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
            priorities: set[str] | None,
            types: set[str] | None,
        ) -> None:
            super().__init__()
            self.search = search
            self.statuses = statuses
            self.priorities = priorities
            self.types = types

    _search_timer: Timer
    _selected_statuses: set[str]
    _selected_priorities: set[str]
    _selected_types: set[str]

    def compose(self) -> ComposeResult:
        self._selected_statuses = set(_DEFAULT_STATUSES)
        self._selected_priorities = set(_DEFAULT_PRIORITIES)
        self._selected_types = set(_DEFAULT_TYPES)
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
        def _on_dismiss(result: set[str] | None) -> None:
            if result is not None:
                self._selected_priorities = result
                self.query_one("#priority-filter-btn", Button).label = _priority_button_label(result)
                self._post_filters_changed()

        self.app.push_screen(
            CheckboxFilterModal("Priority Filter", _PRIORITY_CHOICES, self._selected_priorities),
            callback=_on_dismiss,
        )

    def _open_type_modal(self) -> None:
        def _on_dismiss(result: set[str] | None) -> None:
            if result is not None:
                self._selected_types = result
                self.query_one("#type-filter-btn", Button).label = _type_button_label(result)
                self._post_filters_changed()

        self.app.push_screen(
            CheckboxFilterModal("Type Filter", _TYPE_CHOICES, self._selected_types),
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
                priorities=filters["priorities"],
                types=filters["types"],
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
        self._selected_priorities = set(_DEFAULT_PRIORITIES)
        self._selected_types = set(_DEFAULT_TYPES)
        self.query_one("#status-filter-btn", Button).label = _status_button_label(self._selected_statuses)
        self.query_one("#priority-filter-btn", Button).label = "All Priorities"
        self.query_one("#type-filter-btn", Button).label = "All Types"
        self._post_filters_changed()

    def get_filters(self) -> dict:
        """Return the current filter state.

        Returns a dict with keys: search, statuses, priorities, types.
        Set values are None when all options are selected (meaning "show all").
        """
        search_val = self.query_one("#search-input", Input).value.strip()

        all_statuses = len(self._selected_statuses) == len(_STATUS_CHOICES)
        statuses: set[str] | None = None if all_statuses else set(self._selected_statuses)

        all_pri = len(self._selected_priorities) == len(_PRIORITY_CHOICES)
        priorities: set[str] | None = None if all_pri else set(self._selected_priorities)

        all_types = len(self._selected_types) == len(_TYPE_CHOICES)
        types: set[str] | None = None if all_types else set(self._selected_types)

        return {
            "search": search_val or None,
            "statuses": statuses,
            "priorities": priorities,
            "types": types,
        }
