"""Live reload mixin for periodic data refresh with zero flicker."""

from __future__ import annotations

from typing import TYPE_CHECKING

from beads_tui.models import Issue

if TYPE_CHECKING:
    from textual.timer import Timer


def diff_issues(
    old: list[Issue], new: list[Issue]
) -> tuple[list[Issue], list[Issue], list[str]]:
    """Compare two issue lists and return the differences.

    Returns a tuple of (added, changed, removed_ids) where:
    - added: issues present in *new* but not in *old*
    - changed: issues present in both but with a different updated_at
    - removed_ids: IDs present in *old* but missing from *new*
    """
    old_map: dict[str, Issue] = {issue.id: issue for issue in old}
    new_map: dict[str, Issue] = {issue.id: issue for issue in new}

    added: list[Issue] = []
    changed: list[Issue] = []

    for issue_id, issue in new_map.items():
        if issue_id not in old_map:
            added.append(issue)
        elif issue.updated_at != old_map[issue_id].updated_at:
            changed.append(issue)

    removed_ids = [iid for iid in old_map if iid not in new_map]

    return added, changed, removed_ids


class LiveReloadMixin:
    """Mixin that adds periodic data refresh to a Textual App.

    The host class must be a ``textual.app.App`` (or subclass) so that
    ``self.set_interval`` and ``self.call_later`` are available.

    Subclasses should override ``refresh_data`` to perform the actual data
    fetch and diff/update cycle.
    """

    REFRESH_INTERVAL: float = 5.0  # seconds

    _refresh_paused: bool = False
    _refresh_timer: Timer | None = None

    def start_live_reload(self) -> None:
        """Start the periodic refresh timer."""
        self._refresh_timer = self.set_interval(  # type: ignore[attr-defined]
            self.REFRESH_INTERVAL,
            self._do_refresh,
            name="live-reload",
        )

    def stop_live_reload(self) -> None:
        """Stop the periodic refresh timer."""
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
            self._refresh_timer = None

    def pause_refresh(self) -> None:
        """Pause refresh (e.g. when the user is editing)."""
        self._refresh_paused = True

    def resume_refresh(self) -> None:
        """Resume refresh after editing."""
        self._refresh_paused = False

    async def _do_refresh(self) -> None:
        """Called periodically by the timer."""
        if self._refresh_paused:
            return
        await self.refresh_data()

    async def refresh_data(self) -> None:
        """Override in app to reload data.

        Implementations should:
        1. Fetch fresh data via ``BdClient``
        2. Use ``diff_issues`` to find what changed
        3. Only update the rows that actually changed
        4. Never clear/rebuild the entire table
        5. Preserve scroll and cursor position
        """
        raise NotImplementedError("Subclass must implement refresh_data()")
