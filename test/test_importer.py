"""Tests for the general importer functionality."""

from __future__ import annotations

import os
import re
import shutil
import stat
import sys
import unicodedata
import unittest
from functools import cached_property
from io import StringIO
from pathlib import Path
from tarfile import TarFile
from tempfile import mkstemp
from typing import Literal
from unittest.mock import Mock, patch
from zipfile import ZipFile

import pytest
from mediafile import MediaFile

from beets import config, importer, logging, util
from beets.autotag import AlbumInfo, AlbumMatch, Distance, TrackInfo
from beets.importer.tasks import albums_in_dir
from beets.test import _common
from beets.test.helper import (
    NEEDS_FFPROBE,
    NEEDS_REFLINK,
    AsIsImporterMixin,
    AutotagImportHelper,
    AutotagImportTestCase,
    AutotagStub,
    BeetsTestCase,
    ImportHelper,
    PluginMixin,
    TestHelper,
    has_program,
)
from beets.util import bytestring_path, syspath
from beets.util.extension import remux_mpeglayer3_wav


class PathsMixin:
    import_media: list[MediaFile]

    @cached_property
    def track_import_path(self) -> Path:
        return Path(self.import_media[0].path)

    @cached_property
    def album_path(self) -> Path:
        return self.track_import_path.parent

    @cached_property
    def track_lib_path(self):
        return self.lib_path / "Tag Artist" / "Tag Album" / "Tag Track 1.mp3"


class TestNonAutotaggedImport(PathsMixin, AsIsImporterMixin, ImportHelper):
    db_on_disk = True

    def test_album_created_with_track_artist(self):
        self.run_asis_importer()

        albums = self.lib.albums()
        assert len(albums) == 1
        assert albums[0].albumartist == "Tag Artist"

    def test_import_copy_arrives(self):
        self.run_asis_importer()

        assert self.track_lib_path.exists()

    def test_threaded_import_copy_arrives(self):
        config["threaded"] = True

        self.run_asis_importer()
        assert self.track_lib_path.exists()

    def test_import_with_move_deletes_import_files(self):
        assert self.album_path.exists()
        assert self.track_import_path.exists()
        (self.album_path / "alog.log").touch()
        config["clutter"] = ["*.log"]

        self.run_asis_importer(move=True)

        assert not self.track_import_path.exists()
        assert not self.album_path.exists()

    def test_threaded_import_move_arrives(self):
        self.run_asis_importer(move=True, threaded=True)

        assert self.track_lib_path.exists()
        assert not self.track_import_path.exists()

    def test_import_without_delete_retains_files(self):
        self.run_asis_importer(delete=False)

        assert self.track_import_path.exists()

    def test_import_with_delete_removes_files(self):
        self.run_asis_importer(delete=True)

        assert not self.album_path.exists()
        assert not self.track_import_path.exists()

    def test_album_mb_albumartistids(self):
        self.run_asis_importer()
        album = self.lib.albums()[0]
        assert album.mb_albumartistids == album.items()[0].mb_albumartistids

    @pytest.mark.skipif(not _common.HAVE_SYMLINK, reason="need symlinks")
    def test_import_link_arrives(self):
        self.run_asis_importer(link=True)

        assert self.track_lib_path.exists()
        assert self.track_lib_path.is_symlink()
        assert self.track_lib_path.resolve() == self.track_import_path.resolve()

    @pytest.mark.skipif(not _common.HAVE_HARDLINK, reason="need hardlinks")
    def test_import_hardlink_arrives(self):
        self.run_asis_importer(hardlink=True)

        assert self.track_lib_path.exists()
        media_stat = self.track_import_path.stat()
        lib_media_stat = self.track_lib_path.stat()
        assert media_stat[stat.ST_INO] == lib_media_stat[stat.ST_INO]
        assert media_stat[stat.ST_DEV] == lib_media_stat[stat.ST_DEV]

    @NEEDS_REFLINK
    def test_import_reflink_arrives(self):
        # Detecting reflinks is currently tricky due to various fs
        # implementations, we'll just check the file exists.
        self.run_asis_importer(reflink=True)

        assert self.track_lib_path.exists()

    def test_import_reflink_auto_arrives(self):
        # Should pass regardless of reflink support due to fallback.
        self.run_asis_importer(reflink="auto")

        assert self.track_lib_path.exists()


def create_archive(session):
    handle, path = mkstemp(dir=session.temp_path)
    path = bytestring_path(path)
    os.close(handle)
    archive = ZipFile(os.fsdecode(path), mode="w")
    archive.write(syspath(_common.RSRC / "full.mp3"), "full.mp3")
    archive.close()
    return bytestring_path(path)


class TestRmTemp(TestHelper):
    """Tests that temporarily extracted archives are properly removed
    after usage.
    """

    def setup_beets(self):
        super().setup_beets()
        self.want_resume = False
        self.config["incremental"] = False
        self.config["copy"] = False
        self.config["move"] = False
        self.config["delete"] = False
        self._old_home = None

    def test_rm(self):
        zip_path = create_archive(self)
        archive_task = importer.ArchiveImportTask(zip_path)
        archive_task.extract()
        tmp_path = Path(os.fsdecode(archive_task.toppath))
        assert tmp_path.exists()
        archive_task.finalize(self)
        assert not tmp_path.exists()

    def test_archive_removed_on_move_complete(self):
        zip_path = create_archive(self)
        archive_task = importer.ArchiveImportTask(zip_path)
        archive_task.extract()
        for root, _, files in os.walk(syspath(archive_task.toppath)):
            for f in files:
                os.remove(os.path.join(root, f))
        assert Path(os.fsdecode(zip_path)).exists()
        archive_task.cleanup(move=True)
        assert not Path(os.fsdecode(zip_path)).exists()

    def test_archive_preserved_on_move_partial(self):
        zip_path = create_archive(self)
        archive_task = importer.ArchiveImportTask(zip_path)
        archive_task.extract()
        archive_task.cleanup(move=True)
        assert Path(os.fsdecode(zip_path)).exists()

    def test_archive_preserved_on_copy(self):
        zip_path = create_archive(self)
        archive_task = importer.ArchiveImportTask(zip_path)
        archive_task.extract()
        archive_task.cleanup(copy=True)
        assert Path(os.fsdecode(zip_path)).exists()

    def test_tempdir_removed_in_all_modes(self):
        for cleanup_kwargs in (
            {},
            {"move": True},
            {"copy": True},
            {"copy": True, "delete": True},
        ):
            zip_path = create_archive(self)
            archive_task = importer.ArchiveImportTask(zip_path)
            archive_task.extract()
            tmp_path = Path(os.fsdecode(archive_task.toppath))
            assert tmp_path.exists(), f"extract failed for {cleanup_kwargs}"
            archive_task.cleanup(**cleanup_kwargs)
            assert not tmp_path.exists(), (
                f"tempdir {tmp_path} not removed for {cleanup_kwargs}"
            )


class TestImportZip(AsIsImporterMixin, ImportHelper):
    def test_import_zip(self):
        zip_path = create_archive(self)
        assert len(self.lib.items()) == 0
        assert len(self.lib.albums()) == 0

        self.run_asis_importer(import_dir=zip_path)
        assert len(self.lib.items()) == 1
        assert len(self.lib.albums()) == 1


class TestImportTar(TestImportZip):
    def create_archive(self):
        (handle, path) = mkstemp(dir=self.temp_path)
        path = bytestring_path(path)
        os.close(handle)
        archive = TarFile(os.fsdecode(path), mode="w")
        archive.add(syspath(_common.RSRC / "full.mp3"), "full.mp3")
        archive.close()
        return path


@pytest.mark.skipif(not has_program("unrar"), reason="unrar program not found")
class TestImportRar(TestImportZip):
    def create_archive(self):
        return _common.RSRC / "archive.rar"


class TestImport7z(TestImportZip):
    def create_archive(self):
        return _common.RSRC / "archive.7z"


@pytest.mark.skip(reason="Implement me!")
class TestImportPasswordRar(TestImportZip):
    def create_archive(self):
        return _common.RSRC / "password.rar"


class ImportSingletonTest(AutotagImportTestCase):
    """Test ``APPLY`` and ``ASIS`` choices for an import session with
    singletons config set to True.
    """

    def setUp(self):
        super().setUp()
        self.prepare_album_for_import(1)
        self.importer = self.setup_singleton_importer()

    def test_apply_asis_adds_only_singleton_track(self):
        self.importer.add_choice(importer.Action.ASIS)
        self.importer.run()

        # album not added
        assert not self.lib.albums()
        assert self.lib.items().get().title == "Tag Track 1"
        assert (self.lib_path / "singletons" / "Tag Track 1.mp3").exists()

    def test_apply_candidate_adds_track(self):
        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()

        assert not self.lib.albums()
        assert self.lib.items().get().title == "Applied Track 1"
        assert (self.lib_path / "singletons" / "Applied Track 1.mp3").exists()

    def test_apply_from_scratch_removes_other_metadata(self):
        config["import"]["from_scratch"] = True

        for mediafile in self.import_media:
            mediafile.comments = "Tag Comment"
            mediafile.save()

        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()
        assert self.lib.items().get().comments == ""

    def test_skip_does_not_add_track(self):
        self.importer.add_choice(importer.Action.SKIP)
        self.importer.run()

        assert not self.lib.items()

    def test_skip_first_add_second_asis(self):
        self.prepare_album_for_import(2)

        self.importer.add_choice(importer.Action.SKIP)
        self.importer.add_choice(importer.Action.ASIS)
        self.importer.run()

        assert len(self.lib.items()) == 1

    def test_import_single_files(self):
        resource_path = _common.RSRC / "empty.mp3"
        single_path = self.import_path / "track_2.mp3"

        util.copy(resource_path, single_path)
        import_files = [self.import_path / "album", single_path]
        self.setup_importer()
        self.importer.paths = list(map(os.fsencode, import_files))

        self.importer.add_choice(importer.Action.ASIS)
        self.importer.add_choice(importer.Action.ASIS)
        self.importer.run()

        assert len(self.lib.items()) == 2
        assert len(self.lib.albums()) == 2

    def test_set_fields(self):
        genres = ["\U0001f3b7 Jazz", "Rock"]
        collection = "To Listen"
        disc = 0

        config["import"]["set_fields"] = {
            "genres": "; ".join(genres),
            "collection": collection,
            "disc": disc,
            "title": "$title - formatted",
        }

        # As-is item import.
        assert self.lib.albums().get() is None
        self.importer.add_choice(importer.Action.ASIS)
        self.importer.run()

        for item in self.lib.items():
            item.load()  # TODO: Not sure this is necessary.
            assert item.genres == genres
            assert item.collection == collection
            assert item.title == "Tag Track 1 - formatted"
            assert item.disc == disc
            # Remove item from library to test again with APPLY choice.
            item.remove()

        # Autotagged.
        assert not self.lib.albums()
        self.importer.clear_choices()
        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()

        for item in self.lib.items():
            item.load()
            assert item.genres == genres
            assert item.collection == collection
            assert item.title == "Applied Track 1 - formatted"
            assert item.disc == disc


@pytest.mark.skipif(
    not has_program("ffprobe", ["-L"]),
    reason="need ffprobe for format recognition",
)
class TestImportFormat(ImportHelper):
    """Test fix_extension during import."""

    def test_recognize_format(self):
        resource_src = _common.RSRC / "no_ext"
        resource_path = self.import_path / "no_ext"
        util.copy(resource_src, resource_path)
        self.setup_importer(autotag=False)
        self.importer.paths = [os.fsencode(resource_path)]
        self.importer.run()
        assert self.lib.items().get().path.endswith(b".mp3")

    def test_recognize_format_already_exist(self, caplog):
        resource_path = _common.RSRC / "no_ext"
        temp_resource_path = self.temp_path / "no_ext"
        util.copy(resource_path, temp_resource_path)
        new_path = self.temp_path / "no_ext.mp3"
        util.copy(temp_resource_path, new_path)
        self.setup_importer(autotag=False)
        self.importer.paths = [os.fsencode(temp_resource_path)]
        with caplog.at_level("DEBUG"):
            self.importer.run()
        assert (
            "Import file with matching format to original target"
            in caplog.messages
        )
        assert self.lib.items().get().path.endswith(b".mp3")

    def test_recognize_format_not_music(self):
        resource_path = _common.RSRC / "no_ext_not_music"
        self.setup_importer(autotag=False)
        self.importer.paths = [os.fsencode(resource_path)]
        self.importer.run()
        assert len(self.lib.items()) == 0

    def test_recognize_format_change_original(self):
        config["import"]["fix_ext_inplace"] = True
        resource_src = _common.RSRC / "no_ext"
        resource_path = self.temp_path / "no_ext"
        util.copy(resource_src, resource_path)
        self.setup_importer(autotag=False)
        self.importer.paths = [os.fsencode(resource_path)]
        self.importer.run()
        assert not Path(self.temp_path / "no_ext").exists()

    def test_recognize_format_keep_original(self):
        config["import"]["fix_ext_inplace"] = False
        resource_src = _common.RSRC / "no_ext"
        resource_path = self.temp_path / "no_ext"
        util.copy(resource_src, resource_path)
        self.setup_importer(autotag=False)
        self.importer.paths = [os.fsencode(resource_path)]
        self.importer.run()
        assert Path(self.temp_path / "no_ext").exists()


class TestImport(PathsMixin, AutotagImportHelper):
    """Test APPLY, ASIS and SKIP choices."""

    def setup_beets(self):
        super().setup_beets()
        self.prepare_album_for_import(1)
        self.setup_importer()

    def test_asis_moves_album_and_track(self):
        self.importer.add_choice(importer.Action.ASIS)
        self.importer.run()

        assert self.lib.albums().get().album == "Tag Album"
        item = self.lib.items().get()
        assert item.title == "Tag Track 1"
        assert item.filepath.exists()

    def test_apply_moves_album_and_track(self):
        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()

        assert self.lib.albums().get().album == "Applied Album"
        item = self.lib.items().get()
        assert item.title == "Applied Track 1"
        assert item.filepath.exists()

    def test_apply_from_scratch_removes_other_metadata(self):
        config["import"]["from_scratch"] = True

        for mediafile in self.import_media:
            mediafile.genres = ["Tag Genre"]
            mediafile.save()

        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()
        assert not self.lib.items().get().genres

    def test_apply_from_scratch_keeps_format(self):
        config["import"]["from_scratch"] = True

        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()
        assert self.lib.items().get().format == "MP3"

    def test_apply_from_scratch_keeps_bitrate(self):
        config["import"]["from_scratch"] = True
        bitrate = 80000

        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()
        assert self.lib.items().get().bitrate == bitrate

    def test_apply_with_move_deletes_import(self):
        assert self.track_import_path.exists()

        config["import"]["move"] = True
        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()

        assert not self.track_import_path.exists()

    def test_apply_with_delete_deletes_import(self):
        assert self.track_import_path.exists()

        config["import"]["delete"] = True
        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()

        assert not self.track_import_path.exists()

    def test_skip_does_not_add_track(self):
        self.importer.add_choice(importer.Action.SKIP)
        self.importer.run()

        assert not self.lib.items()

    @NEEDS_FFPROBE
    def test_skip_non_album_dirs(self):
        assert (self.import_path / "album").exists()
        (self.import_path / "cruft").touch()
        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()

        assert len(self.lib.albums()) == 1

    def test_unmatched_tracks_not_added(self):
        self.prepare_album_for_import(2)
        self.matcher.matching = self.matcher.MISSING
        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()
        assert len(self.lib.items()) == 1

    @NEEDS_FFPROBE
    def test_empty_directory_warning(self, caplog):
        import_dir = self.temp_path / "empty"
        import_dir.mkdir()
        (import_dir / "non-audio").touch()
        self.setup_importer(import_dir=import_dir)
        with caplog.at_level("DEBUG"):
            self.importer.run()

        assert f"No files imported from {import_dir}" in caplog.messages

    @NEEDS_FFPROBE
    def test_empty_directory_singleton_warning(self, caplog):
        import_dir = self.temp_path / "empty"
        import_dir.mkdir()
        (import_dir / "non-audio").touch()
        self.setup_singleton_importer(import_dir=import_dir)
        with caplog.at_level("DEBUG"):
            self.importer.run()

        assert f"No files imported from {import_dir}" in caplog.messages

    def test_asis_no_data_source(self):
        assert self.lib.items().get() is None

        self.importer.add_choice(importer.Action.ASIS)
        self.importer.run()

        with pytest.raises(AttributeError):
            self.lib.items().get().data_source

    def test_set_fields(self):
        genres = ["\U0001f3b7 Jazz", "Rock"]
        collection = "To Listen"
        disc = 0
        comments = "managed by beets"

        config["import"]["set_fields"] = {
            "genres": "; ".join(genres),
            "collection": collection,
            "disc": disc,
            "comments": comments,
            "album": "$album - formatted",
        }

        # As-is album import.
        assert self.lib.albums().get() is None
        self.importer.add_choice(importer.Action.ASIS)
        self.importer.run()

        for album in self.lib.albums():
            assert album.genres == genres
            assert album.comments == comments
            for item in album.items():
                assert item.get("genres", with_album=False) == genres
                assert item.get("collection", with_album=False) == collection
                assert item.get("comments", with_album=False) == comments
                assert (
                    item.get("album", with_album=False)
                    == "Tag Album - formatted"
                )
                assert item.disc == disc
            # Remove album from library to test again with APPLY choice.
            album.remove()

        # Autotagged.
        assert self.lib.albums().get() is None
        self.importer.clear_choices()
        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()

        for album in self.lib.albums():
            assert album.genres == genres
            assert album.comments == comments
            for item in album.items():
                assert item.get("genres", with_album=False) == genres
                assert item.get("collection", with_album=False) == collection
                assert item.get("comments", with_album=False) == comments
                assert (
                    item.get("album", with_album=False)
                    == "Applied Album - formatted"
                )
                assert item.disc == disc


class ImportTracksTest(AutotagImportTestCase):
    """Test TRACKS and APPLY choice."""

    def setUp(self):
        super().setUp()
        self.prepare_album_for_import(1)
        self.setup_importer()

    def test_apply_tracks_adds_singleton_track(self):
        self.importer.add_choice(importer.Action.TRACKS)
        self.importer.add_choice(importer.Action.APPLY)
        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()

        assert self.lib.items().get().title == "Applied Track 1"
        assert not self.lib.albums()

    def test_apply_tracks_adds_singleton_path(self):
        self.importer.add_choice(importer.Action.TRACKS)
        self.importer.add_choice(importer.Action.APPLY)
        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()

        assert (self.lib_path / "singletons" / "Applied Track 1.mp3").exists()


class ImportCompilationTest(AutotagImportTestCase):
    """Test ASIS import of a folder containing tracks with different artists."""

    def setUp(self):
        super().setUp()
        self.prepare_album_for_import(3)
        self.setup_importer()

    def test_asis_homogenous_sets_albumartist(self):
        self.importer.add_choice(importer.Action.ASIS)
        self.importer.run()
        assert self.lib.albums().get().albumartist == "Tag Artist"
        for item in self.lib.items():
            assert item.albumartist == "Tag Artist"

    def test_asis_heterogenous_sets_various_albumartist(self):
        self.import_media[0].artist = "Other Artist"
        self.import_media[0].save()
        self.import_media[1].artist = "Another Artist"
        self.import_media[1].save()

        self.importer.add_choice(importer.Action.ASIS)
        self.importer.run()
        assert self.lib.albums().get().albumartist == "Various Artists"
        for item in self.lib.items():
            assert item.albumartist == "Various Artists"

    def test_asis_heterogenous_sets_compilation(self):
        self.import_media[0].artist = "Other Artist"
        self.import_media[0].save()
        self.import_media[1].artist = "Another Artist"
        self.import_media[1].save()

        self.importer.add_choice(importer.Action.ASIS)
        self.importer.run()
        for item in self.lib.items():
            assert item.comp

    def test_asis_sets_majority_albumartist(self):
        self.import_media[0].artist = "Other Artist"
        self.import_media[0].save()
        self.import_media[1].artist = "Other Artist"
        self.import_media[1].save()

        self.importer.add_choice(importer.Action.ASIS)
        self.importer.run()
        assert self.lib.albums().get().albumartist == "Other Artist"
        for item in self.lib.items():
            assert item.albumartist == "Other Artist"

    def test_asis_albumartist_tag_sets_albumartist(self):
        self.import_media[0].artist = "Other Artist"
        self.import_media[1].artist = "Another Artist"
        for mediafile in self.import_media:
            mediafile.albumartist = "Album Artist"
            mediafile.mb_albumartistid = "Album Artist ID"
            mediafile.save()

        self.importer.add_choice(importer.Action.ASIS)
        self.importer.run()
        assert self.lib.albums().get().albumartist == "Album Artist"
        assert self.lib.albums().get().mb_albumartistid == "Album Artist ID"
        for item in self.lib.items():
            assert item.albumartist == "Album Artist"
            assert item.mb_albumartistid == "Album Artist ID"

    def test_asis_albumartists_tag_sets_multi_albumartists(self):
        self.import_media[0].artist = "Other Artist"
        self.import_media[0].artists = ["Other Artist", "Other Artist 2"]
        self.import_media[1].artist = "Another Artist"
        self.import_media[1].artists = ["Another Artist", "Another Artist 2"]
        for mediafile in self.import_media:
            mediafile.albumartist = "Album Artist"
            mediafile.albumartists = ["Album Artist 1", "Album Artist 2"]
            mediafile.mb_albumartistid = "Album Artist ID"
            mediafile.save()

        self.importer.add_choice(importer.Action.ASIS)
        self.importer.run()
        assert self.lib.albums().get().albumartist == "Album Artist"
        assert self.lib.albums().get().albumartists == [
            "Album Artist 1",
            "Album Artist 2",
        ]
        assert self.lib.albums().get().mb_albumartistid == "Album Artist ID"

        # Make sure both custom media items get tested
        asserted_multi_artists_0 = False
        asserted_multi_artists_1 = False
        for item in self.lib.items():
            assert item.albumartist == "Album Artist"
            assert item.albumartists == ["Album Artist 1", "Album Artist 2"]
            assert item.mb_albumartistid == "Album Artist ID"

            if item.artist == "Other Artist":
                asserted_multi_artists_0 = True
                assert item.artists == ["Other Artist", "Other Artist 2"]
            if item.artist == "Another Artist":
                asserted_multi_artists_1 = True
                assert item.artists == ["Another Artist", "Another Artist 2"]

        assert asserted_multi_artists_0
        assert asserted_multi_artists_1


class ImportExistingTest(PathsMixin, AutotagImportTestCase):
    """Test importing files that are already in the library directory."""

    def setUp(self):
        super().setUp()
        self.prepare_album_for_import(1)

        self.reimporter = self.setup_importer(import_dir=self.lib_path)
        self.importer = self.setup_importer()

    def tearDown(self):
        super().tearDown()
        self.matcher.restore()

    @cached_property
    def applied_track_path(self) -> Path:
        return Path(str(self.track_lib_path).replace("Tag", "Applied"))

    def test_does_not_duplicate_item_nor_album(self):
        self.importer.run()
        assert len(self.lib.items()) == 1
        assert len(self.lib.albums()) == 1

        self.reimporter.add_choice(importer.Action.APPLY)
        self.reimporter.run()

        assert len(self.lib.items()) == 1
        assert len(self.lib.albums()) == 1

    def test_does_not_duplicate_singleton_track(self):
        self.importer.add_choice(importer.Action.TRACKS)
        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()
        assert len(self.lib.items()) == 1

        self.reimporter.add_choice(importer.Action.TRACKS)
        self.reimporter.add_choice(importer.Action.APPLY)
        self.reimporter.run()
        assert len(self.lib.items()) == 1

    def test_asis_updates_metadata_and_moves_file(self):
        self.importer.run()

        medium = MediaFile(self.lib.items().get().path)
        medium.title = "New Title"
        medium.save()

        self.reimporter.add_choice(importer.Action.ASIS)
        self.reimporter.run()

        assert self.lib.items().get().title == "New Title"
        assert not self.applied_track_path.exists()
        assert self.applied_track_path.with_name("New Title.mp3").exists()

    def test_asis_updated_without_copy_does_not_move_file(self):
        self.importer.run()
        medium = MediaFile(self.lib.items().get().path)
        medium.title = "New Title"
        medium.save()

        config["import"]["copy"] = False
        self.reimporter.add_choice(importer.Action.ASIS)
        self.reimporter.run()

        assert self.applied_track_path.exists()
        assert not self.applied_track_path.with_name("New Title.mp3").exists()

    def test_outside_file_is_copied(self):
        config["import"]["copy"] = False
        self.importer.run()
        assert self.lib.items().get().filepath == self.track_import_path

        self.reimporter = self.setup_importer()
        self.reimporter.add_choice(importer.Action.APPLY)
        self.reimporter.run()

        assert self.applied_track_path.exists()
        assert self.lib.items().get().filepath == self.applied_track_path


class GroupAlbumsImportTest(AutotagImportTestCase):
    matching = AutotagStub.NONE

    def setUp(self):
        super().setUp()
        self.prepare_album_for_import(3)
        self.setup_importer()

        # Split tracks into two albums and use both as-is
        self.importer.add_choice(importer.Action.ALBUMS)
        self.importer.add_choice(importer.Action.ASIS)
        self.importer.add_choice(importer.Action.ASIS)

    def test_add_album_for_different_artist_and_different_album(self):
        self.import_media[0].artist = "Artist B"
        self.import_media[0].album = "Album B"
        self.import_media[0].save()

        self.importer.run()
        albums = {album.album for album in self.lib.albums()}
        assert albums == {"Album B", "Tag Album"}

    def test_add_album_for_different_artist_and_same_albumartist(self):
        self.import_media[0].artist = "Artist B"
        self.import_media[0].albumartist = "Album Artist"
        self.import_media[0].save()
        self.import_media[1].artist = "Artist C"
        self.import_media[1].albumartist = "Album Artist"
        self.import_media[1].save()

        self.importer.run()
        artists = {album.albumartist for album in self.lib.albums()}
        assert artists == {"Album Artist", "Tag Artist"}

    def test_add_album_for_same_artist_and_different_album(self):
        self.import_media[0].album = "Album B"
        self.import_media[0].save()

        self.importer.run()
        albums = {album.album for album in self.lib.albums()}
        assert albums == {"Album B", "Tag Album"}

    def test_add_album_for_same_album_and_different_artist(self):
        self.import_media[0].artist = "Artist B"
        self.import_media[0].save()

        self.importer.run()
        artists = {album.albumartist for album in self.lib.albums()}
        assert artists == {"Artist B", "Tag Artist"}

    def test_incremental(self):
        config["import"]["incremental"] = True
        self.import_media[0].album = "Album B"
        self.import_media[0].save()

        self.importer.run()
        albums = {album.album for album in self.lib.albums()}
        assert albums == {"Album B", "Tag Album"}


class GlobalGroupAlbumsImportTest(GroupAlbumsImportTest):
    def setUp(self):
        super().setUp()
        self.importer.clear_choices()
        self.importer.default_choice = importer.Action.ASIS
        config["import"]["group_albums"] = True


class ChooseCandidateTest(AutotagImportTestCase):
    matching = AutotagStub.BAD

    def setUp(self):
        super().setUp()
        self.prepare_album_for_import(1)
        self.setup_importer()

    def test_choose_first_candidate(self):
        self.importer.add_choice(1)
        self.importer.run()
        assert self.lib.albums().get().album == "Applied Album M"

    def test_choose_second_candidate(self):
        self.importer.add_choice(2)
        self.importer.run()
        assert self.lib.albums().get().album == "Applied Album MM"


class InferAlbumDataTest(unittest.TestCase):
    def setUp(self):
        super().setUp()

        i1 = _common.item()
        i2 = _common.item()
        i3 = _common.item()
        i1.title = "first item"
        i2.title = "second item"
        i3.title = "third item"
        i1.comp = i2.comp = i3.comp = False
        i1.albumartist = i2.albumartist = i3.albumartist = ""
        i1.mb_albumartistid = i2.mb_albumartistid = i3.mb_albumartistid = ""
        self.items = [i1, i2, i3]

        self.task = importer.ImportTask(
            paths=["a path"], toppath="top path", items=self.items
        )

    def test_asis_homogenous_single_artist(self):
        self.task.set_choice(importer.Action.ASIS)
        self.task.align_album_level_fields()
        assert not self.items[0].comp
        assert self.items[0].albumartist == self.items[2].artist

    def test_asis_heterogenous_va(self):
        self.items[0].artist = "another artist"
        self.items[1].artist = "some other artist"
        self.task.set_choice(importer.Action.ASIS)

        self.task.align_album_level_fields()

        assert self.items[0].comp
        assert self.items[0].albumartist == "Various Artists"

    def test_asis_comp_applied_to_all_items(self):
        self.items[0].artist = "another artist"
        self.items[1].artist = "some other artist"
        self.task.set_choice(importer.Action.ASIS)

        self.task.align_album_level_fields()

        for item in self.items:
            assert item.comp
            assert item.albumartist == "Various Artists"

    def test_asis_majority_artist_single_artist(self):
        self.items[0].artist = "another artist"
        self.task.set_choice(importer.Action.ASIS)

        self.task.align_album_level_fields()

        assert not self.items[0].comp
        assert self.items[0].albumartist == self.items[2].artist

    def test_asis_track_albumartist_override(self):
        self.items[0].artist = "another artist"
        self.items[1].artist = "some other artist"
        for item in self.items:
            item.albumartist = "some album artist"
            item.mb_albumartistid = "some album artist id"
        self.task.set_choice(importer.Action.ASIS)

        self.task.align_album_level_fields()

        assert self.items[0].albumartist == "some album artist"
        assert self.items[0].mb_albumartistid == "some album artist id"

    def test_apply_gets_artist_and_id(self):
        self.task.set_choice(AlbumMatch(Distance(), None, {}))  # APPLY

        self.task.align_album_level_fields()

        assert self.items[0].albumartist == self.items[0].artist
        assert self.items[0].mb_albumartistid == self.items[0].mb_artistid

    def test_apply_lets_album_values_override(self):
        for item in self.items:
            item.albumartist = "some album artist"
            item.mb_albumartistid = "some album artist id"
        self.task.set_choice(AlbumMatch(Distance(), None, {}))  # APPLY

        self.task.align_album_level_fields()

        assert self.items[0].albumartist == "some album artist"
        assert self.items[0].mb_albumartistid == "some album artist id"

    def test_small_single_artist_album(self):
        self.items = [self.items[0]]
        self.task.items = self.items
        self.task.set_choice(importer.Action.ASIS)
        self.task.align_album_level_fields()
        assert not self.items[0].comp


def album_candidates_mock(*args, **kwargs):
    """Create an AlbumInfo object for testing."""
    yield AlbumInfo(
        artist="artist",
        album="album",
        tracks=[TrackInfo(title="new title", track_id="trackid", index=0)],
        album_id="albumid",
        artist_id="artistid",
        flex="flex",
    )


@patch(
    "beets.metadata_plugins.candidates", Mock(side_effect=album_candidates_mock)
)
class TestImportDuplicateAlbum(PluginMixin, ImportHelper):
    plugin = "musicbrainz"

    def setup_beets(self):
        super().setup_beets()
        # Original album
        self.add_album_fixture(albumartist="artist", album="album")

        # Create import session
        self.prepare_album_for_import(1)
        self.importer = self.setup_importer(
            duplicate_keys={"album": "albumartist album"}
        )

    def test_remove_duplicate_album(self):
        item = self.lib.items().get()
        assert item.title == "t\xeftle 0"
        assert item.filepath.exists()

        self.config["import"]["duplicate_action"] = "remove"
        self.importer.run()

        assert not item.filepath.exists()
        assert len(self.lib.albums()) == 1
        assert len(self.lib.items()) == 1
        item = self.lib.items().get()
        assert item.title == "new title"

    def test_remove_duplicate_album_deletes_art(self):
        album = self.lib.albums().get()
        art_source = _common.RSRC / "abbey.jpg"
        album.set_art(art_source)
        album.store()
        old_artpath = album.art_filepath

        assert old_artpath.exists()

        self.config["import"]["duplicate_action"] = "remove"
        self.importer.run()

        assert not old_artpath.exists()
        assert len(self.lib.albums()) == 1

    def test_no_autotag_removes_duplicate_album(self):
        config["import"]["autotag"] = False
        album = self.lib.albums().get()
        item = self.lib.items().get()
        assert item.title == "t\xeftle 0"
        assert item.filepath.exists()

        # Imported item has the same albumartist and album as the one in the
        # library album. We use album metadata (not item metadata) since
        # duplicate detection uses album-level fields.
        import_file = os.path.join(
            self.importer.paths[0], b"album", b"track_1.mp3"
        )
        import_file = MediaFile(import_file)
        import_file.artist = album.albumartist
        import_file.albumartist = album.albumartist
        import_file.album = album.album
        import_file.title = "new title"
        import_file.save()

        self.config["import"]["duplicate_action"] = "remove"
        self.importer.run()

        # Old duplicate should be removed, new one imported
        assert len(self.lib.albums()) == 1
        assert len(self.lib.items()) == 1
        # The new item should be in the library
        assert self.lib.items().get().title == "new title"

    def test_keep_duplicate_album(self):
        self.config["import"]["duplicate_action"] = "keep"
        self.importer.run()

        assert len(self.lib.albums()) == 2
        assert len(self.lib.items()) == 2

    def test_skip_duplicate_album(self):
        item = self.lib.items().get()
        assert item.title == "t\xeftle 0"

        self.config["import"]["duplicate_action"] = "skip"
        self.importer.run()

        assert len(self.lib.albums()) == 1
        assert len(self.lib.items()) == 1
        item = self.lib.items().get()
        assert item.title == "t\xeftle 0"

    def test_merge_duplicate_album(self):
        self.config["import"]["duplicate_action"] = "merge"
        self.importer.run()

        assert len(self.lib.albums()) == 1

    def test_twice_in_import_dir(self):
        pytest.skip(reason="write me")

    def test_keep_when_extra_key_is_different(self):
        config["import"]["duplicate_keys"]["album"] = "albumartist album flex"

        item = self.lib.items().get()
        import_file = MediaFile(
            os.path.join(self.importer.paths[0], b"album", b"track_1.mp3")
        )
        import_file.artist = item["artist"]
        import_file.albumartist = item["artist"]
        import_file.album = item["album"]
        import_file.title = item["title"]
        import_file.flex = "different"

        self.config["import"]["duplicate_action"] = "skip"
        self.importer.run()

        assert len(self.lib.albums()) == 2
        assert len(self.lib.items()) == 2

    def add_album_fixture(self, **kwargs):
        # TODO move this into upstream
        album = super().add_album_fixture()
        album.update(kwargs)
        album.store()
        return album


@patch(
    "beets.metadata_plugins.candidates", Mock(side_effect=album_candidates_mock)
)
class TestImportDuplicateAlbumThreaded(PluginMixin, ImportHelper):
    """Regression test for #6601: threaded merge must propagate context vars."""

    plugin = "musicbrainz"
    # Each thread gets its own connection; :memory: would give each thread an
    # empty DB, so we need a real file that all threads share.
    db_on_disk = True

    def setup_beets(self):
        super().setup_beets()
        self.add_album_fixture(albumartist="artist", album="album")
        self.prepare_album_for_import(1)
        self.importer = self.setup_importer(
            duplicate_keys={"album": "albumartist album"}
        )

    def add_album_fixture(self, **kwargs):
        album = super().add_album_fixture()
        album.update(kwargs)
        album.store()
        return album

    def test_merge_duplicate_album_threaded(self):
        self.config["threaded"] = True
        self.config["import"]["duplicate_action"] = "merge"
        self.importer.run()

        assert len(self.lib.albums()) == 1
        for item in self.lib.items():
            assert item.filepath.exists(), f"item path not found: {item.path}"

        # Without the fix, lost context vars cause relative paths to stay
        # unresolved, so items land in different (duplicate) directories.
        album_dirs = {item.filepath.parent for item in self.lib.items()}
        assert len(album_dirs) == 1, (
            f"expected single album dir, got {album_dirs}"
        )


def item_candidates_mock(*args, **kwargs):
    yield TrackInfo(
        artist="artist", title="title", track_id="new trackid", index=0
    )


@patch(
    "beets.metadata_plugins.item_candidates",
    Mock(side_effect=item_candidates_mock),
)
class TestImportDuplicateSingleton(ImportHelper):
    def setup_beets(self):
        super().setup_beets()
        # Original file in library
        self.add_item_fixture(
            artist="artist", title="title", mb_trackid="old trackid"
        )

        # Import session
        self.prepare_album_for_import(1)
        self.importer = self.setup_singleton_importer(
            duplicate_keys={"album": "artist title"}
        )

    def test_remove_duplicate(self):
        item = self.lib.items().get()
        assert item.mb_trackid == "old trackid"
        assert item.filepath.exists()

        self.config["import"]["duplicate_action"] = "remove"
        self.importer.run()

        assert not item.filepath.exists()
        assert len(self.lib.items()) == 1
        item = self.lib.items().get()
        assert item.mb_trackid == "new trackid"

    def test_keep_duplicate(self):
        assert len(self.lib.items()) == 1

        self.config["import"]["duplicate_action"] = "keep"
        self.importer.run()

        assert len(self.lib.items()) == 2

    def test_skip_duplicate(self):
        item = self.lib.items().get()
        assert item.mb_trackid == "old trackid"

        self.config["import"]["duplicate_action"] = "skip"
        self.importer.run()

        assert len(self.lib.items()) == 1
        item = self.lib.items().get()
        assert item.mb_trackid == "old trackid"

    def test_keep_when_extra_key_is_different(self):
        config["import"]["duplicate_keys"]["item"] = "artist title flex"
        item = self.lib.items().get()
        item.flex = "different"
        item.store()
        assert len(self.lib.items()) == 1

        self.config["import"]["duplicate_action"] = "skip"
        self.importer.run()

        assert len(self.lib.items()) == 2

    def test_no_autotag_removes_duplicate_singleton(self):
        config["import"]["autotag"] = False
        item = self.lib.items().get()
        assert item.mb_trackid == "old trackid"
        assert item.filepath.exists()

        # Imported item has the same artist and title as the one in the
        # library. We use item metadata since duplicate detection uses
        # item-level fields for singletons.
        import_file = os.path.join(
            self.importer.paths[0], b"album", b"track_1.mp3"
        )
        import_file = MediaFile(import_file)
        import_file.artist = item.artist
        import_file.title = item.title
        import_file.mb_trackid = "new trackid"
        import_file.save()

        self.config["import"]["duplicate_action"] = "remove"
        self.importer.run()

        # Old duplicate should be removed, new one imported
        assert len(self.lib.items()) == 1
        # The new item should be in the library
        assert self.lib.items().get().mb_trackid == "new trackid"

    def test_twice_in_import_dir(self):
        pytest.skip(reason="write me")

    def add_item_fixture(self, **kwargs):
        # Move this to TestHelper
        item = self.add_item_fixtures()[0]
        item.update(kwargs)
        item.store()
        return item


class TagLogTest(unittest.TestCase):
    def test_tag_log_line(self):
        sio = StringIO()
        handler = logging.StreamHandler(sio)
        session = _common.import_session(loghandler=handler)
        session.tag_log("status", "path")
        assert "status path" in sio.getvalue()

    def test_tag_log_unicode(self):
        sio = StringIO()
        handler = logging.StreamHandler(sio)
        session = _common.import_session(loghandler=handler)
        session.tag_log("status", "caf\xe9")  # send unicode
        assert "status caf\xe9" in sio.getvalue()


class TestResumeImport(ImportHelper):
    @patch("beets.plugins.send")
    def test_resume_album(self, plugins_send):
        self.prepare_albums_for_import(2)
        self.importer = self.setup_importer(autotag=False, resume=True)

        # Aborts import after one album. This also ensures that we skip
        # the first album in the second try.
        def raise_exception(event, **kwargs):
            if event == "album_imported":
                raise importer.ImportAbortError

        plugins_send.side_effect = raise_exception

        self.importer.run()
        assert len(self.lib.albums()) == 1
        assert self.lib.albums("album:'Album 1'").get() is not None

        self.importer.run()
        assert len(self.lib.albums()) == 2
        assert self.lib.albums("album:'Album 2'").get() is not None

    @patch("beets.plugins.send")
    def test_resume_singleton(self, plugins_send):
        self.prepare_album_for_import(2)
        self.importer = self.setup_singleton_importer(
            autotag=False, resume=True
        )

        # Aborts import after one track. This also ensures that we skip
        # the first album in the second try.
        def raise_exception(event, **kwargs):
            if event == "item_imported":
                raise importer.ImportAbortError

        plugins_send.side_effect = raise_exception

        self.importer.run()
        assert len(self.lib.items()) == 1
        assert self.lib.items("title:'Track 1'").get() is not None

        self.importer.run()
        assert len(self.lib.items()) == 2
        assert self.lib.items("title:'Track 1'").get() is not None


class TestIncrementalImport(AsIsImporterMixin, ImportHelper):
    def test_incremental_album(self):
        importer = self.run_asis_importer(incremental=True)

        # Change album name so the original file would be imported again
        # if incremental was off.
        album = self.lib.albums().get()
        album["album"] = "edited album"
        album.store()

        importer.run()
        assert len(self.lib.albums()) == 2

    def test_incremental_item(self):
        importer = self.run_asis_importer(incremental=True, singletons=True)

        # Change track name so the original file would be imported again
        # if incremental was off.
        item = self.lib.items().get()
        item["artist"] = "edited artist"
        item.store()

        importer.run()
        assert len(self.lib.items()) == 2

    def test_invalid_state_file(self):
        self.config["statefile"].as_path().write_bytes(b"000")
        self.run_asis_importer(incremental=True)
        assert len(self.lib.albums()) == 1


def _mkmp3(path):
    shutil.copyfile(syspath(_common.RSRC / "min.mp3"), syspath(path))


class AlbumsInDirTest(BeetsTestCase):
    def setUp(self):
        super().setUp()

        # create a directory structure for testing
        base = (self.temp_path / "tempdir").resolve()
        base.mkdir()

        album1_dir = base / "album1"
        album2_dir = base / "album2"
        album3_dir = base / "more" / "album3"
        album4_dir = base / "more" / "album4"
        album1_dir.mkdir()
        album2_dir.mkdir()
        album3_dir.mkdir(parents=True)
        album4_dir.mkdir(parents=True)

        _mkmp3(album1_dir / "album1song1.mp3")
        _mkmp3(album1_dir / "album1song2.mp3")
        _mkmp3(album2_dir / "album2song.mp3")
        _mkmp3(album3_dir / "album3song.mp3")
        _mkmp3(album4_dir / "album4song.mp3")
        self.base = str(base)

    def test_finds_all_albums(self):
        albums = list(albums_in_dir(self.base))
        assert len(albums) == 4

    def test_separates_contents(self):
        found = []
        for _, album in albums_in_dir(self.base):
            found.append(re.search(r"album(.)song", album[0]).group(1))
        assert "1" in found
        assert "2" in found
        assert "3" in found
        assert "4" in found

    def test_finds_multiple_songs(self):
        for _, album in albums_in_dir(self.base):
            n = re.search(r"album(.)song", album[0]).group(1)
            if n == "1":
                assert len(album) == 2
            else:
                assert len(album) == 1


class MultiDiscAlbumsInDirTest(BeetsTestCase):
    def create_music(self, files=True, ascii_=True):
        """Create some music in multiple album directories.

        `files` indicates whether to create the files (otherwise, only
        directories are made). `ascii_` indicates ACII-only filenames;
        otherwise, we use Unicode names.
        """
        self.base = (self.temp_path / "tempdir").resolve()
        self.base.mkdir()

        name = "CAT" if ascii_ else "C\xc1T"
        name_alt_case = "CAt" if ascii_ else "C\xc1t"

        self.dirs = [
            # Nested album, multiple subdirs.
            # Also, false positive marker in root dir, and subtitle for disc 3.
            self.base / "ABCD1234",
            self.base / "ABCD1234" / "cd 1",
            self.base / "ABCD1234" / "cd 3 - bonus",
            # Nested album, single subdir.
            # Also, punctuation between marker and disc number.
            self.base / "album",
            self.base / "album" / "cd _ 1",
            # Flattened album, case typo.
            # Also, false positive marker in parent dir.
            self.base / "artist [CD5]",
            self.base / "artist [CD5]" / f"{name} disc 1",
            self.base / "artist [CD5]" / f"{name_alt_case} disc 2",
            # Single disc album, sorted between CAT discs.
            self.base / "artist [CD5]" / f"{name} S",
        ]
        deep_dirs = [*self.dirs[:3], self.dirs[4], *self.dirs[6:]]
        self.files = [d / f"song{i}.mp3" for i, d in enumerate(deep_dirs)]

        if not ascii_:
            self.dirs = [self._normalize_path(p) for p in self.dirs]
            self.files = [self._normalize_path(p) for p in self.files]

        for path in self.dirs:
            path.mkdir()
        if files:
            for path in self.files:
                _mkmp3(syspath(path))

        self.dirs = list(map(str, self.dirs))
        self.files = list(map(str, self.files))
        self.base = str(self.base)

    def _normalize_path(self, path: Path) -> Path:
        """Normalize a path's Unicode combining form according to the
        platform.
        """
        norm_form: Literal["NFD", "NFC"] = (
            "NFD" if sys.platform == "darwin" else "NFC"
        )
        return Path(unicodedata.normalize(norm_form, str(path)))

    def test_coalesce_nested_album_multiple_subdirs(self):
        self.create_music()
        albums = list(albums_in_dir(self.base))
        assert len(albums) == 4
        root, items = albums[0]
        assert root == self.dirs[0:3]
        assert len(items) == 3

    def test_coalesce_nested_album_single_subdir(self):
        self.create_music()
        albums = list(albums_in_dir(self.base))
        root, items = albums[1]
        assert root == self.dirs[3:5]
        assert len(items) == 1

    def test_coalesce_flattened_album_case_typo(self):
        self.create_music()
        albums = list(albums_in_dir(self.base))
        root, items = albums[2]
        assert root == self.dirs[6:8]
        assert len(items) == 2

    def test_single_disc_album(self):
        self.create_music()
        albums = list(albums_in_dir(self.base))
        root, items = albums[3]
        assert root == self.dirs[8:]
        assert len(items) == 1

    def test_do_not_yield_empty_album(self):
        self.create_music(files=False)
        albums = list(albums_in_dir(self.base))
        assert len(albums) == 0

    def test_single_disc_unicode(self):
        self.create_music(ascii_=False)
        albums = list(albums_in_dir(self.base))
        root, items = albums[3]
        assert root == self.dirs[8:]
        assert len(items) == 1

    def test_coalesce_multiple_unicode(self):
        self.create_music(ascii_=False)
        albums = list(albums_in_dir(self.base))
        assert len(albums) == 4
        root, items = albums[0]
        assert root == self.dirs[0:3]
        assert len(items) == 3

    def test_coalesce_markers(self):
        for i, (marker, suffix1, suffix2) in enumerate(
            [
                ("Disc", " 1", " 02"),  # titlecase, space-separated
                ("disk 757", " 1", " 02"),  # lowercase, numerical suffix
                ("CD", "01", "02"),  # uppercase, no space (e.g. CD01)
                ("disc", "_1", "_2"),  # underscore separator (e.g. disc_1)
                ("cAsSeTtE", " 1", " 02"),  # mixed case
                ("Digital   Media", " 1", " 02"),  # multiple spaces
                ("vinyl", " 1", " 02"),  # lowercase
                ("12 vinyl", " 1", " 02"),  # common prefix
            ]
        ):
            with self.subTest(marker=marker, suffix1=suffix1, suffix2=suffix2):
                base = self.temp_path / f"marker_{i}"
                base.mkdir()

                album_dir = base / "Album Name"
                album_dir.mkdir()

                discs = []
                for suffix in (suffix1, suffix2):
                    disc = album_dir / f"{marker}{suffix}"
                    disc.mkdir()
                    _mkmp3(disc / "song.mp3")
                    discs.append(str(disc))

                albums = list(albums_in_dir(str(base)))
                assert len(albums) == 1
                root, items = albums[0]
                for disc in discs:
                    assert disc in root
                assert len(items) == 2

    def test_no_coalesce_mismatched_prefixes(self):
        # "CD 02" and "Enhanced CD 01" share the "cd" marker but have
        # different prefixes, so they should not be collapsed.
        base = self.temp_path / "mismatched"
        base.mkdir()

        album_dir = base / "Album Name"
        album_dir.mkdir()

        for subdir in ("CD 02", "Enhanced CD 01"):
            d = album_dir / subdir
            d.mkdir()
            _mkmp3(d / "song.mp3")

        albums = list(albums_in_dir(str(base)))
        assert len(albums) == 2


class ReimportTest(AutotagImportTestCase):
    """Test "re-imports", in which the autotagging machinery is used for
    music that's already in the library.

    This works by importing new database entries for the same files and
    replacing the old data with the new data. We also copy over flexible
    attributes and the added date.
    """

    matching = AutotagStub.GOOD

    def setUp(self):
        super().setUp()

        # The existing album.
        album = self.add_album_fixture()
        album.added = 4242.0
        album.foo = "bar"  # Some flexible attribute.
        album.data_source = "original_source"
        album.store()
        item = album.items().get()
        item.baz = "qux"
        item.added = 4747.0
        item.store()

    def _setup_session(self, singletons=False):
        self.setup_importer(import_dir=self.lib_path, singletons=singletons)
        self.importer.add_choice(importer.Action.APPLY)

    def _album(self):
        return self.lib.albums().get()

    def _item(self):
        return self.lib.items().get()

    def test_reimported_album_gets_new_metadata(self):
        self._setup_session()
        assert self._album().album == "\xe4lbum"
        self.importer.run()
        assert self._album().album == "the album"

    def test_reimported_album_preserves_flexattr(self):
        self._setup_session()
        self.importer.run()
        assert self._album().foo == "bar"

    def test_reimported_album_preserves_added(self):
        self._setup_session()
        self.importer.run()
        assert self._album().added == 4242.0

    def test_reimported_album_preserves_item_flexattr(self):
        self._setup_session()
        self.importer.run()
        assert self._item().baz == "qux"

    def test_reimported_album_preserves_item_added(self):
        self._setup_session()
        self.importer.run()
        assert self._item().added == 4747.0

    def test_reimported_item_gets_new_metadata(self):
        self._setup_session(True)
        assert self._item().title == "t\xeftle 0"
        self.importer.run()
        assert self._item().title == "full"

    def test_reimported_item_preserves_flexattr(self):
        self._setup_session(True)
        self.importer.run()
        assert self._item().baz == "qux"

    def test_reimported_item_preserves_added(self):
        self._setup_session(True)
        self.importer.run()
        assert self._item().added == 4747.0

    def test_reimported_item_preserves_art(self):
        self._setup_session()
        art_source = _common.RSRC / "abbey.jpg"
        replaced_album = self._album()
        replaced_album.set_art(art_source)
        replaced_album.store()
        old_artpath = replaced_album.art_filepath
        self.importer.run()
        new_album = self._album()
        new_artpath = new_album.art_destination(art_source)
        assert new_album.artpath == new_artpath
        assert new_album.art_filepath.exists()
        if new_artpath != old_artpath:
            assert not old_artpath.exists()

    def test_reimported_album_has_new_flexattr(self):
        self._setup_session()
        assert self._album().get("bandcamp_album_id") is None
        self.importer.run()
        assert self._album().bandcamp_album_id == "bc_url"

    def test_reimported_album_not_preserves_flexattr(self):
        self._setup_session()

        self.importer.run()
        assert self._album().data_source == "match_source"


class TestImportPretend(ImportHelper):
    """Test the pretend commandline option."""

    def setup_beets(self):
        super().setup_beets()
        self.album_track_path = self.prepare_album_for_import(1)[0]
        self.single_path = self.prepare_track_for_import(2, self.import_path)
        self.album_path = self.album_track_path.parent

    def _run(self, importer, caplog):
        with caplog.at_level("DEBUG"):
            importer.run()
        assert len(self.lib.items()) == 0
        assert len(self.lib.albums()) == 0
        return [
            r.message
            for r in caplog.records
            if not r.message.startswith("Sending event:")
        ]

    def test_import_singletons_pretend(self, caplog):
        assert self._run(
            self.setup_singleton_importer(pretend=True), caplog
        ) == [
            f"Singleton: {self.single_path}",
            f"Singleton: {self.album_track_path}",
        ]

    def test_import_album_pretend(self, caplog):
        assert self._run(self.setup_importer(pretend=True), caplog) == [
            f"Album: {self.import_path}",
            f"  {self.single_path}",
            f"Album: {self.album_path}",
            f"  {self.album_track_path}",
        ]

    def test_import_pretend_empty(self, caplog):
        empty_path = self.temp_path / "empty"
        empty_path.mkdir()

        importer = self.setup_importer(pretend=True, import_dir=empty_path)

        assert self._run(importer, caplog) == [
            f"No files imported from {empty_path}"
        ]


def mocked_get_albums_by_ids(ids):
    """Return album candidate for the given id.

    The two albums differ only in the release title and artist name, so that
    ID_RELEASE_0 is a closer match to the items created by
    ImportHelper.prepare_album_for_import().
    """
    # Map IDs to (release title, artist), so the distances are different.
    album_artist_map = {
        TestImportId.ID_RELEASE_0: ("VALID_RELEASE_0", "TAG ARTIST"),
        TestImportId.ID_RELEASE_1: ("VALID_RELEASE_1", "DISTANT_MATCH"),
    }

    for id_ in ids:
        album, artist = album_artist_map[id_]
        yield AlbumInfo(
            album_id=id_,
            album=album,
            artist_id="some-id",
            artist=artist,
            albumstatus="Official",
            tracks=[
                TrackInfo(
                    track_id="bar",
                    title="foo",
                    artist_id="some-id",
                    artist=artist,
                    length=59,
                    index=9,
                    track_allt="A2",
                )
            ],
        )


def mocked_get_tracks_by_ids(ids):
    """Return track candidate for the given id.

    The two tracks differ only in the release title and artist name, so that
    ID_RELEASE_0 is a closer match to the items created by
    ImportHelper.prepare_album_for_import().
    """
    # Map IDs to (recording title, artist), so the distances are different.
    title_artist_map = {
        TestImportId.ID_RECORDING_0: ("VALID_RECORDING_0", "TAG ARTIST"),
        TestImportId.ID_RECORDING_1: ("VALID_RECORDING_1", "DISTANT_MATCH"),
    }

    for id_ in ids:
        title, artist = title_artist_map[id_]
        yield TrackInfo(
            track_id=id_,
            title=title,
            artist_id="some-id",
            artist=artist,
            length=59,
        )


@patch(
    "beets.metadata_plugins.tracks_for_ids",
    Mock(side_effect=mocked_get_tracks_by_ids),
)
@patch(
    "beets.metadata_plugins.albums_for_ids",
    Mock(side_effect=mocked_get_albums_by_ids),
)
class TestImportId(ImportHelper):
    ID_RELEASE_0 = "00000000-0000-0000-0000-000000000000"
    ID_RELEASE_1 = "11111111-1111-1111-1111-111111111111"
    ID_RECORDING_0 = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    ID_RECORDING_1 = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    def setup_beets(self):
        super().setup_beets()
        self.prepare_album_for_import(1)

    def test_one_mbid_one_album(self):
        self.setup_importer(search_ids=[self.ID_RELEASE_0])

        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()
        assert self.lib.albums().get().album == "VALID_RELEASE_0"

    def test_several_mbid_one_album(self):
        self.setup_importer(search_ids=[self.ID_RELEASE_0, self.ID_RELEASE_1])

        self.importer.add_choice(2)  # Pick the 2nd best match (release 1).
        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()
        assert self.lib.albums().get().album == "VALID_RELEASE_1"

    def test_one_mbid_one_singleton(self):
        self.setup_singleton_importer(search_ids=[self.ID_RECORDING_0])

        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()
        assert self.lib.items().get().title == "VALID_RECORDING_0"

    def test_several_mbid_one_singleton(self):
        self.setup_singleton_importer(
            search_ids=[self.ID_RECORDING_0, self.ID_RECORDING_1]
        )

        self.importer.add_choice(2)  # Pick the 2nd best match (recording 1).
        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()
        assert self.lib.items().get().title == "VALID_RECORDING_1"

    def test_candidates_album(self):
        """Test directly ImportTask.lookup_candidates()."""
        task = importer.ImportTask(
            paths=os.fsencode(self.import_path),
            toppath="top path",
            items=[_common.item()],
        )

        task.lookup_candidates([self.ID_RELEASE_0, self.ID_RELEASE_1])

        assert {"VALID_RELEASE_0", "VALID_RELEASE_1"} == {
            c.info.album for c in task.candidates
        }

    def test_candidates_singleton(self):
        """Test directly SingletonImportTask.lookup_candidates()."""
        task = importer.SingletonImportTask(
            toppath="top path", item=_common.item()
        )

        task.lookup_candidates([self.ID_RECORDING_0, self.ID_RECORDING_1])

        assert {"VALID_RECORDING_0", "VALID_RECORDING_1"} == {
            c.info.title for c in task.candidates
        }


class TestMpeglayerWavImport(AsIsImporterMixin, ImportHelper):
    """Test remuxing of WAVE_FORMAT_MPEGLAYER3 WAV files."""

    def test_remux_mpeglayer3_wav(self):
        src = _common.RSRC / "mpeglayer3.wav"
        dest = self.temp_path / "mpeglayer3.wav"
        shutil.copy(syspath(src), syspath(dest))

        mp3_path = remux_mpeglayer3_wav(dest)

        assert mp3_path is not None
        assert mp3_path.suffix == ".mp3"
        assert mp3_path.exists()
        assert not dest.exists()

    def test_remux_mpeglayer3_wav_disabled(self):
        """When remux_mp3_in_wav is disabled, WAV file should not be remuxed."""
        self.config["import"]["remux_mp3_in_wav"] = False
        src = _common.RSRC / "mpeglayer3.wav"
        dest = self.import_path / "mpeglayer3.wav"
        shutil.copy(syspath(src), syspath(dest))

        self.run_asis_importer()
        assert dest.exists()
