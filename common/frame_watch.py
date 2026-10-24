"""Finds the frames that hang, by the work they do (not the wait that holds the frame rate).

A frame over HITCH_SECONDS is logged as a warning, with the time of each phase and of the rare operations that ran in
it. At most one such warning is written per second; the hangs left out in between are counted in the next one.

The game loop marks the end of each phase (mark) between `begin`, right after the frame timer ticks, and `end`, right
before it ticks again; the drawing marks its own parts in between. Rare or first-use operations (a Km2 generated, a
rock batch built, a belt sector, a save) are timed at their top calling method with `timed`; never nest them, so the
figures do not count twice. A modal dialog, which blocks for as long as the pilot takes, calls `discard` so its frame
is not reported. The last phase is the GPU one: pygame.display.flip is where a slow draw shows up, because OpenGL
calls return before the work is done.

Garbage collections that take longer than GC_SECONDS are logged too, since they hang a frame at random.
"""

from __future__ import annotations
import gc
import logging
import time
from contextlib import contextmanager
from typing import Iterator, List, Optional, Tuple
from common.game_logging.constants import HITCH_SECONDS, GC_SECONDS

logger = logging.getLogger(__name__)

HANG_LOG_INTERVAL_SECONDS = 1.0  # the least time between two hang warnings


class FrameWatch:
    """Times the phases of the current frame and reports it if it hung."""

    def __init__(self) -> None:
        self._frame_start: Optional[float] = None  # None: no frame is being watched
        self._last_mark: float = 0.0
        self._phases: List[Tuple[str, float]] = []
        self._operations: List[Tuple[str, float]] = []
        self._gc_started: float = 0.0
        self._last_hang_logged: float = float('-inf')
        self._hangs_left_out: int = 0

    def begin(self) -> None:
        """A new frame starts (call right after the frame timer ticks)."""
        self._frame_start = self._last_mark = time.perf_counter()
        self._phases.clear()
        self._operations.clear()

    def mark(self, phase: str) -> None:
        """The phase `phase` ends here: it started at the previous mark (or at `begin`)."""
        now = time.perf_counter()
        self._phases.append((phase, now - self._last_mark))
        self._last_mark = now

    @contextmanager
    def timed(self, operation: str) -> Iterator[None]:
        """Times a rare operation, to name it in the report of the frame it hangs."""
        started = time.perf_counter()
        try:
            yield
        finally:
            self._operations.append((operation, time.perf_counter() - started))

    def discard(self) -> None:
        """The frame being watched is not reported (a modal dialog ran in it)."""
        self._frame_start = None

    def end(self) -> None:
        """The frame ends (call right before the frame timer ticks): warns if it took longer than HITCH_SECONDS."""
        if self._frame_start is None:
            return
        now = time.perf_counter()
        total = now - self._frame_start
        self._frame_start = None
        if total <= HITCH_SECONDS:
            return
        if now - self._last_hang_logged < HANG_LOG_INTERVAL_SECONDS:
            self._hangs_left_out += 1
            return
        phases = ', '.join(f'{name} {seconds:.3f} s' for name, seconds in self._phases)
        operations = ', '.join(f'{name} {seconds:.3f} s' for name, seconds in self._operations)
        logger.warning(
            f'Frame hang: {total:.3f} s. Phases: {phases}.'
            + (f' Operations: {operations}.' if operations else '')
            + (f' {self._hangs_left_out} more hangs since the last warning.' if self._hangs_left_out else ''))
        self._last_hang_logged = now
        self._hangs_left_out = 0

    def watch_garbage_collector(self) -> None:
        """Logs the garbage collections longer than GC_SECONDS."""
        gc.callbacks.append(self._on_garbage_collection)

    def _on_garbage_collection(self, phase: str, info: dict) -> None:
        if phase == 'start':
            self._gc_started = time.perf_counter()
            return
        seconds = time.perf_counter() - self._gc_started
        if seconds > GC_SECONDS:
            logger.warning(f"Garbage collection of generation {info['generation']} took {seconds:.3f} s.")


frame_watch = FrameWatch()  # the singleton: use it anywhere in the application
