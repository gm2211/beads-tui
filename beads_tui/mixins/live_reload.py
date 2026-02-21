"""Live reload mixin — file-watch driven refresh with fallback poll."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual.timer import Timer


def _snapshot_mtimes(watch_path: Path) -> dict[str, float]:
    """Return mtime of every file under *watch_path* (full recursive walk).

    Typically only ~20 files so the walk is negligible even at 1 Hz.
    """
    mtimes: dict[str, float] = {}
    root = str(watch_path)
    try:
        for dirpath, _dirnames, filenames in os.walk(root):
            for fn in filenames:
                p = os.path.join(dirpath, fn)
                try:
                    mtimes[p] = os.stat(p).st_mtime
                except OSError:
                    pass
    except OSError:
        pass
    return mtimes


class LiveReloadMixin:
    """Mixin that adds file-watch-driven data refresh to a Textual App.

    Set ``WATCH_PATH`` to a :class:`~pathlib.Path` pointing at the ``.beads/``
    directory before calling :meth:`start_live_reload`.  The mixin will poll
    file mtimes under that directory every ``WATCH_INTERVAL`` seconds (cheap
    ``os.walk`` — no subprocess) and call :meth:`_on_change_detected` when
    something changed.

    A fallback refresh runs every ``FALLBACK_INTERVAL`` seconds as a safety
    net (e.g. if the database lives outside the watched directory).

    Subclasses must override :meth:`_on_change_detected` to perform the
    actual data reload.
    """

    WATCH_PATH: Path | None = None
    WATCH_INTERVAL: float = 1.0      # seconds between mtime checks
    FALLBACK_INTERVAL: float = 30.0  # safety-net full refresh

    _refresh_paused: bool = False
    _watch_timer: Timer | None = None
    _fallback_timer: Timer | None = None
    _last_mtimes: dict[str, float] = {}

    def start_live_reload(self) -> None:
        """Start the file watcher and fallback poll timers."""
        if self.WATCH_PATH is not None:
            self._last_mtimes = _snapshot_mtimes(self.WATCH_PATH)
            self._watch_timer = self.set_interval(  # type: ignore[attr-defined]
                self.WATCH_INTERVAL,
                self._check_files,
                name="live-reload-watch",
            )
        # Always run the fallback poll (covers non-filesystem changes
        # and acts as the sole mechanism if WATCH_PATH is unset).
        self._fallback_timer = self.set_interval(  # type: ignore[attr-defined]
            self.FALLBACK_INTERVAL if self.WATCH_PATH else 5.0,
            self._do_fallback,
            name="live-reload-fallback",
        )

    def stop_live_reload(self) -> None:
        """Stop all live-reload timers."""
        if self._watch_timer is not None:
            self._watch_timer.stop()
            self._watch_timer = None
        if self._fallback_timer is not None:
            self._fallback_timer.stop()
            self._fallback_timer = None

    def pause_refresh(self) -> None:
        """Pause refresh (e.g. when the user is editing)."""
        self._refresh_paused = True

    def resume_refresh(self) -> None:
        """Resume refresh after editing."""
        self._refresh_paused = False

    async def _check_files(self) -> None:
        """Compare mtimes; trigger refresh only if files changed."""
        if self._refresh_paused or self.WATCH_PATH is None:
            return
        curr = _snapshot_mtimes(self.WATCH_PATH)
        if curr != self._last_mtimes:
            self._last_mtimes = curr
            self._on_change_detected()

    async def _do_fallback(self) -> None:
        """Unconditional refresh (fallback timer)."""
        if self._refresh_paused:
            return
        if self.WATCH_PATH is not None:
            self._last_mtimes = _snapshot_mtimes(self.WATCH_PATH)
        self._on_change_detected()

    def _on_change_detected(self) -> None:
        """Called when a change is detected.  Subclasses must override."""
        raise NotImplementedError("Subclass must implement _on_change_detected()")
