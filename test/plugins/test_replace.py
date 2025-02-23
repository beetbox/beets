from beets import ui
from beets.test.helper import PluginTestCase
from beetsplug.replace import ReplacePlugin
from mediafile import MediaFile
from pathlib import Path
import pytest
import shutil
from beets.test import _common

replace = ReplacePlugin()


class TestReplace:
    @pytest.fixture(autouse=True)
    def fake_dir(self, tmp_path):
        self.fakeDir = tmp_path

    @pytest.fixture(autouse=True)
    def fake_file(self, tmp_path):
        self.fakeFile = tmp_path

    def test_path_is_dir(self):
        fakeDirectory = self.fakeDir / "fakeDir"
        fakeDirectory.mkdir()
        with pytest.raises(ui.UserError):
            replace.file_check(fakeDirectory)

    def test_path_is_unspported_file(self):
        fakeFile = self.fakeFile / "fakefile.txt"
        fakeFile.write_text("test", encoding="utf-8")
        with pytest.raises(ui.UserError):
            replace.file_check(fakeFile)

    def test_path_is_supported_file(self):
        dest = self.fakeFile / "full.mp3"
        src = Path(_common.RSRC.decode()) / "full.mp3"
        shutil.copyfile(src, dest)

        mediafile = MediaFile(dest)
        mediafile.albumartist = "AAA"
        mediafile.disctitle = "DDD"
        mediafile.genres = ["a", "b", "c"]
        mediafile.composer = None
        mediafile.save()

        replace.file_check(Path(str(dest)))

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
        print(captured)

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
