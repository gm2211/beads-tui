"""Live reload mixin for file-watch + fallback-poll data refresh with zero flicker."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from beads_tui.models import Issue

if TYPE_CHECKING:
    from textual.timer import Timer

try:
    from watchfiles import awatch as _awatch
    _WATCHFILES_AVAILABLE = True
except ImportError:
    _WATCHFILES_AVAILABLE = False


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
    """Mixin that adds file-watch + fallback-poll data refresh to a Textual App.

    The host class must be a ``textual.app.App`` (or subclass) so that
    ``self.set_interval`` and ``self.call_later`` are available.

    Class attributes
    ----------------
    WATCH_PATH : str | Path | None
        Directory to watch with ``watchfiles``.  Set this on the concrete app
        class.  When ``None`` (or when watchfiles is not installed) the mixin
        falls back to polling every ``REFRESH_INTERVAL`` seconds.
    REFRESH_INTERVAL : float
        Polling interval (seconds) used when watchfiles is unavailable.
        Default: 3.0.
    FALLBACK_INTERVAL : float
        Safety-net fallback poll interval (seconds) used alongside the file
        watcher to catch any missed events.  Default: 30.0.
    DEBOUNCE_DELAY : float
        Seconds to wait after the first file-change event before triggering a
        refresh, so that a burst of rapid writes causes only one refresh.
        Default: 0.5.

    Subclasses should override ``refresh_data`` to perform the actual data
    fetch and diff/update cycle.
    """

    WATCH_PATH: str | Path | None = None
    REFRESH_INTERVAL: float = 3.0       # seconds — used in polling-only fallback
    FALLBACK_INTERVAL: float = 30.0     # seconds — safety-net alongside watcher
    DEBOUNCE_DELAY: float = 0.5         # seconds

    _refresh_paused: bool = False
    _refresh_timer: Timer | None = None
    _watcher_task: asyncio.Task | None = None  # type: ignore[type-arg]
    _debounce_handle: asyncio.TimerHandle | None = None

    # ------------------------------------------------------------------
    # Public control API
    # ------------------------------------------------------------------

    def start_live_reload(self) -> None:
        """Start the file-watcher task and/or the fallback timer."""
        watch_path = self._resolve_watch_path()

        if _WATCHFILES_AVAILABLE and watch_path is not None:
            # Launch the async file-watcher as a background task.
            self._watcher_task = asyncio.get_event_loop().create_task(
                self._run_file_watcher(watch_path),
                name="live-reload-watcher",
            )
            # Start safety-net fallback timer at a slow interval.
            self._refresh_timer = self.set_interval(  # type: ignore[attr-defined]
                self.FALLBACK_INTERVAL,
                self._do_refresh,
                name="live-reload-fallback",
            )
        else:
            # watchfiles unavailable or no path configured — fall back to polling.
            self._refresh_timer = self.set_interval(  # type: ignore[attr-defined]
                self.REFRESH_INTERVAL,
                self._do_refresh,
                name="live-reload",
            )

    def stop_live_reload(self) -> None:
        """Cancel the file-watcher task and stop the fallback timer."""
        if self._watcher_task is not None:
            self._watcher_task.cancel()
            self._watcher_task = None
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
            self._refresh_timer = None
        if self._debounce_handle is not None:
            self._debounce_handle.cancel()
            self._debounce_handle = None

    def pause_refresh(self) -> None:
        """Pause refresh (e.g. when the user is editing)."""
        self._refresh_paused = True

    def resume_refresh(self) -> None:
        """Resume refresh after editing."""
        self._refresh_paused = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_watch_path(self) -> Path | None:
        """Return the resolved watch path, or None if not configured."""
        wp = self.WATCH_PATH  # type: ignore[attr-defined]
        if wp is None:
            return None
        p = Path(wp)
        if not p.exists():
            return None
        return p

    async def _run_file_watcher(self, watch_path: Path) -> None:
        """Async task: watch *watch_path* and schedule debounced refreshes."""
        try:
            async for _changes in _awatch(watch_path):
                if self._refresh_paused:
                    continue
                self._schedule_debounced_refresh()
        except asyncio.CancelledError:
            pass

    def _schedule_debounced_refresh(self) -> None:
        """Cancel any pending debounce handle and reschedule."""
        if self._debounce_handle is not None:
            self._debounce_handle.cancel()
        loop = asyncio.get_event_loop()
        self._debounce_handle = loop.call_later(
            self.DEBOUNCE_DELAY,
            self._fire_refresh_from_watcher,
        )

    def _fire_refresh_from_watcher(self) -> None:
        """Synchronous callback from call_later; schedules the async refresh."""
        self._debounce_handle = None
        asyncio.get_event_loop().create_task(self._do_refresh())

    async def _do_refresh(self) -> None:
        """Trigger a data refresh, unless paused."""
        if self._refresh_paused:
            return
        await self.refresh_data()  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Subclass contract
    # ------------------------------------------------------------------

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
