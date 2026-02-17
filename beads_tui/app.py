"""Main Textual application."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header
from textual import work
from textual import on
from rich.text import Text

from .bd_client import BdClient, BdError
from .models import Issue


# Map priority int to (label, Rich style)
_PRIORITY_STYLES: dict[int, tuple[str, str]] = {
    0: ("P0", "bold red"),
    1: ("P1", "dark_orange"),
    2: ("P2", "yellow"),
    3: ("P3", "dodger_blue"),
    4: ("P4", "dim"),
}

# Map status string to display symbol
_STATUS_SYMBOLS: dict[str, str] = {
    "open": "\u25cb",          # ○
    "in_progress": "\u25d0",   # ◐
    "blocked": "\u25cf",       # ●
    "deferred": "\u2744",      # ❄
    "closed": "\u2713",        # ✓
}


def _styled(value: str, style: str) -> Text:
    """Return a Rich Text with the given style."""
    return Text(value, style=style)


def _priority_cell(priority: int) -> Text:
    label, style = _PRIORITY_STYLES.get(priority, ("P?", ""))
    return _styled(label, style)


def _status_cell(status: str) -> Text:
    symbol = _STATUS_SYMBOLS.get(status, status)
    style_map = {
        "open": "green",
        "in_progress": "cyan",
        "blocked": "bold red",
        "deferred": "blue",
        "closed": "dim",
    }
    return _styled(symbol, style_map.get(status, ""))


def _title_cell(title: str, priority: int) -> Text:
    _, style = _PRIORITY_STYLES.get(priority, ("", ""))
    return _styled(title, style)


def _short_date(dt: str) -> str:
    """Extract YYYY-MM-DD from an ISO datetime string."""
    if not dt:
        return ""
    return dt[:10]


class BeadsTuiApp(App):
    """Interactive TUI for beads (bd) issue tracker."""

    TITLE = "Beads TUI"
    CSS_PATH = "styles/app.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("question_mark", "help", "Help", key_display="?"),
        Binding("c", "create", "Create"),
        Binding("slash", "search", "Search", key_display="/"),
        Binding("r", "refresh", "Refresh"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "select_issue", "Open", show=False),
    ]

    def __init__(self, bd_path: str | None = None, db_path: str | None = None):
        super().__init__()
        self._bd_path = bd_path
        self._db_path = db_path
        self.client: BdClient | None = None
        self._issues: list[Issue] = []

    def compose(self) -> ComposeResult:
        yield Header()
        table = DataTable(id="issue-table", cursor_type="row")
        table.add_columns("ID", "P", "Status", "Type", "Title", "Assignee", "Updated")
        yield table
        yield Footer()

    def on_mount(self) -> None:
        try:
            self.client = BdClient(bd_path=self._bd_path, db_path=self._db_path)
        except BdError:
            self.client = None
        self._load_issues()

    @work(exclusive=True)
    async def _load_issues(self) -> None:
        """Fetch issues in a worker and populate the table."""
        if self.client is None:
            return
        try:
            issues = await self.client.list_issues(all_=True)
        except BdError:
            issues = []
        self._issues = issues
        self._populate_table()

    def _populate_table(self) -> None:
        table = self.query_one("#issue-table", DataTable)
        table.clear()
        for issue in self._issues:
            table.add_row(
                _styled(issue.id, "bold"),
                _priority_cell(issue.priority),
                _status_cell(issue.status),
                issue.issue_type or "",
                _title_cell(issue.title, issue.priority),
                issue.owner or issue.assignee or "",
                _short_date(issue.updated_at),
                key=issue.id,
            )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_cursor_down(self) -> None:
        table = self.query_one("#issue-table", DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        table = self.query_one("#issue-table", DataTable)
        table.action_cursor_up()

    def action_refresh(self) -> None:
        self._load_issues()

    def action_select_issue(self) -> None:
        table = self.query_one("#issue-table", DataTable)
        if table.row_count == 0:
            return
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        issue_id = str(row_key)
        if not issue_id:
            return
        from .screens.detail_screen import DetailScreen
        self.push_screen(DetailScreen(issue_id))

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        issue_id = str(event.row_key.value)
        if not issue_id:
            return
        from .screens.detail_screen import DetailScreen
        self.push_screen(DetailScreen(issue_id))

    def action_help(self) -> None:
        self.notify(
            "q=Quit  r=Refresh  c=Create  /=Search  Enter=Open  j/k=Navigate",
            title="Keybindings",
        )

    def action_create(self) -> None:
        self.notify("Create issue: not yet implemented", title="TODO")

    def action_search(self) -> None:
        self.notify("Search: not yet implemented", title="TODO")
