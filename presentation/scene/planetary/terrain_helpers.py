"""The helper processes that build the terrain's chunks, so that the game does not stall while it flies over new ground.

Rules, from the test of a packaged build (temp/ideas/helper_spike/NOTES.md): main.py calls `freeze_support()` first
under its `__main__` guard; what a helper runs lives in this small module and in `terrain_mesh` (numpy only), never in
main.py; the helpers end with their parent, because a crashed or killed game gives them no chance to be shut down;
they print nothing (a windowed game has no stdout); a dead helper is replaced; and the pool starts at load, not at the
first chunk. The terrain is rebuilt from the seed, so nothing is lost when a helper dies.
"""

from __future__ import annotations
import multiprocessing
import os
import threading
import time
from concurrent.futures import Future, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from typing import Dict, List, Tuple

import numpy as np

from .terrain_mesh import Key, build_chunk_timed

WORKERS = 2


def _end_with_parent() -> None:
    parent = multiprocessing.parent_process()
    if parent is None:
        return
    while parent.is_alive():
        time.sleep(0.5)
    os._exit(0)


def start() -> None:
    """What every helper does when it starts: watches for the end of the game."""
    threading.Thread(target=_end_with_parent, name="end-with-parent", daemon=True).start()


class ChunkBuilder:
    """Chunks asked for and built in the helpers, for the main process to collect: `request` them, then `collect`."""

    def __init__(self) -> None:
        self._pool: ProcessPoolExecutor | None = None
        self._pending: Dict[Key, Future] = {}
        self.build_seconds = 0.0
        self.built = 0

    def start(self) -> None:
        """Starts the helpers and waits for them to be up (about 0.6 s), so that the first request does not stall."""
        self._pool = ProcessPoolExecutor(max_workers=WORKERS, initializer=start)
        for warm in [self._pool.submit(build_chunk_timed, (8, 0, 0), 1, 6.0e6, 0.0) for _ in range(WORKERS)]:
            warm.result()

    @property
    def pending(self) -> int:
        return len(self._pending)

    def request(self, key: Key, seed: int, radius: float, relief: float, platforms: Tuple = ()) -> None:
        if self._pool is None:
            self.start()
        if key in self._pending or self._pool is None:
            return
        try:
            self._pending[key] = self._pool.submit(build_chunk_timed, key, seed, radius, relief, platforms)
        except BrokenProcessPool:   # a helper has died: new ones, and this request is dropped like the lost ones
            self._replace_pool()

    def collect(self, limit: int) -> List[Tuple[Key, np.ndarray]]:
        """Up to `limit` finished chunks. If a helper has died, the pool is replaced and the lost requests dropped: the
        renderer asks again for what it still needs."""
        done: List[Tuple[Key, np.ndarray]] = []
        for key, future in list(self._pending.items()):
            if len(done) >= limit:
                break
            if not future.done():
                continue
            del self._pending[key]
            try:
                _, vertices, seconds = future.result()
            except BrokenProcessPool:
                self._replace_pool()
                break
            self.build_seconds += seconds
            self.built += 1
            done.append((key, vertices))
        return done

    def _replace_pool(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
        self._pending.clear()
        self.start()

    def shutdown(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=True, cancel_futures=True)
            self._pool = None
        self._pending.clear()
