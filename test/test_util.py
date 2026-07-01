"""Tests for base utils from the beets.util package."""

import os
import platform
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from beets import util
from beets.library import Item
from beets.test import _common
from beets.test._common import touch
from beets.test.helper import NEEDS_REFLINK, BeetsTestCase
from beets.util import syspath


class UtilTest(unittest.TestCase):
    def test_open_anything(self):
        with _common.system_mock("Windows"):
            assert util.open_anything() == 'cmd /c start ""'

        with _common.system_mock("Darwin"):
            assert util.open_anything() == "open"

        with _common.system_mock("Tagada"):
            assert util.open_anything() == "xdg-open"

    @patch("os.execlp")
    @patch("beets.util.open_anything")
    def test_interactive_open(self, mock_open, mock_execlp):
        mock_open.return_value = "tagada"
        util.interactive_open(["foo"], util.open_anything())
        mock_execlp.assert_called_once_with("tagada", "tagada", "foo")
        mock_execlp.reset_mock()

        util.interactive_open(["foo"], "bar")
        mock_execlp.assert_called_once_with("bar", "bar", "foo")

    def test_sanitize_unix_replaces_leading_dot(self):
        with _common.platform_posix():
            p = util.sanitize_path("one/.two/three")
        assert "." not in p

    def test_sanitize_windows_replaces_trailing_dot(self):
        with _common.platform_windows():
            p = util.sanitize_path("one/two./three")
        assert "." not in p

    def test_sanitize_windows_replaces_illegal_chars(self):
        with _common.platform_windows():
            p = util.sanitize_path(':*?"<>|')
        assert ":" not in p
        assert "*" not in p
        assert "?" not in p
        assert '"' not in p
        assert "<" not in p
        assert ">" not in p
        assert "|" not in p

    def test_sanitize_windows_replaces_trailing_space(self):
        with _common.platform_windows():
            p = util.sanitize_path("one/two /three")
        assert " " not in p

    def test_sanitize_path_works_on_empty_string(self):
        with _common.platform_posix():
            p = util.sanitize_path("")
        assert p == ""

    def test_sanitize_with_custom_replace_overrides_built_in_sub(self):
        with _common.platform_posix():
            p = util.sanitize_path("a/.?/b", [(re.compile(r"foo"), "bar")])
        assert p == "a/.?/b"

    def test_sanitize_with_custom_replace_adds_replacements(self):
        with _common.platform_posix():
            p = util.sanitize_path("foo/bar", [(re.compile(r"foo"), "bar")])
        assert p == "bar/bar"

    @unittest.skip("unimplemented: #359")
    def test_sanitize_empty_component(self):
        with _common.platform_posix():
            p = util.sanitize_path("foo//bar", [(re.compile(r"^$"), "_")])
        assert p == "foo/_/bar"

    @patch("beets.util.subprocess.Popen")
    def test_command_output(self, mock_popen):
        def popen_fail(*args, **kwargs):
            m = Mock(returncode=1)
            m.communicate.return_value = "foo", "bar"
            return m

        mock_popen.side_effect = popen_fail
        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            util.command_output(["taga", "\xc3\xa9"])
        assert exc_info.value.returncode == 1
        assert exc_info.value.cmd == "taga \xc3\xa9"

    def test_case_sensitive_default(self):
        path = util.bytestring_path(util.normpath("/this/path/does/not/exist"))

        assert util.case_sensitive(path) == (platform.system() != "Windows")

    @unittest.skipIf(sys.platform == "win32", "fs is not case sensitive")
    def test_case_sensitive_detects_sensitive(self):
        # FIXME: Add tests for more code paths of case_sensitive()
        # when the filesystem on the test runner is not case sensitive
        pass

    @unittest.skipIf(sys.platform != "win32", "fs is case sensitive")
    def test_case_sensitive_detects_insensitive(self):
        # FIXME: Add tests for more code paths of case_sensitive()
        # when the filesystem on the test runner is case sensitive
        pass


class PathConversionTest(unittest.TestCase):
    def test_syspath_windows_format(self):
        with _common.platform_windows():
            path = os.path.join("a", "b", "c")
            outpath = util.syspath(path)
        assert isinstance(outpath, str)
        assert outpath.startswith("\\\\?\\")

    def test_syspath_windows_format_unc_path(self):
        # The \\?\ prefix on Windows behaves differently with UNC
        # (network share) paths.
        path = "\\\\server\\share\\file.mp3"
        with _common.platform_windows():
            outpath = util.syspath(path)
        assert isinstance(outpath, str)
        assert outpath == "\\\\?\\UNC\\server\\share\\file.mp3"

    def test_syspath_posix_unchanged(self):
        with _common.platform_posix():
            path = os.path.join("a", "b", "c")
            outpath = util.syspath(path)
        assert path == outpath

    def _windows_bytestring_path(self, path):
        with _common.platform_windows():
            return util.bytestring_path(path)

    def test_bytestring_path_windows_encodes_utf8(self):
        path = "caf\xe9"
        outpath = self._windows_bytestring_path(path)
        assert path == outpath.decode("utf-8")

    def test_bytesting_path_windows_removes_magic_prefix(self):
        path = "\\\\?\\C:\\caf\xe9"
        outpath = self._windows_bytestring_path(path)
        assert outpath == "C:\\caf\xe9".encode()


class TestPathLegalization:
    _p = pytest.param

    @pytest.fixture(autouse=True)
    def _patch_max_filename_length(self, monkeypatch):
        monkeypatch.setattr("beets.util.get_max_filename_length", lambda: 5)

    @pytest.mark.parametrize(
        "path, expected",
        [
            _p("abcdeX/fgh", "abcde/fgh", id="truncate-parent-dir"),
            _p("abcde/fXX.ext", "abcde/f.ext", id="truncate-filename"),
            # note that 🎹 is 4 bytes long:
            # >>> "🎹".encode("utf-8")
            # b'\xf0\x9f\x8e\xb9'
            _p("a🎹/a.ext", "a🎹/a.ext", id="unicode-fit"),
            _p("ab🎹/a.ext", "ab/a.ext", id="unicode-truncate-fully-one-byte-over-limit"),
            _p("f.a.e", "f.a.e", id="persist-dot-in-filename"),  # see #5771
        ],
    )  # fmt: skip
    def test_truncate(self, path, expected):
        path = path.replace("/", os.path.sep)
        expected = expected.replace("/", os.path.sep)

        assert util.truncate_path(path) == expected

    @pytest.mark.parametrize(
        "replacements, expected_path, expected_truncated",
        [  # [ repl before truncation, repl after truncation   ]
            _p([                                                  ], "_abcd",  False, id="default"),
            _p([(r"abcdX$", "1ST"),                               ], ":1ST",   False, id="1st_valid"),
            _p([(r"abcdX$", "TOO_LONG"),                          ], ":TOO_",  False, id="1st_truncated"),
            _p([(r"abcdX$", "1ST"),       (r"1ST$",   "2ND")      ], ":2ND",   False, id="both_valid"),
            _p([(r"abcdX$", "TOO_LONG"),  (r"TOO_$",  "2ND")      ], ":2ND",   False, id="1st_truncated_2nd_valid"),
            _p([(r"abcdX$", "1ST"),       (r"1ST$",   "TOO_LONG") ], ":TOO_",  False, id="1st_valid_2nd_truncated"),
            # if the logic truncates the path twice, it ends up applying the default replacements
            _p([(r"abcdX$", "TOO_LONG"),  (r"TOO_$",  "TOO_LONG") ], "_TOO_",  True,  id="both_truncated_default_repl_applied"),
        ]
    )  # fmt: skip
    def test_replacements(
        self, replacements, expected_path, expected_truncated
    ):
        replacements = [(re.compile(pat), repl) for pat, repl in replacements]

        assert util.legalize_path(":abcdX", replacements, "") == (
            expected_path,
            expected_truncated,
        )


class TestPlurality:
    @pytest.mark.parametrize(
        "objs, expected_obj, expected_freq",
        [
            pytest.param([1, 1, 1, 1], 1, 4, id="consensus"),
            pytest.param([1, 1, 2, 1], 1, 3, id="near consensus"),
            pytest.param([1, 1, 2, 2, 3], 1, 2, id="conflict-first-wins"),
        ],
    )
    def test_plurality(self, objs, expected_obj, expected_freq):
        assert (expected_obj, expected_freq) == util.plurality(objs)

    def test_empty_sequence_raises_error(self):
        with pytest.raises(ValueError, match="must be non-empty"):
            util.plurality([])

    def test_get_most_common_tags(self):
        items = [
            Item(albumartist="aartist", label="label 1", album="album"),
            Item(albumartist="aartist", label="label 2", album="album"),
            Item(albumartist="aartist", label="label 3", album="another album"),
        ]

        likelies, consensus = util.get_most_common_tags(items)

        assert likelies["albumartist"] == "aartist"
        assert likelies["album"] == "album"
        # albumartist consensus overrides artist
        assert likelies["artist"] == "aartist"
        assert likelies["label"] == "label 1"
        assert likelies["year"] == 0

        assert consensus["year"]
        assert consensus["albumartist"]
        assert not consensus["album"]
        assert not consensus["label"]


class HelperTest(unittest.TestCase):
    def test_ancestry_works_on_file(self):
        p = "/a/b/c"
        a = ["/", "/a", "/a/b"]
        assert util.ancestry(p) == a

    def test_ancestry_works_on_dir(self):
        p = "/a/b/c/"
        a = ["/", "/a", "/a/b", "/a/b/c"]
        assert util.ancestry(p) == a

    def test_ancestry_works_on_relative(self):
        p = "a/b/c"
        a = ["a", "a/b"]
        assert util.ancestry(p) == a

    def test_components_works_on_file(self):
        p = "/a/b/c"
        a = ["/", "a", "b", "c"]
        assert util.components(p) == a

    def test_components_works_on_dir(self):
        p = "/a/b/c/"
        a = ["/", "a", "b", "c"]
        assert util.components(p) == a

    def test_components_works_on_relative(self):
        p = "a/b/c"
        a = ["a", "b", "c"]
        assert util.components(p) == a

    def test_forward_slash(self):
        p = rb"C:\a\b\c"
        a = rb"C:/a/b/c"
        assert util.path_as_posix(p) == a


class FilePathTestCase(BeetsTestCase):
    def setUp(self):
        super().setUp()

        self.path = self.temp_dir_path / "testfile"
        self.path.touch()


# Tests that we can "delete" nonexistent files.
class SoftRemoveTest(FilePathTestCase):
    def test_soft_remove_deletes_file(self):
        util.remove(self.path, True)
        assert not self.path.exists()

    def test_soft_remove_silent_on_no_file(self):
        try:
            util.remove(self.path / "XXX", True)
        except OSError:
            self.fail("OSError when removing path")


class SafeMoveCopyTest(FilePathTestCase):
    def setUp(self):
        super().setUp()

        self.otherpath = self.temp_dir_path / "testfile2"
        self.otherpath.touch()
        self.dest = Path(f"{self.path}.dest")

    def test_successful_move(self):
        util.move(self.path, self.dest)
        assert self.dest.exists()
        assert not self.path.exists()

    def test_successful_copy(self):
        util.copy(self.path, self.dest)
        assert self.dest.exists()
        assert self.path.exists()

    @NEEDS_REFLINK
    def test_successful_reflink(self):
        util.reflink(str(self.path), str(self.dest))
        assert self.dest.exists()
        assert self.path.exists()

    def test_unsuccessful_move(self):
        with pytest.raises(util.FilesystemError):
            util.move(self.path, self.otherpath)

    def test_unsuccessful_copy(self):
        with pytest.raises(util.FilesystemError):
            util.copy(self.path, self.otherpath)

    def test_unsuccessful_reflink(self):
        with pytest.raises(util.FilesystemError, match="target exists"):
            util.reflink(self.path, self.otherpath)

    def test_self_move(self):
        util.move(self.path, self.path)
        assert self.path.exists()

    def test_self_copy(self):
        util.copy(self.path, self.path)
        assert self.path.exists()


class PruneTest(BeetsTestCase):
    def setUp(self):
        super().setUp()

        self.base = self.temp_dir_path / "testdir"
        self.base.mkdir()
        self.sub = self.base / "subdir"
        self.sub.mkdir()

    def test_prune_existent_directory(self):
        util.prune_dirs(self.sub, self.base)
        assert self.base.exists()
        assert not self.sub.exists()

    def test_prune_nonexistent_directory(self):
        util.prune_dirs(self.sub / "another", self.base)
        assert self.base.exists()
        assert not self.sub.exists()


class WalkTest(BeetsTestCase):
    def setUp(self):
        super().setUp()

        self.base = os.path.join(self.temp_dir, b"testdir")
        os.mkdir(syspath(self.base))
        touch(os.path.join(self.base, b"y"))
        touch(os.path.join(self.base, b"x"))
        os.mkdir(syspath(os.path.join(self.base, b"d")))
        touch(os.path.join(self.base, b"d", b"z"))

    def test_sorted_files(self):
        res = list(util.sorted_walk(self.base))
        assert len(res) == 2
        assert res[0] == (self.base, [b"d"], [b"x", b"y"])
        assert res[1] == (os.path.join(self.base, b"d"), [], [b"z"])

    def test_ignore_file(self):
        res = list(util.sorted_walk(self.base, (b"x",)))
        assert len(res) == 2
        assert res[0] == (self.base, [b"d"], [b"y"])
        assert res[1] == (os.path.join(self.base, b"d"), [], [b"z"])

    def test_ignore_directory(self):
        res = list(util.sorted_walk(self.base, (b"d",)))
        assert len(res) == 1
        assert res[0] == (self.base, [], [b"x", b"y"])

    def test_ignore_everything(self):
        res = list(util.sorted_walk(self.base, (b"*",)))
        assert len(res) == 1
        assert res[0] == (self.base, [], [])


class UniquePathTest(BeetsTestCase):
    def setUp(self):
        super().setUp()

        self.base = os.path.join(self.temp_dir, b"testdir")
        os.mkdir(syspath(self.base))
        touch(os.path.join(self.base, b"x.mp3"))
        touch(os.path.join(self.base, b"x.1.mp3"))
        touch(os.path.join(self.base, b"x.2.mp3"))
        touch(os.path.join(self.base, b"y.mp3"))

    def test_new_file_unchanged(self):
        path = util.unique_path(os.path.join(self.base, b"z.mp3"))
        assert path == os.path.join(self.base, b"z.mp3")

    def test_conflicting_file_appends_1(self):
        path = util.unique_path(os.path.join(self.base, b"y.mp3"))
        assert path == os.path.join(self.base, b"y.1.mp3")

    def test_conflicting_file_appends_higher_number(self):
        path = util.unique_path(os.path.join(self.base, b"x.mp3"))
        assert path == os.path.join(self.base, b"x.3.mp3")

    def test_conflicting_file_with_number_increases_number(self):
        path = util.unique_path(os.path.join(self.base, b"x.1.mp3"))
        assert path == os.path.join(self.base, b"x.3.mp3")


class MkDirAllTest(BeetsTestCase):
    def test_mkdirall(self):
        child = self.temp_dir_path / "foo" / "bar" / "baz" / "quz.mp3"
        util.mkdirall(child)
        assert not child.exists()
        assert child.parent.exists()
        assert child.parent.is_dir()
