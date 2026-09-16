from __future__ import annotations

from itertools import chain
from typing import TYPE_CHECKING, Any, Literal, TypedDict, get_args

if TYPE_CHECKING:
    from collections.abc import Mapping

    from beets.autotag import AlbumInfo, TrackInfo
    from beets.autotag.match import AlbumMatch
    from beets.importer import ImportSession, ImportTask
    from beets.library import Album, Item, LibModel, Library

AfterWriteEventType = Literal["after_write"]
ItemPathEventType = Literal[
    "before_item_moved",
    "item_copied",
    "item_hardlinked",
    "item_linked",
    "item_moved",
    "item_reflinked",
]
BeforeChooseCandidateEventType = Literal["before_choose_candidate"]
ImportTaskBeforeChoiceEventType = Literal["import_task_before_choice"]
ImportTaskCreatedEventType = Literal["import_task_created"]
ImportTaskEventType = Literal[
    "import_task_apply",
    "import_task_choice",
    "import_task_files",
    "import_task_start",
]
ImportEventType = Literal["import"]
AlbumImportedEventType = Literal["album_imported"]
AlbumEventType = Literal["album_removed", "art_set"]
AlbumInfoReceivedEventType = Literal["albuminfo_received"]
TrackInfoReceivedEventType = Literal["trackinfo_received"]
MetadataReceivedEventType = (
    AlbumInfoReceivedEventType | TrackInfoReceivedEventType
)
AlbumMatchedEventType = Literal["album_matched"]
LibraryEventType = Literal["cli_exit", "library_opened"]
DatabaseChangeEventType = Literal["database_change"]
ImportBeginEventType = Literal["import_begin"]
ItemImportedEventType = Literal["item_imported"]
ItemEventType = Literal["item_removed"]
WriteEventType = Literal["write"]
MusicBrainzExtractEventType = Literal["mb_album_extract", "mb_track_extract"]
NoArgsEventType = Literal["pluginload", "smartplaylist_update"]
AfterConvertEventType = Literal["after_convert"]
EventType = (
    AfterWriteEventType
    | ItemPathEventType
    | BeforeChooseCandidateEventType
    | ImportTaskBeforeChoiceEventType
    | ImportTaskCreatedEventType
    | ImportTaskEventType
    | ImportEventType
    | AlbumImportedEventType
    | AlbumEventType
    | MetadataReceivedEventType
    | AlbumMatchedEventType
    | LibraryEventType
    | DatabaseChangeEventType
    | ImportBeginEventType
    | ItemImportedEventType
    | ItemEventType
    | WriteEventType
    | MusicBrainzExtractEventType
    | NoArgsEventType
    | AfterConvertEventType
)
ALL_EVENTS = list(chain.from_iterable(get_args(e) for e in get_args(EventType)))


class AfterWriteEventArgs(TypedDict):
    item: Item
    path: bytes


class ItemPathEventArgs(TypedDict):
    item: Item
    source: bytes
    destination: bytes


class ImportTaskEventArgs(TypedDict):
    session: ImportSession
    task: ImportTask


class ImportEventArgs(TypedDict):
    lib: Library
    paths: list[bytes]


class AlbumImportedEventArgs(TypedDict):
    lib: Library
    album: Album


class AlbumEventArgs(TypedDict):
    album: Album


class AlbumInfoReceivedEventArgs(TypedDict):
    info: AlbumInfo


class TrackInfoReceivedEventArgs(TypedDict):
    info: TrackInfo


class AlbumMatchedEventArgs(TypedDict):
    match: AlbumMatch


class LibraryEventArgs(TypedDict):
    lib: Library


class DatabaseChangeEventArgs(TypedDict):
    lib: Library
    model: LibModel


class ImportBeginEventArgs(TypedDict):
    session: ImportSession


class ItemImportedEventArgs(TypedDict):
    lib: Library
    item: Item


class ItemEventArgs(TypedDict):
    item: Item


class WriteEventArgs(TypedDict):
    item: Item
    path: bytes
    tags: dict[str, Any]


class MusicBrainzExtractEventArgs(TypedDict):
    data: Mapping[str, Any]


class AfterConvertEventArgs(TypedDict):
    item: Item
    dest: bytes
    keepnew: bool
