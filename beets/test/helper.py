"""This module includes various helpers that provide fixtures, capture
information or mock the environment.

- `has_program` checks the presence of a command on the system.

- The `ImportSessionFixture` allows one to run importer code while
  controlling the interactions through code.

- The `TestHelper` class encapsulates various fixtures that can be set up.
"""

from __future__ import annotations

import importlib.util
import os
import os.path
import shutil
import subprocess
import sys
import unittest
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from functools import cache, cached_property
from pathlib import Path
from tempfile import gettempdir, mkdtemp, mkstemp
from typing import TYPE_CHECKING, Any, ClassVar, Literal
from unittest.mock import Mock, patch

import pytest
from mediafile import Image, MediaFile

import beets
import beets.plugins
from beets import importer, util
from beets.autotag import AlbumInfo, TrackInfo
from beets.importer import ImportSession
from beets.library import Item, Library
from beets.test import _common
from beets.ui.commands.import_.session import TerminalImportSession
from beets.util import (
    MoveOperation,
    bytestring_path,
    clean_module_tempdir,
    syspath,
)
from beets.util.functemplate import template

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence
    from types import TracebackType
    from unittest.mock import _patch

    from confuse import ConfigSource
    from requests_mock.mocker import Mocker
    from typing_extensions import Self

    from beets.autotag import AlbumMatch, TrackMatch
    from beets.library import Album

RUNNING_IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"


def has_program(cmd: str, args: Iterable[str] = ("--version",)) -> bool:
    """Returns `True` if `cmd` can be executed."""
    full_cmd = [cmd, *args]
    try:
        with open(os.devnull, "wb") as devnull:
            subprocess.check_call(
                full_cmd, stderr=devnull, stdout=devnull, stdin=devnull
            )
    except OSError:
        return False
    except subprocess.CalledProcessError:
        return False
    else:
        return True


@cache
def is_importable(modname: str) -> bool:
    return bool(importlib.util.find_spec(modname))


def check_reflink_support(path: str) -> bool:
    try:
        import reflink
    except ImportError:
        return False

    return reflink.supported_at(path)


NEEDS_REFLINK = pytest.mark.skipif(
    not check_reflink_support(gettempdir()), reason="need reflink"
)
NEEDS_FFPROBE = pytest.mark.skipif(
    not has_program("ffprobe", ("-version",)) and not RUNNING_IN_CI,
    reason="ffprobe (ffmpeg) is not available",
)


class ConfigMixin:
    """Provide isolated configuration for tests."""

    _default_config_sources: ClassVar[list[ConfigSource] | None] = None

    @classmethod
    def default_config_sources(cls) -> list[ConfigSource]:
        """Return a reusable default configuration baseline.

        This way, we only need to call very expensive ``config.read`` once per
        test session.

        NOTE: we're not using ``util.cached_classproperty`` here because its cache is
        reset on every test.
        """
        if cls._default_config_sources is not None:
            return deepcopy(cls._default_config_sources)

        config = beets.IncludeLazyConfig("beets", beets.__name__)
        config.read(user=False, defaults=True)

        config["plugins"] = []
        config["verbose"] = 2
        config["ui"]["color"] = False
        config["threaded"] = False
        config["create_backup_before_migrations"] = False
        cls._default_config_sources = deepcopy(config.sources)
        return deepcopy(cls._default_config_sources)

    @cached_property
    def config(self) -> beets.IncludeLazyConfig:
        """Reset the shared config to a fresh test baseline."""
        config = beets.config
        config.clear()
        config._materialized = True
        config.sources.extend(self.default_config_sources())
        return config


class RunMixin:
    lib: Library

    def run_command(self, *args: str, lib: Library | None = None) -> None:
        """Run a beets command with an arbitrary amount of arguments. The
        Library` defaults to `self.lib`, but can be overridden with
        the keyword argument `lib`.
        """
        sys.argv = ["beet", *args]  # avoid leakage from test suite args
        lib = lib or self.lib

        with (
            patch.object(lib, "_close", Mock()),
            patch("beets.ui._open_library", return_value=lib),
        ):
            beets.ui._raw_main(list(args))


@pytest.mark.usefixtures("io")
class IOMixin(RunMixin):
    io: _common.DummyIO

    def run_with_output(self, *args: str) -> str:
        self.io.getoutput()
        self.run_command(*args)
        return self.io.getoutput()


class PathsMixin:
    resource_path = Path(os.fsdecode(_common.RSRC)) / "full.mp3"

    @cached_property
    def temp_path(self) -> Path:
        return Path(self.create_temp_dir())

    def create_temp_dir(self, **kwargs: Any) -> str:
        return mkdtemp(**kwargs)

    def remove_temp_dir(self) -> None:
        """Delete the temporary directory created by `create_temp_dir`."""
        shutil.rmtree(self.temp_path)


class TestHelper(RunMixin, PathsMixin, ConfigMixin):
    """Helper mixin for high-level cli and plugin tests.

    This mixin provides methods to isolate beets' global state.

    You may use it as a context manager in pytest fixtures in order to setup
    tests at a class or module level. See ``module_helper`` and ``class_helper``
    fixtures, for example.
    """

    request: pytest.FixtureRequest

    def __enter__(self) -> Self:
        self.setup_beets()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Literal[False]:
        self.teardown_beets()
        # return False/None to propagate exceptions
        return False

    @pytest.fixture(autouse=True)
    def setup(self, request: pytest.FixtureRequest) -> Iterator[None]:
        self.request = request
        self.setup_beets()
        try:
            yield
        finally:
            self.teardown_beets()

    lib: Library

    db_on_disk: ClassVar[bool] = False

    @cached_property
    def lib_path(self) -> Path:
        lib_path = self.temp_path / "libdir"
        lib_path.mkdir(exist_ok=True)
        return lib_path

    # TODO automate teardown through hook registration

    def setup_beets(self) -> None:
        """Setup pristine global configuration and library for testing.

        Sets ``beets.config`` so we can safely use any functionality
        that uses the global configuration.  All paths used are
        contained in a temporary directory

        Sets the following properties on itself.

        - ``temp_path`` Path to a temporary directory containing all
          files specific to beets

        - ``lib_path`` Path to a subfolder of ``temp_path``, containing the
          library's media files. Same as ``config['directory']``.

        - ``lib`` Library instance created with the settings from
          ``config``.

        Make sure you call ``teardown_beets()`` afterwards.
        """
        temp_dir_str = str(self.temp_path)
        self.env_patcher = patch.dict(
            "os.environ",
            {
                "BEETSDIR": temp_dir_str,
                "HOME": temp_dir_str,  # used by Confuse to create directories.
            },
        )
        self.env_patcher.start()

        self.config["directory"] = str(self.lib_path)

        dbpath = (
            self.config["library"].as_path()
            if self.db_on_disk
            else Path(":memory:")
        )
        self.lib = Library(dbpath, str(self.lib_path))

    def teardown_beets(self) -> None:
        self.env_patcher.stop()
        self.lib._close()
        self.remove_temp_dir()

    # Library fixtures methods

    def create_item(self, **values: Any) -> Item:
        """Return an `Item` instance with sensible default values.

        The item receives its attributes from `**values` paratmeter. The
        `title`, `artist`, `album`, `track`, `format` and `path`
        attributes have defaults if they are not given as parameters.
        The `title` attribute is formatted with a running item count to
        prevent duplicates. The default for the `path` attribute
        respects the `format` value.

        The item is attached to the database from `self.lib`.
        """
        values_: dict[str, Any] = {
            "title": "t\u00eftle 1",
            "artist": "the \u00e4rtist",
            "album": "the \u00e4lbum",
            "track": 1,
            "format": "MP3",
        }
        values_.update(values)
        values_["db"] = self.lib
        item = Item(**values_)
        if "path" not in values:
            item["path"] = f"audio.{item['format'].lower()}"
        # mtime needs to be set last since other assignments reset it.
        item.mtime = 12345
        return item

    def add_item(self, **values: Any) -> Item:
        """Add an item to the library and return it.

        Creates the item by passing the parameters to `create_item()`.

        If `path` is not set in `values` it is set to `item.destination()`.
        """
        # When specifying a path, store it normalized (as beets does
        # ordinarily).
        if "path" in values:
            values["path"] = util.normpath(values["path"])

        item = self.create_item(**values)
        item.add(self.lib)

        # Ensure every item has a path.
        if "path" not in values:
            item["path"] = item.destination()
            item.store()

        return item

    def add_item_fixture(self, **values: Any) -> Item:
        """Add an item with an actual audio file to the library."""
        item = self.create_item(**values)
        extension = item["format"].lower()
        item["path"] = os.path.join(
            _common.RSRC, util.bytestring_path(f"min.{extension}")
        )
        item.add(self.lib)
        item.move(operation=MoveOperation.COPY)
        item.store()
        return item

    def add_album(self, **values: Any) -> Album:
        item = self.add_item(**values)
        return self.lib.add_album([item])

    def add_item_fixtures(self, ext: str = "mp3", count: int = 1) -> list[Item]:
        """Add a number of items with files to the database."""
        # TODO base this on `add_item()`
        items = []
        path = os.path.join(_common.RSRC, util.bytestring_path(f"full.{ext}"))
        for i in range(count):
            item = Item.from_path(path)
            item.album = f"\u00e4lbum {i}"  # Check unicode paths
            item.title = f"t\u00eftle {i}"
            # mtime needs to be set last since other assignments reset it.
            item.mtime = 12345
            item.add(self.lib)
            item.move(operation=MoveOperation.COPY)
            item.store()
            items.append(item)
        return items

    def add_album_fixture(
        self,
        track_count: int = 1,
        fname: str = "full",
        ext: str = "mp3",
        disc_count: int = 1,
    ) -> Album:
        """Add an album with files to the database."""
        items = []
        path = os.path.join(
            _common.RSRC, util.bytestring_path(f"{fname}.{ext}")
        )
        for discnumber in range(1, disc_count + 1):
            for i in range(track_count):
                item = Item.from_path(path)
                item.album = "\u00e4lbum"  # Check unicode paths
                item.title = f"t\u00eftle {i}"
                item.disc = discnumber
                # mtime needs to be set last since other assignments reset it.
                item.mtime = 12345
                item.add(self.lib)
                item.move(operation=MoveOperation.COPY)
                item.store()
                items.append(item)
        return self.lib.add_album(items)

    def create_mediafile_fixture(
        self,
        ext: str = "mp3",
        images: list[str] | None = None,
        target_dir: util.PathLike | None = None,
    ) -> bytes:
        """Copy a fixture mediafile with the extension to `temp_path`.

        `images` is a subset of 'png', 'jpg', and 'tiff'. For each
        specified extension a cover art image is added to the media
        file.
        """
        if not target_dir:
            target_dir = self.temp_path
        src = os.path.join(_common.RSRC, util.bytestring_path(f"full.{ext}"))
        handle, path = mkstemp(dir=target_dir)
        path = bytestring_path(path)
        os.close(handle)
        shutil.copyfile(syspath(src), syspath(path))

        if images:
            mediafile = MediaFile(path)
            imgs = []
            for img_ext in images:
                file = util.bytestring_path(f"image-2x3.{img_ext}")
                img_path = os.path.join(_common.RSRC, file)
                with open(img_path, "rb") as f:
                    imgs.append(Image(f.read()))
            mediafile.images = imgs
            mediafile.save()

        return path

    # Safe file operations

    def touch(
        self,
        path: util.PathLike,
        dir_: util.PathLike | None = None,
        content: str = "",
    ) -> bytes:
        """Create a file at `path` with given content.

        If `dir_` is given, it is prepended to `path`. After that, if the
        path is relative, it is resolved with respect to
        `self.temp_path`.
        """
        bytes_path = os.fsencode(path)
        if dir_:
            bytes_path = os.path.join(os.fsencode(dir_), bytes_path)

        if not os.path.isabs(bytes_path):
            bytes_path = os.path.join(os.fsencode(self.temp_path), bytes_path)

        parent = os.path.dirname(bytes_path)
        if not os.path.isdir(syspath(parent)):
            os.makedirs(syspath(parent))

        with open(syspath(bytes_path), "a+") as f:
            f.write(content)
        return bytes_path


# A test harness for all beets tests.
# Provides temporary, isolated configuration.
class BeetsTestCase(unittest.TestCase, TestHelper):
    """A unittest.TestCase subclass that saves and restores beets'
    global configuration. This allows tests to make temporary
    modifications that will then be automatically removed when the test
    completes. Also provides some additional assertion methods, a
    temporary directory, and a DummyIO.

    DEPRECATED: Use TestHelper instead.
    """


class ItemInDBTestCase(BeetsTestCase):
    """A test case that includes an in-memory library object (`lib`) and
    an item added to the library (`i`).
    """

    def setUp(self) -> None:
        super().setUp()
        self.i = _common.item(self.lib)


class PytestTestHelper(TestHelper):
    """Same as the BeetsTestCase unittest setup but for pytest."""

    @pytest.fixture(autouse=True)
    def setup(self) -> Iterator[None]:
        self.setup_beets()
        try:
            yield
        finally:
            self.teardown_beets()


class PluginMixin(ConfigMixin):
    plugin: ClassVar[str]
    preload_plugin: ClassVar[bool] = True

    def setup_beets(self) -> None:
        super().setup_beets()  # type: ignore[misc]
        if self.preload_plugin:
            self.load_plugins()

    def teardown_beets(self) -> None:
        super().teardown_beets()  # type: ignore[misc]
        self.unload_plugins()

    def register_plugin(
        self, plugin_class: type[beets.plugins.BeetsPlugin]
    ) -> None:
        beets.plugins._instances.append(plugin_class())

    def load_plugins(self, *plugins: str) -> None:
        """Load and initialize plugins by names.

        Similar setting a list of plugins in the configuration. Make
        sure you call ``unload_plugins()`` afterwards.
        """
        # FIXME this should eventually be handled by a plugin manager
        plugins = (self.plugin,) if hasattr(self, "plugin") else plugins
        self.config["plugins"] = plugins
        beets.plugins.load_plugins()

    def unload_plugins(self) -> None:
        """Unload all plugins and remove them from the configuration."""
        # FIXME this should eventually be handled by a plugin manager
        beets.plugins.BeetsPlugin.listeners.clear()
        beets.plugins.BeetsPlugin._raw_listeners.clear()
        self.config["plugins"] = []
        beets.plugins._instances.clear()

    @contextmanager
    def configure_plugin(self, config: Any) -> Iterator[None]:
        self.config[self.plugin].set(config)
        self.load_plugins(self.plugin)

        yield

        self.unload_plugins()


class PluginTestCase(PluginMixin, BeetsTestCase):
    """
    DEPRECATED: Use PluginTestHelper instead.
    """


class PluginTestHelper(PluginMixin, TestHelper):
    """Helper mixin for pytest-based plugin tests.

    This mixin provides the standard beets test setup and automatically
    initializes and tears down plugin state for each test.

    .. code-block:: python

        class TestMyPlugin(PluginTestHelper):
            plugin: ClassVar[str] = "myplugin"
    """


class ImporterMixin(PathsMixin, ConfigMixin):
    """Provides tools to setup a library, a directory containing files that are
    to be imported and an import session. The class also provides stubs for the
    autotagging library and several assertions for the library.
    """

    default_import_config: ClassVar[dict[str, Any]] = {
        "autotag": True,
        "copy": True,
        "hardlink": False,
        "link": False,
        "move": False,
        "resume": False,
        "singletons": False,
        "timid": True,
    }

    lib: Library
    importer: ImportSession
    import_media: list[MediaFile]

    @cached_property
    def import_path(self) -> Path:
        import_path = self.temp_path / "import"
        import_path.mkdir(exist_ok=True)
        return import_path

    def prepare_track_for_import(
        self, track_id: int, album_path: Path, album_id: int | None = None
    ) -> Path:
        track_path = album_path / f"track_{track_id}.mp3"
        shutil.copy(self.resource_path, track_path)
        medium = MediaFile(track_path)
        medium.update(
            {
                "album": f"Tag Album{f' {album_id}' if album_id else ''}",
                "albumartist": None,
                "mb_albumid": None,
                "comp": None,
                "artist": "Tag Artist",
                "title": f"Tag Track {track_id}",
                "track": track_id,
                "mb_trackid": None,
            }
        )
        medium.save()
        self.import_media.append(medium)
        return track_path

    def prepare_album_for_import(
        self,
        item_count: int,
        album_id: int | None = None,
        album_path: Path | None = None,
    ) -> list[Path]:
        """Create an album directory with media files to import.

        The directory has following layout
          album/
            track_1.mp3
            track_2.mp3
            track_3.mp3
        """
        if not album_path:
            album_dir = f"album_{album_id}" if album_id else "album"
            album_path = self.import_path / album_dir

        album_path.mkdir(exist_ok=True)

        return [
            self.prepare_track_for_import(tid, album_path, album_id=album_id)
            for tid in range(1, item_count + 1)
        ]

    def prepare_albums_for_import(self, count: int = 1) -> None:
        album_dirs = self.import_path.glob("album_*")
        base_idx = int(str(max(album_dirs, default="0")).split("_")[-1]) + 1

        for album_id in range(base_idx, count + base_idx):
            self.prepare_album_for_import(1, album_id=album_id)

    def _get_import_session(self, import_dir: Path) -> ImportSession:
        return ImportSessionFixture(
            self.lib,
            loghandler=None,
            query=None,
            paths=[os.fsencode(import_dir)],
        )

    def setup_importer(
        self, import_dir: Path | None = None, **kwargs: Any
    ) -> ImportSession:
        self.config["import"].set_args({**self.default_import_config, **kwargs})
        self.importer = self._get_import_session(import_dir or self.import_path)
        return self.importer

    def setup_singleton_importer(self, **kwargs: Any) -> ImportSession:
        return self.setup_importer(singletons=True, **kwargs)


class ImportHelper(TestHelper, ImporterMixin):
    def setup_beets(self) -> None:
        super().setup_beets()
        self.import_media = []
        self.lib.path_formats = [
            ("default", template(os.path.join("$artist", "$album", "$title"))),
            ("singleton:true", template(os.path.join("singletons", "$title"))),
            (
                "comp:true",
                template(os.path.join("compilations", "$album", "$title")),
            ),
        ]


class AsIsImporterMixin(ImporterMixin):
    def setup_beets(self) -> None:
        super().setup_beets()  # type: ignore[misc]
        self.prepare_album_for_import(1)

    def run_asis_importer(self, **kwargs: Any) -> ImportSession:
        importer = self.setup_importer(autotag=False, **kwargs)
        importer.run()
        return importer


class ImportSessionFixture(ImportSession):
    """ImportSession that can be controlled programaticaly.

    >>> lib = Library(':memory:')
    >>> importer = ImportSessionFixture(lib, paths=['/path/to/import'])
    >>> importer.add_choice(importer.Action.SKIP)
    >>> importer.add_choice(importer.Action.ASIS)
    >>> importer.default_choice = importer.Action.APPLY
    >>> importer.run()

    This imports ``/path/to/import`` into `lib`. It skips the first
    album and imports the second one with metadata from the tags. For the
    remaining albums, the metadata from the autotagger will be applied.
    """

    _choices: list[importer.Action | int]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._choices = []

    default_choice = importer.Action.APPLY

    def add_choice(self, choice: importer.Action | int) -> None:
        self._choices.append(choice)

    def clear_choices(self) -> None:
        self._choices = []

    def choose_match(
        self, task: importer.ImportTask
    ) -> AlbumMatch | importer.Action:
        try:
            choice = self._choices.pop(0)
        except IndexError:
            choice = self.default_choice

        if task.candidates:
            if choice == importer.Action.APPLY:
                return task.candidates[0]  # type: ignore[return-value]
            if isinstance(choice, int):
                return task.candidates[choice - 1]  # type: ignore[return-value]

        assert not isinstance(choice, int), f"Invalid choice: {choice}"
        return choice

    choose_item = choose_match  # type: ignore[assignment]


class TerminalImportSessionFixture(TerminalImportSession):
    def __init__(self, *args, **kwargs):
        self.io = kwargs.pop("io")
        super().__init__(*args, **kwargs)
        self._choices = []

    default_choice = importer.Action.APPLY

    def add_choice(self, choice: importer.Action | int) -> None:
        self._choices.append(choice)

    def clear_choices(self) -> None:
        self._choices = []

    def choose_match(
        self, task: importer.ImportTask
    ) -> AlbumMatch | importer.Action:
        self._add_choice_input()
        return super().choose_match(task)

    def choose_item(
        self, task: importer.ImportTask
    ) -> TrackMatch | importer.Action:
        self._add_choice_input()
        return super().choose_item(task)

    def _add_choice_input(self) -> None:
        try:
            choice = self._choices.pop(0)
        except IndexError:
            choice = self.default_choice

        if choice == importer.Action.APPLY:
            self.io.addinput("A")
        elif choice == importer.Action.ASIS:
            self.io.addinput("U")
        elif choice == importer.Action.ALBUMS:
            self.io.addinput("G")
        elif choice == importer.Action.TRACKS:
            self.io.addinput("T")
        elif choice == importer.Action.SKIP:
            self.io.addinput("S")
        else:
            self.io.addinput("M")
            self.io.addinput(str(choice))
            self._add_choice_input()


class TerminalImportMixin(IOMixin, ImportHelper):
    """Provides_a terminal importer for the import session."""

    def _get_import_session(self, import_dir: Path) -> importer.ImportSession:
        return TerminalImportSessionFixture(
            self.lib,
            loghandler=None,
            query=None,
            io=self.request.getfixturevalue("io"),
            paths=[os.fsencode(import_dir)],
        )


@dataclass
class AutotagStub:
    """Stub out MusicBrainz album and track matcher and control what the
    autotagger returns.
    """

    NONE = "NONE"
    IDENT = "IDENT"
    GOOD = "GOOD"
    BAD = "BAD"
    MISSING = "MISSING"
    matching: str

    length = 2

    def install(self) -> Self:
        self.patchers: list[_patch[Any]] = [
            patch("beets.metadata_plugins.album_for_id", lambda *_: None),
            patch("beets.metadata_plugins.track_for_id", lambda *_: None),
            patch("beets.metadata_plugins.candidates", self.candidates),
            patch(
                "beets.metadata_plugins.item_candidates", self.item_candidates
            ),
        ]
        for p in self.patchers:
            p.start()

        return self

    def restore(self) -> None:
        for p in self.patchers:
            p.stop()

    def candidates(
        self, items: Sequence[Item], artist: str, album: str, _: bool
    ) -> Iterable[AlbumInfo]:
        if self.matching == self.IDENT:
            yield self._make_album_match(artist, album, len(items))

        elif self.matching == self.GOOD:
            for i in range(self.length):
                yield self._make_album_match(artist, album, len(items), i)

        elif self.matching == self.BAD:
            for i in range(self.length):
                yield self._make_album_match(artist, album, len(items), i + 1)

        elif self.matching == self.MISSING:
            yield self._make_album_match(artist, album, len(items), missing=1)

    def item_candidates(
        self, item: Item, artist: str, title: str
    ) -> Iterable[TrackInfo]:
        yield TrackInfo(
            title=title.replace("Tag", "Applied"),
            track_id="trackid",
            artist=artist.replace("Tag", "Applied"),
            artist_id="artistid",
            length=1,
            index=0,
        )

    def _make_track_match(
        self, artist: str, album: str, number: int
    ) -> TrackInfo:
        return TrackInfo(
            title=f"Applied Track {number}",
            track_id=f"match {number}",
            artist=artist,
            length=1,
            index=0,
        )

    def _make_album_match(
        self,
        artist: str,
        album: str,
        tracks: int,
        distance: int = 0,
        missing: int = 0,
    ) -> AlbumInfo:
        id_ = f" {'M' * distance}" if distance else ""

        artist = f"{artist.replace('Tag', 'Applied')}{id_}"
        album = f"{album.replace('Tag', 'Applied')}{id_}"

        track_infos = []
        for i in range(tracks - missing):
            track_infos.append(self._make_track_match(artist, album, i + 1))

        return AlbumInfo(
            artist=artist,
            album=album,
            tracks=track_infos,
            va=False,
            album_id=f"albumid{id_}",
            artist_id=f"artistid{id_}",
            albumtype="soundtrack",
            data_source="match_source",
            bandcamp_album_id="bc_url",
        )


class AutotagImportHelper(ImportHelper):
    matching = AutotagStub.IDENT

    def setup_beets(self) -> None:
        super().setup_beets()
        self.matcher = AutotagStub(self.matching).install()

    def teardown_beets(self) -> None:
        self.matcher.restore()
        super().teardown_beets()


class AutotagImportTestCase(AutotagImportHelper, BeetsTestCase):
    """DEPRECATED: Use AutotagImportHelper instead."""


@dataclass(slots=True)
class ImageRequestMocker:
    mocker: Mocker

    # Image types and their file headers
    IMAGE_HEADERS: ClassVar[dict[str, bytes]] = {
        "image/jpeg": b"\xff\xd8\xff\x00\x00\x00JFIF",
        "image/png": b"\211PNG\r\n\032\n",
        "image/gif": b"GIF89a",
        # dummy type that is definitely not a valid image content type
        "image/watercolour": b"watercolour",
        "text/html": (
            b"<!DOCTYPE html>\n<html>\n<head>\n</head>\n"
            b"<body>\n</body>\n</html>"
        ),
    }

    def get(
        self,
        url: str,
        *,
        content_type: str = "image/jpeg",
        file_type: str | None = None,
        content: str | bytes | None = None,
    ) -> None:
        actual_file_type = file_type or content_type

        if content is None:
            try:
                content = self.IMAGE_HEADERS[actual_file_type].ljust(
                    32, b"\x00"
                )
            except KeyError as exc:
                # If we can't return a file that looks like real file of the requested
                # type, better fail the test than returning something else, which might
                # violate assumption made when writing a test.
                raise AssertionError(
                    f"Mocking {actual_file_type!r} responses not supported"
                ) from exc

        if isinstance(content, str):
            content = content.encode()

        self.mocker.get(
            url, headers={"Content-Type": content_type}, content=content
        )


class FetchImageHelper:
    """Pytest mixin providing image response mocking utilities."""

    @pytest.fixture
    def image_request_mock(self, requests_mock: Mocker) -> ImageRequestMocker:
        return ImageRequestMocker(requests_mock)


class CleanupModulesMixin:
    modules: ClassVar[tuple[str, ...]]

    @classmethod
    def tearDownClass(cls) -> None:
        """Remove files created by the plugin."""
        for module in cls.modules:
            clean_module_tempdir(module)
