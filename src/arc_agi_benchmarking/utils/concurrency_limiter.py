"""Cross-process concurrency limits for provider API calls."""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path
import re
import tempfile
from typing import IO, AsyncIterator

# File locking is platform-specific: fcntl.flock on POSIX, msvcrt.locking on
# Windows. Both are wrapped behind _lock_nonblocking/_unlock below so the rest
# of this module stays platform-agnostic.
if sys.platform == "win32":
    import msvcrt

    def _lock_nonblocking(handle: IO[str]) -> bool:
        """Attempt to lock the first byte of ``handle``. Returns True on success."""
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    def _unlock(handle: IO[str]) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock_nonblocking(handle: IO[str]) -> bool:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False

    def _unlock(handle: IO[str]) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class ProviderConcurrencyLimiter:
    """A file-lock semaphore shared by every benchmark process for a provider."""

    def __init__(
        self,
        provider: str,
        max_concurrency: int,
        lock_root: Path | None = None,
        poll_interval: float = 0.1,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")

        safe_provider = re.sub(r"[^A-Za-z0-9_.-]+", "_", provider)
        root = lock_root or (
            Path(tempfile.gettempdir())
            / "arc-agi-benchmarking-provider-concurrency"
        )
        self.lock_dir = root / safe_provider
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self.max_concurrency = max_concurrency
        self.poll_interval = poll_interval

        for slot_index in range(max_concurrency):
            slot_path = self._slot_path(slot_index)
            slot_path.touch(exist_ok=True)
            # msvcrt.locking locks a byte range, so the file needs at least
            # one byte to lock on Windows; a no-op on POSIX (flock locks the
            # whole file regardless of size).
            if sys.platform == "win32" and slot_path.stat().st_size == 0:
                slot_path.write_bytes(b"0")

    def _slot_path(self, slot_index: int) -> Path:
        return self.lock_dir / f"slot-{slot_index}.lock"

    def _try_acquire(self) -> IO[str] | None:
        for slot_index in range(self.max_concurrency):
            handle = self._slot_path(slot_index).open("r+b")
            if _lock_nonblocking(handle):
                return handle
            handle.close()
        return None

    async def acquire(self) -> IO[str]:
        while True:
            handle = self._try_acquire()
            if handle is not None:
                return handle
            await asyncio.sleep(self.poll_interval)

    @staticmethod
    def release(handle: IO[str]) -> None:
        try:
            _unlock(handle)
        finally:
            handle.close()

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        handle = await self.acquire()
        try:
            yield
        finally:
            self.release(handle)
