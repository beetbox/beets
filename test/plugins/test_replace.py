import optparse
import shutil
from collections.abc import Generator
from pathlib import Path
from unittest.mock import Mock

import pytest
from mediafile import MediaFile

from beets import ui
from beets.library import Item, Library
from beets.library.exceptions import WriteError
from beets.test import _common
from beets.test.helper import TestHelper, capture_log
from beetsplug.replace import ReplacePlugin

replace = ReplacePlugin()


def always(x):
    return lambda *args, **kwargs: x


def always_raise(x):
    def err(*args, **kwargs):
        raise x

    return err


class TestReplace:
    @pytest.fixture
    def mp3_file(self, tmp_path) -> Path:
        dest = tmp_path / "full.mp3"
        src = Path(_common.RSRC.decode()) / "full.mp3"
        shutil.copyfile(src, dest)

        mediafile = MediaFile(dest)
        mediafile.title = "AAA"
        mediafile.save()

        return dest

    @pytest.fixture
    def opus_file(self, tmp_path) -> Path:
        dest = tmp_path / "full.opus"
        src = Path(_common.RSRC.decode()) / "full.opus"
        shutil.copyfile(src, dest)

        return dest

    @pytest.fixture
    def library(self) -> Generator[Library]:
        helper = TestHelper()
        helper.setup_beets()

        yield helper.lib

        helper.teardown_beets()

    def test_run_replace_too_few_args(self):
        with pytest.raises(ui.UserError):
            replace.run(None, optparse.Values(), [])

    def test_run_replace_no_matches(self, library):
        with pytest.raises(ui.UserError):
            replace.run(library, optparse.Values(), ["BBB", ""])

    def test_run_replace_no_song_selected(
        self, library, mp3_file, opus_file, monkeypatch
    ):
        monkeypatch.setattr(replace, "file_check", always(None))
        monkeypatch.setattr(replace, "select_song", always(None))

        item = Item.from_path(mp3_file)
        library.add(item)

        replace.run(library, optparse.Values(), ["AAA", str(opus_file)])

        assert mp3_file.exists()
        assert opus_file.exists()

    def test_run_replace_not_confirmed(
        self, library, mp3_file, opus_file, monkeypatch
    ):
        monkeypatch.setattr(replace, "file_check", always(None))
        monkeypatch.setattr(replace, "confirm_replacement", always(False))

        item = Item.from_path(mp3_file)
        library.add(item)

        monkeypatch.setattr(replace, "select_song", always(item))

        replace.run(library, optparse.Values(), ["AAA", str(opus_file)])

        assert mp3_file.exists()
        assert opus_file.exists()

    def test_run_replace(self, library, mp3_file, opus_file, monkeypatch):
        replace_file = Mock(replace.replace_file, return_value=None)
        monkeypatch.setattr(replace, "replace_file", replace_file)

        monkeypatch.setattr(replace, "file_check", always(None))
        monkeypatch.setattr(replace, "confirm_replacement", always(True))

        item = Item.from_path(mp3_file)
        library.add(item)

        monkeypatch.setattr(replace, "select_song", always(item))

        replace.run(library, optparse.Values(), ["AAA", str(opus_file)])

        replace_file.assert_called_once()

    def test_path_is_dir(self, tmp_path):
        fake_directory = tmp_path / "fakeDir"
        fake_directory.mkdir()
        with pytest.raises(ui.UserError):
            replace.file_check(fake_directory)

    def test_path_is_unsupported_file(self, tmp_path):
        fake_file = tmp_path / "fakefile.txt"
        fake_file.write_text("test", encoding="utf-8")
        with pytest.raises(ui.UserError):
            replace.file_check(fake_file)

    def test_path_is_supported_file(self, mp3_file):
        replace.file_check(mp3_file)

    def test_select_song_valid_choice(self, monkeypatch, capfd):
        songs = ["Song A", "Song B", "Song C"]
        monkeypatch.setattr("builtins.input", lambda _: "2")

        selected_song = replace.select_song(songs)

        captured = capfd.readouterr()

        assert "1. Song A" in captured.out
        assert "2. Song B" in captured.out
        assert "3. Song C" in captured.out
        assert selected_song == "Song B"

    def test_select_song_cancel(self, monkeypatch):
        songs = ["Song A", "Song B", "Song C"]
        monkeypatch.setattr("builtins.input", lambda _: "0")

        selected_song = replace.select_song(songs)

        assert selected_song is None

    def test_select_song_invalid_then_valid(self, monkeypatch, capfd):
        songs = ["Song A", "Song B", "Song C"]
        inputs = iter(["invalid", "4", "3"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        selected_song = replace.select_song(songs)

        captured = capfd.readouterr()

        assert "Invalid input. Please type in a number." in captured.out
        assert (
            "Invalid choice. Please enter a number between 1 and 3."
            in captured.out
        )
        assert selected_song == "Song C"

    def test_confirm_replacement_file_not_exist(self):
        class Song:
            path = b"test123321.txt"

        song = Song()

        with pytest.raises(ui.UserError):
            replace.confirm_replacement("test", song)

    def test_confirm_replacement_yes(self, monkeypatch):
        src = Path(_common.RSRC.decode()) / "full.mp3"
        monkeypatch.setattr("builtins.input", always("yes"))

        class Song:
            path = str(src).encode()

        song = Song()

        assert replace.confirm_replacement("test", song) is True

    def test_confirm_replacement_no(self, monkeypatch):
        src = Path(_common.RSRC.decode()) / "full.mp3"
        monkeypatch.setattr("builtins.input", always("no"))

        class Song:
            path = str(src).encode()

        song = Song()

        assert replace.confirm_replacement("test", song) is False

    def test_replace_file_move_fails(self, tmp_path):
        item = Item()
        item.path = bytes(tmp_path / "not_a_song.mp3")

        with pytest.raises(ui.UserError):
            replace.replace_file(tmp_path / "not_a_file.opus", item)

    def test_replace_file_delete_fails(
        self, library, mp3_file, opus_file, monkeypatch
    ):
        monkeypatch.setattr(Path, "unlink", always_raise(OSError))

        item = Item.from_path(mp3_file)
        library.add(item)

        with pytest.raises(ui.UserError):
            replace.replace_file(opus_file, item)

    def test_replace_file_write_fails(
        self, library, mp3_file, opus_file, monkeypatch
    ):
        monkeypatch.setattr(
            Item, "write", always_raise(WriteError("path", "reason"))
        )

        item = Item.from_path(mp3_file)
        library.add(item)

        with capture_log() as logs:
            replace.replace_file(opus_file, item)

        # Assert that a writing error was logged
        assert next(m for m in logs if m.startswith("error writing"))

    def test_replace_file(
        self, mp3_file: Path, opus_file: Path, library: Library
    ):
        old_mediafile = MediaFile(mp3_file)
        old_mediafile.albumartist = "ABC"
        old_mediafile.disctitle = "DEF"
        old_mediafile.genre = "GHI"
        old_mediafile.save()

        item = Item.from_path(mp3_file)
        library.add(item)

        item.mtime = 0
        item.store()

        replace.replace_file(opus_file, item)

        # Check that the file has been replaced.
        assert opus_file.exists()
        assert not mp3_file.exists()

        # Check that the database path and mtime have been updated.
        item.load()
        assert item.path == bytes(opus_file)
        assert item.mtime > 0

        # Check that the new file has the old file's metadata.
        new_mediafile = MediaFile(opus_file)
        assert new_mediafile.albumartist == "ABC"
        assert new_mediafile.disctitle == "DEF"
        assert new_mediafile.genre == "GHI"
