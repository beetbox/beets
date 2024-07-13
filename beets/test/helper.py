# This file is part of beets.
# Copyright 2016, Thomas Scholtes.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""This module includes various helpers that provide fixtures, capture
information or mock the environment.

- The `control_stdin` and `capture_stdout` context managers allow one to
  interact with the user interface.

- `has_program` checks the presence of a command on the system.

- The `generate_album_info` and `generate_track_info` functions return
  fixtures to be used when mocking the autotagger.

- The `ImportSessionFixture` allows one to run importer code while
  controlling the interactions through code.

- The `TestHelper` class encapsulates various fixtures that can be set up.
"""

from __future__ import annotations

import os
import os.path
import shutil
import subprocess
import sys
import unittest
from contextlib import contextmanager
from enum import Enum
from io import StringIO
from tempfile import mkdtemp, mkstemp
from typing import ClassVar
from unittest.mock import patch

import responses
from mediafile import Image, MediaFile

import beets
import beets.plugins
from beets import autotag, config, importer, logging, util
from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.library import Album, Item, Library
from beets.test import _common
from beets.ui.commands import TerminalImportSession
from beets.util import (
    MoveOperation,
    bytestring_path,
    clean_module_tempdir,
    syspath,
)


class LogCapture(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.messages = []

    def emit(self, record):
        self.messages.append(str(record.msg))


@contextmanager
def capture_log(logger="beets"):
    capture = LogCapture()
    log = logging.getLogger(logger)
    log.addHandler(capture)
    try:
        yield capture.messages
    finally:
        log.removeHandler(capture)


@contextmanager
def control_stdin(input=None):
    """Sends ``input`` to stdin.

    >>> with control_stdin('yes'):
    ...     input()
    'yes'
    """
    org = sys.stdin
    sys.stdin = StringIO(input)
    try:
        yield sys.stdin
    finally:
        sys.stdin = org


@contextmanager
def capture_stdout():
    """Save stdout in a StringIO.

    >>> with capture_stdout() as output:
    ...     print('spam')
    ...
    >>> output.getvalue()
    'spam'
    """
    org = sys.stdout
    sys.stdout = capture = StringIO()
    try:
        yield sys.stdout
    finally:
        sys.stdout = org
        print(capture.getvalue())


def _convert_args(args):
    """Convert args to bytestrings for Python 2 and convert them to strings
    on Python 3.
    """
    for i, elem in enumerate(args):
        if isinstance(elem, bytes):
            args[i] = elem.decode(util.arg_encoding())

    return args


def has_program(cmd, args=["--version"]):
    """Returns `True` if `cmd` can be executed."""
    full_cmd = _convert_args([cmd] + args)
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


class TestHelper(_common.Assertions):
    """Helper mixin for high-level cli and plugin tests.

    This mixin provides methods to isolate beets' global state provide
    fixtures.
    """

    # TODO automate teardown through hook registration

    def setup_beets(self, disk=False):
        """Setup pristine global configuration and library for testing.

        Sets ``beets.config`` so we can safely use any functionality
        that uses the global configuration.  All paths used are
        contained in a temporary directory

        Sets the following properties on itself.

        - ``temp_dir`` Path to a temporary directory containing all
          files specific to beets

        - ``libdir`` Path to a subfolder of ``temp_dir``, containing the
          library's media files. Same as ``config['directory']``.

        - ``config`` The global configuration used by beets.

        - ``lib`` Library instance created with the settings from
          ``config``.

        Make sure you call ``teardown_beets()`` afterwards.
        """
        self.create_temp_dir()
        temp_dir_str = os.fsdecode(self.temp_dir)
        self.env_patcher = patch.dict(
            "os.environ",
            {
                "BEETSDIR": temp_dir_str,
                "HOME": temp_dir_str,  # used by Confuse to create directories.
            },
        )
        self.env_patcher.start()

        self.config = beets.config
        self.config.sources = []
        self.config.read(user=False, defaults=True)

        self.config["plugins"] = []
        self.config["verbose"] = 1
        self.config["ui"]["color"] = False
        self.config["threaded"] = False

        self.libdir = os.path.join(self.temp_dir, b"libdir")
        os.mkdir(syspath(self.libdir))
        self.config["directory"] = os.fsdecode(self.libdir)

        if disk:
            dbpath = util.bytestring_path(self.config["library"].as_filename())
        else:
            dbpath = ":memory:"
        self.lib = Library(dbpath, self.libdir)

        # Initialize, but don't install, a DummyIO.
        self.io = _common.DummyIO()

    def teardown_beets(self):
        self.env_patcher.stop()
        self.io.restore()
        self.lib._close()
        self.remove_temp_dir()
        beets.config.clear()
        beets.config._materialized = False

    def load_plugins(self, *plugins):
        """Load and initialize plugins by names.

        Similar setting a list of plugins in the configuration. Make
        sure you call ``unload_plugins()`` afterwards.
        """
        # FIXME this should eventually be handled by a plugin manager
        beets.config["plugins"] = plugins
        beets.plugins.load_plugins(plugins)
        beets.plugins.find_plugins()

        # Take a backup of the original _types and _queries to restore
        # when unloading.
        Item._original_types = dict(Item._types)
        Album._original_types = dict(Album._types)
        Item._types.update(beets.plugins.types(Item))
        Album._types.update(beets.plugins.types(Album))

        Item._original_queries = dict(Item._queries)
        Album._original_queries = dict(Album._queries)
        Item._queries.update(beets.plugins.named_queries(Item))
        Album._queries.update(beets.plugins.named_queries(Album))

    def unload_plugins(self):
        """Unload all plugins and remove the from the configuration."""
        # FIXME this should eventually be handled by a plugin manager
        beets.config["plugins"] = []
        beets.plugins._classes = set()
        beets.plugins._instances = {}
        Item._types = Item._original_types
        Album._types = Album._original_types
        Item._queries = Item._original_queries
        Album._queries = Album._original_queries

    def create_importer(self, item_count=1, album_count=1):
        """Create files to import and return corresponding session.

        Copies the specified number of files to a subdirectory of
        `self.temp_dir` and creates a `ImportSessionFixture` for this path.
        """
        import_dir = os.path.join(self.temp_dir, b"import")
        if not os.path.isdir(syspath(import_dir)):
            os.mkdir(syspath(import_dir))

        album_no = 0
        while album_count:
            album = util.bytestring_path(f"album {album_no}")
            album_dir = os.path.join(import_dir, album)
            if os.path.exists(syspath(album_dir)):
                album_no += 1
                continue
            os.mkdir(syspath(album_dir))
            album_count -= 1

            track_no = 0
            album_item_count = item_count
            while album_item_count:
                title = f"track {track_no}"
                src = os.path.join(_common.RSRC, b"full.mp3")
                title_file = util.bytestring_path(f"{title}.mp3")
                dest = os.path.join(album_dir, title_file)
                if os.path.exists(syspath(dest)):
                    track_no += 1
                    continue
                album_item_count -= 1
                shutil.copy(syspath(src), syspath(dest))
                mediafile = MediaFile(dest)
                mediafile.update(
                    {
                        "artist": "artist",
                        "albumartist": "album artist",
                        "title": title,
                        "album": album,
                        "mb_albumid": None,
                        "mb_trackid": None,
                    }
                )
                mediafile.save()

        config["import"]["quiet"] = True
        config["import"]["autotag"] = False
        config["import"]["resume"] = False

        return ImportSessionFixture(
            self.lib, loghandler=None, query=None, paths=[import_dir]
        )

    # Library fixtures methods

    def create_item(self, **values):
        """Return an `Item` instance with sensible default values.

        The item receives its attributes from `**values` paratmeter. The
        `title`, `artist`, `album`, `track`, `format` and `path`
        attributes have defaults if they are not given as parameters.
        The `title` attribute is formatted with a running item count to
        prevent duplicates. The default for the `path` attribute
        respects the `format` value.

        The item is attached to the database from `self.lib`.
        """
        item_count = self._get_item_count()
        values_ = {
            "title": "t\u00eftle {0}",
            "artist": "the \u00e4rtist",
            "album": "the \u00e4lbum",
            "track": item_count,
            "format": "MP3",
        }
        values_.update(values)
        values_["title"] = values_["title"].format(item_count)
        values_["db"] = self.lib
        item = Item(**values_)
        if "path" not in values:
            item["path"] = "audio." + item["format"].lower()
        # mtime needs to be set last since other assignments reset it.
        item.mtime = 12345
        return item

    def add_item(self, **values):
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

    def add_item_fixture(self, **values):
        """Add an item with an actual audio file to the library."""
        item = self.create_item(**values)
        extension = item["format"].lower()
        item["path"] = os.path.join(
            _common.RSRC, util.bytestring_path("min." + extension)
        )
        item.add(self.lib)
        item.move(operation=MoveOperation.COPY)
        item.store()
        return item

    def add_album(self, **values):
        item = self.add_item(**values)
        return self.lib.add_album([item])

    def add_item_fixtures(self, ext="mp3", count=1):
        """Add a number of items with files to the database."""
        # TODO base this on `add_item()`
        items = []
        path = os.path.join(_common.RSRC, util.bytestring_path("full." + ext))
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
        track_count=1,
        fname="full",
        ext="mp3",
        disc_count=1,
    ):
        """Add an album with files to the database."""
        items = []
        path = os.path.join(
            _common.RSRC,
            util.bytestring_path(f"{fname}.{ext}"),
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

    def create_mediafile_fixture(self, ext="mp3", images=[]):
        """Copy a fixture mediafile with the extension to `temp_dir`.

        `images` is a subset of 'png', 'jpg', and 'tiff'. For each
        specified extension a cover art image is added to the media
        file.
        """
        src = os.path.join(_common.RSRC, util.bytestring_path("full." + ext))
        handle, path = mkstemp(dir=self.temp_dir)
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

    def _get_item_count(self):
        if not hasattr(self, "__item_count"):
            count = 0
        self.__item_count = count + 1
        return count

    # Running beets commands

    def run_command(self, *args, **kwargs):
        """Run a beets command with an arbitrary amount of arguments. The
        Library` defaults to `self.lib`, but can be overridden with
        the keyword argument `lib`.
        """
        sys.argv = ["beet"]  # avoid leakage from test suite args
        lib = None
        if hasattr(self, "lib"):
            lib = self.lib
        lib = kwargs.get("lib", lib)
        beets.ui._raw_main(_convert_args(list(args)), lib)

    def run_with_output(self, *args):
        with capture_stdout() as out:
            self.run_command(*args)
        return out.getvalue()

    # Safe file operations

    def create_temp_dir(self):
        """Create a temporary directory and assign it into
        `self.temp_dir`. Call `remove_temp_dir` later to delete it.
        """
        temp_dir = mkdtemp()
        self.temp_dir = util.bytestring_path(temp_dir)

    def remove_temp_dir(self):
        """Delete the temporary directory created by `create_temp_dir`."""
        shutil.rmtree(syspath(self.temp_dir))

    def touch(self, path, dir=None, content=""):
        """Create a file at `path` with given content.

        If `dir` is given, it is prepended to `path`. After that, if the
        path is relative, it is resolved with respect to
        `self.temp_dir`.
        """
        if dir:
            path = os.path.join(dir, path)

        if not os.path.isabs(path):
            path = os.path.join(self.temp_dir, path)

        parent = os.path.dirname(path)
        if not os.path.isdir(syspath(parent)):
            os.makedirs(syspath(parent))

        with open(syspath(path), "a+") as f:
            f.write(content)
        return path


# A test harness for all beets tests.
# Provides temporary, isolated configuration.
class BeetsTestCase(unittest.TestCase, TestHelper):
    """A unittest.TestCase subclass that saves and restores beets'
    global configuration. This allows tests to make temporary
    modifications that will then be automatically removed when the test
    completes. Also provides some additional assertion methods, a
    temporary directory, and a DummyIO.
    """

    def setUp(self):
        self.setup_beets()

    def tearDown(self):
        self.teardown_beets()


class LibTestCase(BeetsTestCase):
    """A test case that includes an in-memory library object (`lib`) and
    an item added to the library (`i`).
    """

    def setUp(self):
        super().setUp()
        self.lib = beets.library.Library(":memory:")
        self.i = _common.item(self.lib)

    def tearDown(self):
        self.lib._connection().close()
        super().tearDown()


class ImportHelper(TestHelper):
    """Provides tools to setup a library, a directory containing files that are
    to be imported and an import session. The class also provides stubs for the
    autotagging library and several assertions for the library.
    """

    def setup_beets(self, disk=False):
        super().setup_beets(disk)
        self.lib.path_formats = [
            ("default", os.path.join("$artist", "$album", "$title")),
            ("singleton:true", os.path.join("singletons", "$title")),
            ("comp:true", os.path.join("compilations", "$album", "$title")),
        ]

    def _create_import_dir(self, count=3):
        """Creates a directory with media files to import.
        Sets ``self.import_dir`` to the path of the directory. Also sets
        ``self.import_media`` to a list :class:`MediaFile` for all the files in
        the directory.

        The directory has following layout
          the_album/
            track_1.mp3
            track_2.mp3
            track_3.mp3

        :param count:  Number of files to create
        """
        self.import_dir = os.path.join(self.temp_dir, b"testsrcdir")
        if os.path.isdir(syspath(self.import_dir)):
            shutil.rmtree(syspath(self.import_dir))

        album_path = os.path.join(self.import_dir, b"the_album")
        os.makedirs(syspath(album_path))

        resource_path = os.path.join(_common.RSRC, b"full.mp3")

        metadata = {
            "artist": "Tag Artist",
            "album": "Tag Album",
            "albumartist": None,
            "mb_trackid": None,
            "mb_albumid": None,
            "comp": None,
        }
        self.media_files = []
        for i in range(count):
            # Copy files
            medium_path = os.path.join(
                album_path, bytestring_path("track_%d.mp3" % (i + 1))
            )
            shutil.copy(syspath(resource_path), syspath(medium_path))
            medium = MediaFile(medium_path)

            # Set metadata
            metadata["track"] = i + 1
            metadata["title"] = "Tag Title %d" % (i + 1)
            for attr in metadata:
                setattr(medium, attr, metadata[attr])
            medium.save()
            self.media_files.append(medium)
        self.import_media = self.media_files

    def _setup_import_session(
        self,
        import_dir=None,
        delete=False,
        threaded=False,
        copy=True,
        singletons=False,
        move=False,
        autotag=True,
        link=False,
        hardlink=False,
    ):
        config["import"]["copy"] = copy
        config["import"]["delete"] = delete
        config["import"]["timid"] = True
        config["threaded"] = False
        config["import"]["singletons"] = singletons
        config["import"]["move"] = move
        config["import"]["autotag"] = autotag
        config["import"]["resume"] = False
        config["import"]["link"] = link
        config["import"]["hardlink"] = hardlink

        self.importer = ImportSessionFixture(
            self.lib,
            loghandler=None,
            query=None,
            paths=[import_dir or self.import_dir],
        )

    def assert_file_in_lib(self, *segments):
        """Join the ``segments`` and assert that this path exists in the
        library directory.
        """
        self.assertExists(os.path.join(self.libdir, *segments))

    def assert_file_not_in_lib(self, *segments):
        """Join the ``segments`` and assert that this path does not
        exist in the library directory.
        """
        self.assertNotExists(os.path.join(self.libdir, *segments))

    def assert_lib_dir_empty(self):
        self.assertEqual(len(os.listdir(syspath(self.libdir))), 0)


class ImportSessionFixture(importer.ImportSession):
    """ImportSession that can be controlled programaticaly.

    >>> lib = Library(':memory:')
    >>> importer = ImportSessionFixture(lib, paths=['/path/to/import'])
    >>> importer.add_choice(importer.action.SKIP)
    >>> importer.add_choice(importer.action.ASIS)
    >>> importer.default_choice = importer.action.APPLY
    >>> importer.run()

    This imports ``/path/to/import`` into `lib`. It skips the first
    album and imports thesecond one with metadata from the tags. For the
    remaining albums, the metadata from the autotagger will be applied.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._choices = []
        self._resolutions = []

    default_choice = importer.action.APPLY

    def add_choice(self, choice):
        self._choices.append(choice)

    def clear_choices(self):
        self._choices = []

    def choose_match(self, task):
        try:
            choice = self._choices.pop(0)
        except IndexError:
            choice = self.default_choice

        if choice == importer.action.APPLY:
            return task.candidates[0]
        elif isinstance(choice, int):
            return task.candidates[choice - 1]
        else:
            return choice

    choose_item = choose_match

    Resolution = Enum("Resolution", "REMOVE SKIP KEEPBOTH MERGE")

    default_resolution = "REMOVE"

    def add_resolution(self, resolution):
        assert isinstance(resolution, self.Resolution)
        self._resolutions.append(resolution)

    def resolve_duplicate(self, task, found_duplicates):
        try:
            res = self._resolutions.pop(0)
        except IndexError:
            res = self.default_resolution

        if res == self.Resolution.SKIP:
            task.set_choice(importer.action.SKIP)
        elif res == self.Resolution.REMOVE:
            task.should_remove_duplicates = True
        elif res == self.Resolution.MERGE:
            task.should_merge_duplicates = True


class TerminalImportSessionFixture(TerminalImportSession):
    def __init__(self, *args, **kwargs):
        self.io = kwargs.pop("io")
        super().__init__(*args, **kwargs)
        self._choices = []

    default_choice = importer.action.APPLY

    def add_choice(self, choice):
        self._choices.append(choice)

    def clear_choices(self):
        self._choices = []

    def choose_match(self, task):
        self._add_choice_input()
        return super().choose_match(task)

    def choose_item(self, task):
        self._add_choice_input()
        return super().choose_item(task)

    def _add_choice_input(self):
        try:
            choice = self._choices.pop(0)
        except IndexError:
            choice = self.default_choice

        if choice == importer.action.APPLY:
            self.io.addinput("A")
        elif choice == importer.action.ASIS:
            self.io.addinput("U")
        elif choice == importer.action.ALBUMS:
            self.io.addinput("G")
        elif choice == importer.action.TRACKS:
            self.io.addinput("T")
        elif choice == importer.action.SKIP:
            self.io.addinput("S")
        elif isinstance(choice, int):
            self.io.addinput("M")
            self.io.addinput(str(choice))
            self._add_choice_input()
        else:
            raise Exception("Unknown choice %s" % choice)


class TerminalImportSessionSetup:
    """Overwrites ImportHelper._setup_import_session to provide a terminal importer"""

    def _setup_import_session(
        self,
        import_dir=None,
        delete=False,
        threaded=False,
        copy=True,
        singletons=False,
        move=False,
        autotag=True,
    ):
        config["import"]["copy"] = copy
        config["import"]["delete"] = delete
        config["import"]["timid"] = True
        config["threaded"] = False
        config["import"]["singletons"] = singletons
        config["import"]["move"] = move
        config["import"]["autotag"] = autotag
        config["import"]["resume"] = False

        if not hasattr(self, "io"):
            self.io = _common.DummyIO()
        self.io.install()
        self.importer = TerminalImportSessionFixture(
            self.lib,
            loghandler=None,
            query=None,
            io=self.io,
            paths=[import_dir or self.import_dir],
        )


def generate_album_info(album_id, track_values):
    """Return `AlbumInfo` populated with mock data.

    Sets the album info's `album_id` field is set to the corresponding
    argument. For each pair (`id`, `values`) in `track_values` the `TrackInfo`
    from `generate_track_info` is added to the album info's `tracks` field.
    Most other fields of the album and track info are set to "album
    info" and "track info", respectively.
    """
    tracks = [generate_track_info(id, values) for id, values in track_values]
    album = AlbumInfo(
        album_id="album info",
        album="album info",
        artist="album info",
        artist_id="album info",
        tracks=tracks,
    )
    for field in ALBUM_INFO_FIELDS:
        setattr(album, field, "album info")

    return album


ALBUM_INFO_FIELDS = [
    "album",
    "album_id",
    "artist",
    "artist_id",
    "asin",
    "albumtype",
    "va",
    "label",
    "barcode",
    "artist_sort",
    "releasegroup_id",
    "catalognum",
    "language",
    "country",
    "albumstatus",
    "media",
    "albumdisambig",
    "releasegroupdisambig",
    "artist_credit",
    "data_source",
    "data_url",
]


def generate_track_info(track_id="track info", values={}):
    """Return `TrackInfo` populated with mock data.

    The `track_id` field is set to the corresponding argument. All other
    string fields are set to "track info".
    """
    track = TrackInfo(
        title="track info",
        track_id=track_id,
    )
    for field in TRACK_INFO_FIELDS:
        setattr(track, field, "track info")
    for field, value in values.items():
        setattr(track, field, value)
    return track


TRACK_INFO_FIELDS = [
    "artist",
    "artist_id",
    "artist_sort",
    "disctitle",
    "artist_credit",
    "data_source",
    "data_url",
]


class AutotagStub:
    """Stub out MusicBrainz album and track matcher and control what the
    autotagger returns.
    """

    NONE = "NONE"
    IDENT = "IDENT"
    GOOD = "GOOD"
    BAD = "BAD"
    MISSING = "MISSING"
    """Generate an album match for all but one track
    """

    length = 2
    matching = IDENT

    def install(self):
        self.mb_match_album = autotag.mb.match_album
        self.mb_match_track = autotag.mb.match_track
        self.mb_album_for_id = autotag.mb.album_for_id
        self.mb_track_for_id = autotag.mb.track_for_id

        autotag.mb.match_album = self.match_album
        autotag.mb.match_track = self.match_track
        autotag.mb.album_for_id = self.album_for_id
        autotag.mb.track_for_id = self.track_for_id

        return self

    def restore(self):
        autotag.mb.match_album = self.mb_match_album
        autotag.mb.match_track = self.mb_match_track
        autotag.mb.album_for_id = self.mb_album_for_id
        autotag.mb.track_for_id = self.mb_track_for_id

    def match_album(self, albumartist, album, tracks, extra_tags):
        if self.matching == self.IDENT:
            yield self._make_album_match(albumartist, album, tracks)

        elif self.matching == self.GOOD:
            for i in range(self.length):
                yield self._make_album_match(albumartist, album, tracks, i)

        elif self.matching == self.BAD:
            for i in range(self.length):
                yield self._make_album_match(albumartist, album, tracks, i + 1)

        elif self.matching == self.MISSING:
            yield self._make_album_match(albumartist, album, tracks, missing=1)

    def match_track(self, artist, title):
        yield TrackInfo(
            title=title.replace("Tag", "Applied"),
            track_id="trackid",
            artist=artist.replace("Tag", "Applied"),
            artist_id="artistid",
            length=1,
            index=0,
        )

    def album_for_id(self, mbid):
        return None

    def track_for_id(self, mbid):
        return None

    def _make_track_match(self, artist, album, number):
        return TrackInfo(
            title="Applied Title %d" % number,
            track_id="match %d" % number,
            artist=artist,
            length=1,
            index=0,
        )

    def _make_album_match(self, artist, album, tracks, distance=0, missing=0):
        if distance:
            id = " " + "M" * distance
        else:
            id = ""
        if artist is None:
            artist = "Various Artists"
        else:
            artist = artist.replace("Tag", "Applied") + id
        album = album.replace("Tag", "Applied") + id

        track_infos = []
        for i in range(tracks - missing):
            track_infos.append(self._make_track_match(artist, album, i + 1))

        return AlbumInfo(
            artist=artist,
            album=album,
            tracks=track_infos,
            va=False,
            album_id="albumid" + id,
            artist_id="artistid" + id,
            albumtype="soundtrack",
            data_source="match_source",
        )


class FetchImageHelper:
    """Helper mixin for mocking requests when fetching images
    with remote art sources.
    """

    @responses.activate
    def run(self, *args, **kwargs):
        super().run(*args, **kwargs)

    IMAGEHEADER = {
        "image/jpeg": b"\x00" * 6 + b"JFIF",
        "image/png": b"\211PNG\r\n\032\n",
    }

    def mock_response(self, url, content_type="image/jpeg", file_type=None):
        if file_type is None:
            file_type = content_type
        responses.add(
            responses.GET,
            url,
            content_type=content_type,
            # imghdr reads 32 bytes
            body=self.IMAGEHEADER.get(file_type, b"").ljust(32, b"\x00"),
        )


class CleanupModulesMixin:
    modules: ClassVar[tuple[str, ...]]

    @classmethod
    def tearDownClass(cls) -> None:
        """Remove files created by the plugin."""
        for module in cls.modules:
            clean_module_tempdir(module)
