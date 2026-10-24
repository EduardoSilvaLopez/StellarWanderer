"""Finds the frames that take too long, by the work they do (not the wait that holds the frame rate).

A frame over HITCH_SECONDS is a hang: one warning for it, with the time of each phase and of the rare operations that
ran in it. A frame between SLOW_SECONDS and HITCH_SECONDS is only slow, and a run of them is a sustained cost, not a
hitch: it is one warning for the whole run, written when a frame is fast again, with the worst frame and the phases
and operations added up over the run.

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
from collections import defaultdict
from contextlib import contextmanager
from typing import DefaultDict, Dict, Iterator, List, Optional, Tuple
from common.game_logging.constants import HITCH_SECONDS, SLOW_SECONDS, GC_SECONDS

logger = logging.getLogger(__name__)


def _format(seconds_by_name: Dict[str, float], counts: Optional[Dict[str, int]] = None) -> str:
    """'name 0.012 s, other 0.003 s' (with 'name 0.036 s over 3 calls' for a name seen more than once)."""
    return ', '.join(
        f'{name} {seconds:.3f} s' + (f' over {counts[name]} calls' if counts is not None and counts[name] > 1 else '')
        for name, seconds in seconds_by_name.items())


class FrameWatch:
    """Times the phases of the current frame and reports it if it hung or was slow."""

    def __init__(self) -> None:
        self._frame_start: Optional[float] = None  # None: no frame is being watched
        self._last_mark: float = 0.0
        self._phases: List[Tuple[str, float]] = []
        self._operations: List[Tuple[str, float]] = []
        self._gc_started: float = 0.0
        self._run_frames: int = 0  # the run of slow frames in progress
        self._run_seconds: float = 0.0
        self._run_worst: float = 0.0
        self._run_phases: DefaultDict[str, float] = defaultdict(float)
        self._run_operations: DefaultDict[str, float] = defaultdict(float)
        self._run_operation_counts: DefaultDict[str, int] = defaultdict(int)

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
        """Times a rare operation, to name it in the report of the frame it slows."""
        started = time.perf_counter()
        try:
            yield
        finally:
            self._operations.append((operation, time.perf_counter() - started))

    def discard(self) -> None:
        """The frame being watched is not reported (a modal dialog ran in it), and the run of slow frames ends."""
        self._frame_start = None
        self._end_run()

    def end(self) -> None:
        """The frame ends (call right before the frame timer ticks): reports it if it was a hang or a slow one."""
        if self._frame_start is None:
            return
        total = time.perf_counter() - self._frame_start
        self._frame_start = None
        if total > HITCH_SECONDS:
            self._end_run()
            operations = ', '.join(f'{name} {seconds:.3f} s' for name, seconds in self._operations)
            logger.warning(
                f'Frame hang: {total:.3f} s. Phases: '
                + ', '.join(f'{name} {seconds:.3f} s' for name, seconds in self._phases) + '.'
                + (f' Operations: {operations}.' if operations else ''))
        elif total > SLOW_SECONDS:
            self._run_frames += 1
            self._run_seconds += total
            self._run_worst = max(self._run_worst, total)
            for name, seconds in self._phases:
                self._run_phases[name] += seconds
            for name, seconds in self._operations:
                self._run_operations[name] += seconds
                self._run_operation_counts[name] += 1
        else:
            self._end_run()

    def _end_run(self) -> None:
        """Writes the run of slow frames, if there is one."""
        if not self._run_frames:
            return
        phases = _format({name: seconds / self._run_frames for name, seconds in self._run_phases.items()})
        operations = _format(self._run_operations, self._run_operation_counts)
        logger.warning(
            f'Slow frames: {self._run_frames} in a row, {self._run_seconds:.3f} s in all, worst {self._run_worst:.3f} s.'
            f' Phases (mean): {phases}.'
            + (f' Operations (total): {operations}.' if operations else ''))
        self._run_frames = 0
        self._run_seconds = self._run_worst = 0.0
        self._run_phases.clear()
        self._run_operations.clear()
        self._run_operation_counts.clear()

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
