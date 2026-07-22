import os
from unittest.mock import Mock, patch

from beets import library, util
from beets.test import _common
from beets.test.helper import PluginTestCase
from beetsplug.ipfs import IPFSPlugin


@patch("beets.util.command_output", Mock())
class IPFSPluginTest(PluginTestCase):
    plugin = "ipfs"

    def test_stored_hashes(self):
        test_album = self.mk_test_album()
        ipfs = IPFSPlugin()
        added_albums = ipfs.ipfs_added_albums(self.lib, self.lib.path)
        with added_albums.music_dir_context():
            added_album = added_albums.get_album(1)
            assert added_album.ipfs == test_album.ipfs
            found = False
            want_item = test_album.items()[2]
            for check_item in added_album.items():
                if check_item.get("ipfs", with_album=False):
                    ipfs_item = os.fsdecode(os.path.basename(want_item.path))
                    want_path = util.normpath(
                        os.path.join("/ipfs", test_album.ipfs, ipfs_item)
                    )
                    assert check_item.path == want_path
                    assert (
                        check_item.get("ipfs", with_album=False)
                        == want_item.ipfs
                    )
                    assert check_item.title == want_item.title
                    found = True
            assert found

    def test_get_from_hash_cleans_up_single_file_download(self):
        """
        Regression test for
        https://github.com/beetbox/beets/issues/2555

        `ipfs get <hash>` produces a plain file (not a directory) for
        a single-file IPFS object; which one it produces depends on
        what was originally added to IPFS at that hash. Cleanup must
        not assume it's always a directory and unconditionally call
        shutil.rmtree(), which raises OSError: Not a directory on a
        plain file, as in the issue's traceback.
        """
        test_hash = "QmTestHashForASingleFileDownload"
        cwd = os.getcwd()
        os.chdir(self.temp_path)
        try:
            # Simulate what `ipfs get` (mocked out above) would have
            # produced on disk for a single-file IPFS object: a plain
            # file named after the hash, not a directory.
            with open(test_hash, "w") as f:
                f.write("fake downloaded content")

            ipfs = IPFSPlugin()
            with patch(
                "beetsplug.ipfs.ui.commands.TerminalImportSession"
            ) as mock_session_cls:
                mock_session_cls.return_value.run = Mock()
                ipfs.ipfs_get_from_hash(self.lib, test_hash)

            assert not os.path.exists(test_hash)
        finally:
            os.chdir(cwd)

    def test_get_remote_lib_accepts_library_path(self):
        self.lib.path = self.temp_path / "library.db"
        remote_dir = self.temp_path / "remotes"
        remote_dir.mkdir()

        remote_lib = library.Library(remote_dir / "joined.db")
        remote_lib._close()

        ipfs = IPFSPlugin()
        added_lib = ipfs.get_remote_lib(self.lib)
        try:
            assert added_lib.path == remote_dir / "joined.db"
        finally:
            added_lib._close()

    def mk_test_album(self):
        items = [_common.item() for _ in range(3)]
        items[0].title = "foo bar"
        items[0].artist = "1one"
        items[0].album = "baz"
        items[0].year = 2001
        items[0].comp = True
        items[1].title = "baz qux"
        items[1].artist = "2two"
        items[1].album = "baz"
        items[1].year = 2002
        items[1].comp = True
        items[2].title = "beets 4 eva"
        items[2].artist = "3three"
        items[2].album = "foo"
        items[2].year = 2003
        items[2].comp = False
        items[2].ipfs = "QmfM9ic5LJj7V6ecozFx1MkSoaaiq3PXfhJoFvyqzpLXSk"

        for item in items:
            self.lib.add(item)

        album = self.lib.add_album(items)
        album.ipfs = "QmfM9ic5LJj7V6ecozFx1MkSoaaiq3PXfhJoFvyqzpLXSf"
        album.store(inherit=False)

        return album
