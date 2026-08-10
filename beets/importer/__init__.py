"""Provides the basic, interface-agnostic workflow for importing and
autotagging music files.
"""

from .actions import Action, DuplicateAction
from .session import ImportAbortError, ImportSession
from .tasks import (
    ArchiveImportTask,
    ImportTask,
    SentinelImportTask,
    SingletonImportTask,
)

# Note: Stages are not exposed to the public API

__all__ = [
    "Action",
    "ArchiveImportTask",
    "DuplicateAction",
    "ImportAbortError",
    "ImportSession",
    "ImportTask",
    "SentinelImportTask",
    "SingletonImportTask",
]
