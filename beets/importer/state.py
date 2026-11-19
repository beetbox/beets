from __future__ import annotations

import logging
import os
import pickle
import threading
from bisect import bisect_left, insort
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Self

from beets import config

if TYPE_CHECKING:
    from types import TracebackType


# Global logger.
log = logging.getLogger("beets")

_lock = threading.Lock()


@dataclass
class ImportState:
    """Representing the progress of an import task.

    Opens the state file on creation of the class. If you want
    to ensure the state is written to disk, you should use the
    context manager protocol.

    Tagprogress allows long tagging tasks to be resumed when they pause.

    Taghistory is a utility for manipulating the "incremental" import log.
    This keeps track of all directories that were ever imported, which
    allows the importer to only import new stuff.

    Usage
    -----
    ```
    # Readonly
    progress = ImportState().tagprogress

    # Read and write
    with ImportState() as state:
        state["key"] = "value"
    ```
    """

    tagprogress: dict[bytes, list[bytes]]
    taghistory: set[tuple[bytes, ...]]
    path: Path

    def __init__(
        self, readonly: bool = False, path: Path | None = None
    ) -> None:
        self.path = path or config["statefile"].as_path()
        self.tagprogress = {}
        self.taghistory = set()
        self._open()

    def __enter__(self) -> Self:
        _lock.acquire()
        try:
            self._open()  # read latest state
        except BaseException:
            _lock.release()
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            self._save()
        finally:
            _lock.release()

    @property
    def history_dirs(self) -> set[tuple[Path, ...]]:
        """Return imported directory history as a set of `Path` tuples."""
        return {
            tuple(Path(os.fsdecode(p)) for p in paths)
            for paths in self.taghistory
        }

    def _open(self) -> None:
        try:
            with self.path.open("rb") as f:
                state = pickle.load(f)
                # Read the states
                self.tagprogress = state.get("tagprogress", {})
                self.taghistory = state.get("taghistory", set())
        except Exception as exc:
            # The `pickle` module can emit all sorts of exceptions during
            # unpickling, including ImportError. We use a catch-all
            # exception to avoid enumerating them all (the docs don't even have a
            # full list!).
            log.debug("state file could not be read: {}", exc)

    def _save(self) -> None:
        tmp_path = Path(f"{self.path}.tmp")
        try:
            with tmp_path.open("wb") as f:
                pickle.dump(
                    {
                        "tagprogress": self.tagprogress,
                        "taghistory": self.taghistory,
                    },
                    f,
                )
            # Atomic swap so readers never see a partially written file
            tmp_path.replace(self.path)
        except OSError as exc:
            log.error("state file could not be written: {}", exc)

    # -------------------------------- Tagprogress ------------------------------- #

    def progress_add(self, toppath: Path, *paths: Path) -> None:
        """Record that the files under all of the `paths` have been imported
        under `toppath`.
        """
        with self as state:
            imported = state.tagprogress.setdefault(os.fsencode(toppath), [])
            for path in map(os.fsencode, paths):
                if imported and imported[-1] <= path:
                    imported.append(path)
                else:
                    insort(imported, path)

    def progress_has_element(self, toppath: Path, path: Path) -> bool:
        """Return whether `path` has been imported in `toppath`."""
        bytes_path = os.fsencode(path)
        imported = self.tagprogress.get(os.fsencode(toppath), [])
        i = bisect_left(imported, bytes_path)
        return i != len(imported) and imported[i] == bytes_path

    def progress_has(self, toppath: Path) -> bool:
        """Return `True` if there exist paths that have already been
        imported under `toppath`.
        """
        return os.fsencode(toppath) in self.tagprogress

    def progress_reset(self, toppath: Path | None) -> None:
        """Reset the progress for `toppath`."""
        toppath_bytes = os.fsencode(toppath) if toppath else None
        with self as state:
            if toppath_bytes in state.tagprogress:
                del state.tagprogress[toppath_bytes]

    # -------------------------------- Taghistory -------------------------------- #

    def history_add(self, paths: list[Path]) -> None:
        """Add the paths to the history."""
        with self as state:
            state.taghistory.add(tuple(map(os.fsencode, paths)))
