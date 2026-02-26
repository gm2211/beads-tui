"""Worktree picker modal screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option


class WorktreePicker(ModalScreen[str | None]):
    """Modal screen to pick a git worktree to switch to.

    Dismisses with the selected worktree path, or None if cancelled.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    WorktreePicker {
        align: center middle;
    }

    WorktreePicker > #worktree-dialog {
        width: 70;
        max-width: 90%;
        height: auto;
        max-height: 70%;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }

    WorktreePicker > #worktree-dialog > #worktree-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        margin-bottom: 1;
    }

    WorktreePicker > #worktree-dialog > #worktree-hint {
        text-align: center;
        color: $text-muted;
        width: 100%;
        margin-top: 1;
    }
    """

    def __init__(self, worktrees: list[dict], current_path: str) -> None:
        """
        Args:
            worktrees: List of dicts with keys: name, path, branch, is_current
            current_path: Path of the currently active worktree
        """
        super().__init__()
        self._worktrees = worktrees
        self._current_path = current_path

    def compose(self) -> ComposeResult:
        with Vertical(id="worktree-dialog"):
            yield Label("Switch Worktree", id="worktree-title")
            option_list = OptionList(id="worktree-options")
            for wt in self._worktrees:
                label = self._make_label(wt)
                option_list.add_option(Option(label, id=wt["path"]))
            yield option_list
            yield Static("[dim]Enter to select • Escape to cancel[/dim]", id="worktree-hint")

    def _make_label(self, wt: dict) -> str:
        name = wt.get("name", "")
        path = wt.get("path", "")
        is_current = wt.get("is_current", False)

        marker = "* " if is_current else "  "
        return f"{marker}{name}  {path}"

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        selected_path = str(event.option.id)
        self.dismiss(selected_path)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_click(self, event) -> None:
        if self is event.widget:
            self.dismiss(None)
