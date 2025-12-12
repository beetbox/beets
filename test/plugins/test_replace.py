import shutil
from collections.abc import Generator
from pathlib import Path

import pytest
from mediafile import MediaFile

from beets import ui
from beets.library import Item, Library
from beets.test import _common
from beets.test.helper import TestHelper
from beetsplug.replace import ReplacePlugin

replace = ReplacePlugin()


class TestReplace:
    @pytest.fixture
    def mp3_file(self, tmp_path) -> Path:
        dest = tmp_path / "full.mp3"
        src = Path(_common.RSRC.decode()) / "full.mp3"
        shutil.copyfile(src, dest)

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
        monkeypatch.setattr("builtins.input", lambda _: "YES    ")

        class Song:
            path = str(src).encode()

        song = Song()

        assert replace.confirm_replacement("test", song) is True

    def test_confirm_replacement_no(self, monkeypatch):
        src = Path(_common.RSRC.decode()) / "full.mp3"
        monkeypatch.setattr("builtins.input", lambda _: "test123")

        class Song:
            path = str(src).encode()

        song = Song()

        assert replace.confirm_replacement("test", song) is False

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

        replace.replace_file(opus_file, item)

        # Check that the file has been replaced.
        assert opus_file.exists()
        assert not mp3_file.exists()

        # Check that the database path has been updated.
        assert item.path == bytes(opus_file)

        # Check that the new file has the old file's metadata.
        new_mediafile = MediaFile(opus_file)
        assert new_mediafile.albumartist == old_mediafile.albumartist
        assert new_mediafile.disctitle == old_mediafile.disctitle
        assert new_mediafile.genre == old_mediafile.genre
