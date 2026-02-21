"""Live reload mixin — file-watch driven refresh with fallback poll."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual.timer import Timer

# Dolt noms files that change on EVERY bd operation (reads AND writes).
# We exclude these from change detection to avoid false positives when
# the TUI itself runs ``bd list``.
_NOMS_EPHEMERAL = frozenset({"journal.idx", "manifest", "LOCK"})


def _find_write_markers(watch_path: Path) -> dict[str, float]:
    """Return a snapshot of write-only indicators under *watch_path*.

    Dolt's embedded noms storage modifies ``journal.idx``, ``manifest``,
    and the data blob on *every* operation — including reads.  However,
    only **write** operations (create/update/close) **grow** the data
    blob; reads leave its size unchanged.

    Strategy:
    - Noms data files (the ``vvvv…`` blob): track **size** (grows on writes).
    - ``last-touched``: track **mtime** (updated by ``bd create``).
    - ``issues.jsonl``: track **mtime** (updated by ``bd sync``).
    """
    snapshot: dict[str, float] = {}
    root = str(watch_path)
    noms_marker = os.sep + "noms"
    try:
        for dirpath, _dirnames, filenames in os.walk(root):
            is_noms = dirpath.endswith(noms_marker) or (noms_marker + os.sep) in dirpath
            for fn in filenames:
                if fn in ("last-touched", "issues.jsonl"):
                    p = os.path.join(dirpath, fn)
                    try:
                        snapshot[p] = os.stat(p).st_mtime
                    except OSError:
                        pass
                elif is_noms and fn not in _NOMS_EPHEMERAL:
                    # Noms data blob — only grows on writes
                    p = os.path.join(dirpath, fn)
                    try:
                        snapshot[p] = float(os.stat(p).st_size)
                    except OSError:
                        pass
    except OSError:
        pass
    return snapshot


class LiveReloadMixin:
    """Mixin that adds file-watch-driven data refresh to a Textual App.

    Set ``WATCH_PATH`` to a :class:`~pathlib.Path` pointing at the ``.beads/``
    directory before calling :meth:`start_live_reload`.  The mixin tracks
    the **size** of the Dolt noms data blob (which only grows on writes)
    and the **mtime** of ``last-touched`` / ``issues.jsonl``.  This avoids
    false reloads from ``bd list`` which touches mtimes but doesn't grow
    files.

    A fallback refresh runs every ``FALLBACK_INTERVAL`` seconds as a safety
    net.

    Subclasses must override :meth:`_on_change_detected` to perform the
    actual data reload.
    """

    WATCH_PATH: Path | None = None
    WATCH_INTERVAL: float = 1.0      # seconds between mtime checks
    FALLBACK_INTERVAL: float = 30.0  # safety-net full refresh

    _refresh_paused: bool = False
    _watch_timer: Timer | None = None
    _fallback_timer: Timer | None = None
    _last_snapshot: dict[str, float] = {}

    def start_live_reload(self) -> None:
        """Start the file watcher and fallback poll timers."""
        if self.WATCH_PATH is not None:
            self._last_snapshot = _find_write_markers(self.WATCH_PATH)
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
        """Compare write-marker snapshot; trigger refresh only on real changes."""
        if self._refresh_paused or self.WATCH_PATH is None:
            return
        curr = _find_write_markers(self.WATCH_PATH)
        if curr != self._last_snapshot:
            self._last_snapshot = curr
            self._on_change_detected()

    async def _do_fallback(self) -> None:
        """Unconditional refresh (fallback timer)."""
        if self._refresh_paused:
            return
        if self.WATCH_PATH is not None:
            self._last_snapshot = _find_write_markers(self.WATCH_PATH)
        self._on_change_detected()

    def _on_change_detected(self) -> None:
        """Called when a change is detected.  Subclasses must override."""
        raise NotImplementedError("Subclass must implement _on_change_detected()")
