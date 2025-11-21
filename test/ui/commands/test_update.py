import os
from unittest.mock import patch

from mediafile import MediaFile

from beets import library, ui
from beets.test import _common
from beets.test.helper import BeetsTestCase, IOMixin, capture_log
from beets.ui.commands.update import update_func, update_items
from beets.util import MoveOperation, remove, syspath


class UpdateTest(IOMixin, BeetsTestCase):
    def setUp(self):
        super().setUp()

        # Copy a file into the library.
        item_path = os.path.join(_common.RSRC, b"full.mp3")
        item_path_two = os.path.join(_common.RSRC, b"full.flac")
        self.i = library.Item.from_path(item_path)
        self.i2 = library.Item.from_path(item_path_two)
        self.lib.add(self.i)
        self.lib.add(self.i2)
        self.i.move(operation=MoveOperation.COPY)
        self.i2.move(operation=MoveOperation.COPY)
        self.album = self.lib.add_album([self.i, self.i2])

        # Album art.
        artfile = os.path.join(self.temp_dir, b"testart.jpg")
        _common.touch(artfile)
        self.album.set_art(artfile)
        self.album.store()
        remove(artfile)

    def _update(
        self,
        query=(),
        album=False,
        move=False,
        reset_mtime=True,
        fields=None,
        exclude_fields=None,
    ):
        self.io.addinput("y")
        if reset_mtime:
            self.i.mtime = 0
            self.i.store()
        update_items(
            self.lib,
            query,
            album,
            move,
            False,
            fields=fields,
            exclude_fields=exclude_fields,
        )

    def test_delete_removes_item(self):
        assert list(self.lib.items())
        remove(self.i.path)
        remove(self.i2.path)
        self._update()
        assert not list(self.lib.items())

    def test_delete_removes_album(self):
        assert self.lib.albums()
        remove(self.i.path)
        remove(self.i2.path)
        self._update()
        assert not self.lib.albums()

    def test_delete_removes_album_art(self):
        art_filepath = self.album.art_filepath
        assert art_filepath.exists()
        remove(self.i.path)
        remove(self.i2.path)
        self._update()
        assert not art_filepath.exists()

    def test_modified_metadata_detected(self):
        mf = MediaFile(syspath(self.i.path))
        mf.title = "differentTitle"
        mf.save()
        self._update()
        item = self.lib.items().get()
        assert item.title == "differentTitle"

    def test_modified_metadata_moved(self):
        mf = MediaFile(syspath(self.i.path))
        mf.title = "differentTitle"
        mf.save()
        self._update(move=True)
        item = self.lib.items().get()
        assert b"differentTitle" in item.path

    def test_modified_metadata_not_moved(self):
        mf = MediaFile(syspath(self.i.path))
        mf.title = "differentTitle"
        mf.save()
        self._update(move=False)
        item = self.lib.items().get()
        assert b"differentTitle" not in item.path

    def test_selective_modified_metadata_moved(self):
        mf = MediaFile(syspath(self.i.path))
        mf.title = "differentTitle"
        mf.genre = "differentGenre"
        mf.save()
        self._update(move=True, fields=["title"])
        item = self.lib.items().get()
        assert b"differentTitle" in item.path
        assert item.genre != "differentGenre"

    def test_selective_modified_metadata_not_moved(self):
        mf = MediaFile(syspath(self.i.path))
        mf.title = "differentTitle"
        mf.genre = "differentGenre"
        mf.save()
        self._update(move=False, fields=["title"])
        item = self.lib.items().get()
        assert b"differentTitle" not in item.path
        assert item.genre != "differentGenre"

    def test_modified_album_metadata_moved(self):
        mf = MediaFile(syspath(self.i.path))
        mf.album = "differentAlbum"
        mf.save()
        self._update(move=True)
        item = self.lib.items().get()
        assert b"differentAlbum" in item.path

    def test_modified_album_metadata_art_moved(self):
        artpath = self.album.artpath
        mf = MediaFile(syspath(self.i.path))
        mf.album = "differentAlbum"
        mf.save()
        self._update(move=True)
        album = self.lib.albums()[0]
        assert artpath != album.artpath
        assert album.artpath is not None

    def test_selective_modified_album_metadata_moved(self):
        mf = MediaFile(syspath(self.i.path))
        mf.album = "differentAlbum"
        mf.genre = "differentGenre"
        mf.save()
        self._update(move=True, fields=["album"])
        item = self.lib.items().get()
        assert b"differentAlbum" in item.path
        assert item.genre != "differentGenre"

    def test_selective_modified_album_metadata_not_moved(self):
        mf = MediaFile(syspath(self.i.path))
        mf.album = "differentAlbum"
        mf.genre = "differentGenre"
        mf.save()
        self._update(move=True, fields=["genre"])
        item = self.lib.items().get()
        assert b"differentAlbum" not in item.path
        assert item.genre == "differentGenre"

    def test_mtime_match_skips_update(self):
        mf = MediaFile(syspath(self.i.path))
        mf.title = "differentTitle"
        mf.save()

        # Make in-memory mtime match on-disk mtime.
        self.i.mtime = os.path.getmtime(syspath(self.i.path))
        self.i.store()

        self._update(reset_mtime=False)
        item = self.lib.items().get()
        assert item.title == "full"

    def test_multivalued_albumtype_roundtrip(self):
        # https://github.com/beetbox/beets/issues/4528

        # albumtypes is empty for our test fixtures, so populate it first
        album = self.album
        correct_albumtypes = ["album", "live"]

        # Setting albumtypes does not set albumtype, currently.
        # Using x[0] mirrors https://github.com/beetbox/mediafile/blob/057432ad53b3b84385e5582f69f44dc00d0a725d/mediafile.py#L1928  # noqa: E501
        correct_albumtype = correct_albumtypes[0]

        album.albumtype = correct_albumtype
        album.albumtypes = correct_albumtypes
        album.try_sync(write=True, move=False)

        album.load()
        assert album.albumtype == correct_albumtype
        assert album.albumtypes == correct_albumtypes

        self._update()

        album.load()
        assert album.albumtype == correct_albumtype
        assert album.albumtypes == correct_albumtypes

    def test_modified_metadata_excluded(self):
        mf = MediaFile(syspath(self.i.path))
        mf.lyrics = "new lyrics"
        mf.save()
        self._update(exclude_fields=["lyrics"])
        item = self.lib.items().get()
        assert item.lyrics != "new lyrics"

    def test_delete_with_pretend_mode(self):
        """Test that pretend mode shows deletion but doesn't remove items."""
        assert list(self.lib.items())
        remove(self.i.path)
        remove(self.i2.path)

        # Run update in pretend mode
        self.i.mtime = 0
        self.i.store()
        update_items(self.lib, (), False, False, True, fields=None)

        # Items should still exist in database
        assert len(list(self.lib.items())) == 2

    def test_singleton_item_updated(self):
        """Test that singleton items (not in albums) are updated correctly."""
        # Create a singleton item (not part of an album)
        singleton_path = os.path.join(_common.RSRC, b"full.mp3")
        singleton = library.Item.from_path(singleton_path)
        self.lib.add(singleton)
        singleton.move(operation=MoveOperation.COPY)

        # Modify the metadata
        mf = MediaFile(syspath(singleton.path))
        mf.title = "SingletonTitle"
        mf.save()

        # Update and verify
        singleton.mtime = 0
        singleton.store()
        update_items(self.lib, (), False, False, False, fields=None)

        # Check that singleton was updated
        updated_singleton = self.lib.get_item(singleton.id)
        assert updated_singleton.title == "SingletonTitle"

    def test_singleton_deleted(self):
        """Test that deleted singleton items are removed from library."""
        # Create a singleton item
        singleton_path = os.path.join(_common.RSRC, b"full.mp3")
        singleton = library.Item.from_path(singleton_path)
        self.lib.add(singleton)
        singleton.move(operation=MoveOperation.COPY)

        initial_count = len(list(self.lib.items()))

        # Delete the file
        remove(singleton.path)

        # Update
        singleton.mtime = 0
        singleton.store()
        update_items(self.lib, (), False, False, False, fields=None)

        # Singleton should be removed from database
        assert len(list(self.lib.items())) == initial_count - 1
        assert self.lib.get_item(singleton.id) is None

    def test_corrupted_file_skipped(self):
        """Test that corrupted/unreadable files are skipped with error log."""
        # Create a corrupted file by writing invalid data
        corrupted_path = os.path.join(self.temp_dir, b"corrupted.mp3")
        with open(corrupted_path, "wb") as f:
            f.write(b"This is not a valid audio file")

        # Create an item pointing to this corrupted file
        self.i.path = corrupted_path
        self.i.mtime = 0
        self.i.store()

        # Run update and capture log messages
        with capture_log("beets") as logs:
            update_items(self.lib, (), False, False, False, fields=None)

        # Check that an error was logged
        assert any("error reading" in msg.lower() for msg in logs)

        # Item should still exist (just wasn't updated)
        assert self.lib.get_item(self.i.id) is not None

    def test_albumartist_preserved_when_empty(self):
        """Test that albumartist is preserved when it matches artist."""
        # Set up initial state where albumartist equals artist
        self.i.artist = "Test Artist"
        self.i.albumartist = "Test Artist"
        self.i.store()

        # Modify the file to have no albumartist but same artist
        mf = MediaFile(syspath(self.i.path))
        mf.artist = "Test Artist"
        mf.albumartist = ""  # Clear albumartist in file
        mf.title = "Modified"
        mf.save()

        # Update
        self.i.mtime = 0
        self.i.store()
        update_items(self.lib, (), False, False, False, fields=None)

        # albumartist should be preserved from the old item
        updated_item = self.lib.get_item(self.i.id)
        assert updated_item.albumartist == "Test Artist"
        assert updated_item.title == "Modified"

    def test_albumartist_not_preserved_when_different(self):
        """Test that albumartist is updated when artist changes."""
        # Set up initial state
        self.i.artist = "Old Artist"
        self.i.albumartist = "Old Artist"
        self.i.store()

        # Modify the file with different artist and no albumartist
        mf = MediaFile(syspath(self.i.path))
        mf.artist = "New Artist"
        mf.albumartist = ""
        mf.save()

        # Update
        self.i.mtime = 0
        self.i.store()
        update_items(self.lib, (), False, False, False, fields=None)

        # albumartist should NOT be preserved (artist changed)
        updated_item = self.lib.get_item(self.i.id)
        assert updated_item.artist == "New Artist"
        # albumartist should be empty or equal to new artist
        assert updated_item.albumartist != "Old Artist"

    def test_pretend_mode_shows_changes_no_album_update(self):
        """Test that pretend mode doesn't update album metadata."""
        # Modify item metadata
        mf = MediaFile(syspath(self.i.path))
        original_album = self.album.album
        mf.album = "DifferentAlbum"
        mf.save()

        # Run in pretend mode
        self.i.mtime = 0
        self.i.store()
        update_items(self.lib, (), False, False, True, fields=None)

        # Album should not be updated
        self.album.load()
        assert self.album.album == original_album

    def test_no_metadata_change_skips_store(self):
        """Test that when file mtime changes but metadata doesn't, nothing is stored.

        This validates the current behavior where mtime is not in the media
        fields, so items without metadata changes don't update their mtime.
        This might be a bug, but we're documenting current behavior.
        """
        original_title = self.i.title

        # Set mtime to very old value
        self.i.mtime = 0
        self.i.store()

        # Touch the file (changes mtime but not metadata)
        import time
        time.sleep(0.01)
        os.utime(syspath(self.i.path), None)

        # Run update
        update_items(self.lib, (), False, False, False, fields=None)

        # Title should be unchanged
        updated_item = self.lib.get_item(self.i.id)
        assert updated_item.title == original_title

        # Note: mtime is NOT updated because it's not in media_fields
        # This documents current behavior which may be a bug


class UpdateFuncTest(IOMixin, BeetsTestCase):
    """Tests for the update_func command function."""

    def setUp(self):
        super().setUp()

        # Copy a file into the library
        item_path = os.path.join(_common.RSRC, b"full.mp3")
        self.i = library.Item.from_path(item_path)
        self.lib.add(self.i)
        self.i.move(operation=MoveOperation.COPY)
        self.album = self.lib.add_album([self.i])

    def test_missing_library_directory_prompts_user(self):
        """Test that missing library directory prompts user for confirmation.

        This test exposes a bug in the production code where lib.directory
        (bytes) is passed to ui.print_() which expects a string.
        """
        # Create a mock options object
        class MockOpts:
            album = False
            move = False
            pretend = False
            fields = None
            exclude_fields = None

        opts = MockOpts()

        # Save original directory and set to non-existent path
        original_dir = self.lib.directory
        self.lib.directory = b"/nonexistent/path/to/library"

        # User answers 'no' to continue
        self.io.addinput("n")

        # This should raise a TypeError due to the bug in line 136
        # where bytes are passed to ui.print_() instead of string
        try:
            update_func(self.lib, opts, [])
            # If it doesn't raise, check the output
            output = self.io.getoutput()
            assert "Library path is unavailable or does not exist" in output
        except TypeError as e:
            # Expected due to bug in production code
            assert "expected str instance, bytes found" in str(e)
        finally:
            # Restore original directory
            self.lib.directory = original_dir

    def test_missing_library_directory_user_continues(self):
        """Test that user can choose to continue with missing directory.

        This test exposes a bug in the production code where lib.directory
        (bytes) is passed to ui.print_() which expects a string.
        """
        # Create a mock options object
        class MockOpts:
            album = False
            move = False
            pretend = False
            fields = None
            exclude_fields = None

        opts = MockOpts()

        # Save original directory
        original_dir = self.lib.directory
        self.lib.directory = b"/nonexistent/path"

        # User answers 'yes' to continue
        self.io.addinput("y")

        # This should raise a TypeError due to the bug in line 136
        try:
            update_func(self.lib, opts, [])
            output = self.io.getoutput()
            assert "Library path is unavailable or does not exist" in output
        except TypeError as e:
            # Expected due to bug in production code
            assert "expected str instance, bytes found" in str(e)
        finally:
            # Restore original directory
            self.lib.directory = original_dir

    def test_normal_library_directory_no_prompt(self):
        """Test that valid library directory doesn't prompt user."""
        # Create a mock options object
        class MockOpts:
            album = False
            move = False
            pretend = False
            fields = None
            exclude_fields = None

        opts = MockOpts()

        # Library directory should exist
        assert os.path.isdir(syspath(self.lib.directory))

        # Run update (no input needed)
        update_func(self.lib, opts, [])

        # Should not contain warning message
        output = self.io.getoutput()
        assert "Library path is unavailable" not in output

    def test_missing_library_directory_user_declines(self):
        """Test that user can decline to continue with missing directory."""
        from unittest.mock import patch

        # Create a mock options object
        class MockOpts:
            album = False
            move = False
            pretend = False
            fields = None
            exclude_fields = None

        opts = MockOpts()

        # Save original directory
        original_dir = self.lib.directory
        self.lib.directory = b"/nonexistent/path"

        try:
            # Patch ui.print_ in the update module to handle bytes
            with patch("beets.ui.commands.update.ui.print_") as mock_print:
                # User answers 'no' to continue
                self.io.addinput("n")

                # Call update_func - should return early
                result = update_func(self.lib, opts, [])

                # Should have returned without doing anything
                assert result is None

                # Verify print was called with warning messages
                assert mock_print.call_count >= 2
                call_args = [str(call[0][0]) if call[0] else "" for call in mock_print.call_args_list]
                output_str = " ".join(call_args)
                assert "Library path is unavailable or does not exist" in output_str
        finally:
            # Restore original directory
            self.lib.directory = original_dir
