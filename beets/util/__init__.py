# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

"""Miscellaneous utility functions."""

import errno
import fnmatch
import functools
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import traceback
from collections import Counter, namedtuple
from enum import Enum
from logging import Logger
from multiprocessing.pool import ThreadPool
from typing import (
    Any,
    AnyStr,
    Callable,
    Generator,
    Iterable,
    List,
    MutableSequence,
    Optional,
    Pattern,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)

from typing_extensions import TypeAlias
from unidecode import unidecode

from beets.util import hidden

MAX_FILENAME_LENGTH = 200
WINDOWS_MAGIC_PREFIX = "\\\\?\\"
T = TypeVar("T")
Bytes_or_String: TypeAlias = Union[str, bytes]


class HumanReadableException(Exception):
    """An Exception that can include a human-readable error message to
    be logged without a traceback. Can preserve a traceback for
    debugging purposes as well.

    Has at least two fields: `reason`, the underlying exception or a
    string describing the problem; and `verb`, the action being
    performed during the error.

    If `tb` is provided, it is a string containing a traceback for the
    associated exception. (Note that this is not necessary in Python 3.x
    and should be removed when we make the transition.)
    """

    error_kind = "Error"  # Human-readable description of error type.

    def __init__(self, reason, verb, tb=None):
        self.reason = reason
        self.verb = verb
        self.tb = tb
        super().__init__(self.get_message())

    def _gerund(self):
        """Generate a (likely) gerund form of the English verb."""
        if " " in self.verb:
            return self.verb
        gerund = self.verb[:-1] if self.verb.endswith("e") else self.verb
        gerund += "ing"
        return gerund

    def _reasonstr(self):
        """Get the reason as a string."""
        if isinstance(self.reason, str):
            return self.reason
        elif isinstance(self.reason, bytes):
            return self.reason.decode("utf-8", "ignore")
        elif hasattr(self.reason, "strerror"):  # i.e., EnvironmentError
            return self.reason.strerror
        else:
            return '"{}"'.format(str(self.reason))

    def get_message(self):
        """Create the human-readable description of the error, sans
        introduction.
        """
        raise NotImplementedError

    def log(self, logger):
        """Log to the provided `logger` a human-readable message as an
        error and a verbose traceback as a debug message.
        """
        if self.tb:
            logger.debug(self.tb)
        logger.error("{0}: {1}", self.error_kind, self.args[0])


class FilesystemError(HumanReadableException):
    """An error that occurred while performing a filesystem manipulation
    via a function in this module. The `paths` field is a sequence of
    pathnames involved in the operation.
    """

    def __init__(self, reason, verb, paths, tb=None):
        self.paths = paths
        super().__init__(reason, verb, tb)

    def get_message(self):
        # Use a nicer English phrasing for some specific verbs.
        if self.verb in ("move", "copy", "rename"):
            clause = "while {} {} to {}".format(
                self._gerund(),
                displayable_path(self.paths[0]),
                displayable_path(self.paths[1]),
            )
        elif self.verb in ("delete", "write", "create", "read"):
            clause = "while {} {}".format(
                self._gerund(), displayable_path(self.paths[0])
            )
        else:
            clause = "during {} of paths {}".format(
                self.verb, ", ".join(displayable_path(p) for p in self.paths)
            )

        return f"{self._reasonstr()} {clause}"


class MoveOperation(Enum):
    """The file operations that e.g. various move functions can carry out."""

    MOVE = 0
    COPY = 1
    LINK = 2
    HARDLINK = 3
    REFLINK = 4
    REFLINK_AUTO = 5


def normpath(path: bytes) -> bytes:
    """Provide the canonical form of the path suitable for storing in
    the database.
    """
    path = syspath(path, prefix=False)
    path = os.path.normpath(os.path.abspath(os.path.expanduser(path)))
    return bytestring_path(path)


def ancestry(path: bytes) -> List[str]:
    """Return a list consisting of path's parent directory, its
    grandparent, and so on. For instance:

       >>> ancestry(b'/a/b/c')
       ['/', '/a', '/a/b']

    The argument should *not* be the result of a call to `syspath`.
    """
    out = []
    last_path = None
    while path:
        path = os.path.dirname(path)

        if path == last_path:
            break
        last_path = path

        if path:
            # don't yield ''
            out.insert(0, path)
    return out


def sorted_walk(
    path: AnyStr,
    ignore: Sequence = (),
    ignore_hidden: bool = False,
    logger: Optional[Logger] = None,
) -> Generator[Tuple, None, None]:
    """Like `os.walk`, but yields things in case-insensitive sorted,
    breadth-first order.  Directory and file names matching any glob
    pattern in `ignore` are skipped. If `logger` is provided, then
    warning messages are logged there when a directory cannot be listed.
    """
    # Make sure the paths aren't Unicode strings.
    path = bytestring_path(path)
    ignore = [bytestring_path(i) for i in ignore]

    # Get all the directories and files at this level.
    try:
        contents = os.listdir(syspath(path))
    except OSError as exc:
        if logger:
            logger.warning(
                "could not list directory {}: {}".format(
                    displayable_path(path), exc.strerror
                )
            )
        return
    dirs = []
    files = []
    for base in contents:
        base = bytestring_path(base)

        # Skip ignored filenames.
        skip = False
        for pat in ignore:
            if fnmatch.fnmatch(base, pat):
                if logger:
                    logger.debug(
                        "ignoring {} due to ignore rule {}".format(base, pat)
                    )
                skip = True
                break
        if skip:
            continue

        # Add to output as either a file or a directory.
        cur = os.path.join(path, base)
        if (ignore_hidden and not hidden.is_hidden(cur)) or not ignore_hidden:
            if os.path.isdir(syspath(cur)):
                dirs.append(base)
            else:
                files.append(base)

    # Sort lists (case-insensitive) and yield the current level.
    dirs.sort(key=bytes.lower)
    files.sort(key=bytes.lower)
    yield (path, dirs, files)

    # Recurse into directories.
    for base in dirs:
        cur = os.path.join(path, base)
        # yield from sorted_walk(...)
        yield from sorted_walk(cur, ignore, ignore_hidden, logger)


def path_as_posix(path: bytes) -> bytes:
    """Return the string representation of the path with forward (/)
    slashes.
    """
    return path.replace(b"\\", b"/")


def mkdirall(path: bytes):
    """Make all the enclosing directories of path (like mkdir -p on the
    parent).
    """
    for ancestor in ancestry(path):
        if not os.path.isdir(syspath(ancestor)):
            try:
                os.mkdir(syspath(ancestor))
            except OSError as exc:
                raise FilesystemError(
                    exc, "create", (ancestor,), traceback.format_exc()
                )


def fnmatch_all(names: Sequence[bytes], patterns: Sequence[bytes]) -> bool:
    """Determine whether all strings in `names` match at least one of
    the `patterns`, which should be shell glob expressions.
    """
    for name in names:
        matches = False
        for pattern in patterns:
            matches = fnmatch.fnmatch(name, pattern)
            if matches:
                break
        if not matches:
            return False
    return True


def prune_dirs(
    path: str,
    root: Optional[Bytes_or_String] = None,
    clutter: Sequence[str] = (".DS_Store", "Thumbs.db"),
):
    """If path is an empty directory, then remove it. Recursively remove
    path's ancestry up to root (which is never removed) where there are
    empty directories. If path is not contained in root, then nothing is
    removed. Glob patterns in clutter are ignored when determining
    emptiness. If root is not provided, then only path may be removed
    (i.e., no recursive removal).
    """
    path = normpath(path)
    if root is not None:
        root = normpath(root)

    ancestors = ancestry(path)
    if root is None:
        # Only remove the top directory.
        ancestors = []
    elif root in ancestors:
        # Only remove directories below the root.
        ancestors = ancestors[ancestors.index(root) + 1 :]
    else:
        # Remove nothing.
        return

    # Traverse upward from path.
    ancestors.append(path)
    ancestors.reverse()
    for directory in ancestors:
        directory = syspath(directory)
        if not os.path.exists(directory):
            # Directory gone already.
            continue
        clutter: List[bytes] = [bytestring_path(c) for c in clutter]
        match_paths = [bytestring_path(d) for d in os.listdir(directory)]
        try:
            if fnmatch_all(match_paths, clutter):
                # Directory contains only clutter (or nothing).
                shutil.rmtree(directory)
            else:
                break
        except OSError:
            break


def components(path: AnyStr) -> MutableSequence[AnyStr]:
    """Return a list of the path components in path. For instance:

       >>> components(b'/a/b/c')
       ['a', 'b', 'c']

    The argument should *not* be the result of a call to `syspath`.
    """
    comps = []
    ances = ancestry(path)
    for anc in ances:
        comp = os.path.basename(anc)
        if comp:
            comps.append(comp)
        else:  # root
            comps.append(anc)

    last = os.path.basename(path)
    if last:
        comps.append(last)

    return comps


def arg_encoding() -> str:
    """Get the encoding for command-line arguments (and other OS
    locale-sensitive strings).
    """
    return sys.getfilesystemencoding()


def _fsencoding() -> str:
    """Get the system's filesystem encoding. On Windows, this is always
    UTF-8 (not MBCS).
    """
    encoding = sys.getfilesystemencoding() or sys.getdefaultencoding()
    if encoding == "mbcs":
        # On Windows, a broken encoding known to Python as "MBCS" is
        # used for the filesystem. However, we only use the Unicode API
        # for Windows paths, so the encoding is actually immaterial so
        # we can avoid dealing with this nastiness. We arbitrarily
        # choose UTF-8.
        encoding = "utf-8"
    return encoding


def bytestring_path(path: Bytes_or_String) -> bytes:
    """Given a path, which is either a bytes or a unicode, returns a str
    path (ensuring that we never deal with Unicode pathnames). Path should be
    bytes but has safeguards for strings to be converted.
    """
    # Pass through bytestrings.
    if isinstance(path, bytes):
        return path

    # On Windows, remove the magic prefix added by `syspath`. This makes
    # ``bytestring_path(syspath(X)) == X``, i.e., we can safely
    # round-trip through `syspath`.
    if os.path.__name__ == "ntpath" and path.startswith(WINDOWS_MAGIC_PREFIX):
        path = path[len(WINDOWS_MAGIC_PREFIX) :]

    # Try to encode with default encodings, but fall back to utf-8.
    try:
        return path.encode(_fsencoding())
    except (UnicodeError, LookupError):
        return path.encode("utf-8")


PATH_SEP: bytes = bytestring_path(os.sep)


def displayable_path(
    path: Union[bytes, str, Tuple[Union[bytes, str], ...]],
    separator: str = "; ",
) -> str:
    """Attempts to decode a bytestring path to a unicode object for the
    purpose of displaying it to the user. If the `path` argument is a
    list or a tuple, the elements are joined with `separator`.
    """
    if isinstance(path, (list, tuple)):
        return separator.join(displayable_path(p) for p in path)
    elif isinstance(path, str):
        return path
    elif not isinstance(path, bytes):
        # A non-string object: just get its unicode representation.
        return str(path)

    try:
        return path.decode(_fsencoding(), "ignore")
    except (UnicodeError, LookupError):
        return path.decode("utf-8", "ignore")


def syspath(path: Bytes_or_String, prefix: bool = True) -> Bytes_or_String:
    """Convert a path for use by the operating system. In particular,
    paths on Windows must receive a magic prefix and must be converted
    to Unicode before they are sent to the OS. To disable the magic
    prefix on Windows, set `prefix` to False---but only do this if you
    *really* know what you're doing.
    """
    # Don't do anything if we're not on windows
    if os.path.__name__ != "ntpath":
        return path

    if not isinstance(path, str):
        # Beets currently represents Windows paths internally with UTF-8
        # arbitrarily. But earlier versions used MBCS because it is
        # reported as the FS encoding by Windows. Try both.
        try:
            path = path.decode("utf-8")
        except UnicodeError:
            # The encoding should always be MBCS, Windows' broken
            # Unicode representation.
            assert isinstance(path, bytes)
            encoding = sys.getfilesystemencoding() or sys.getdefaultencoding()
            path = path.decode(encoding, "replace")

    # Add the magic prefix if it isn't already there.
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa365247.aspx
    if prefix and not path.startswith(WINDOWS_MAGIC_PREFIX):
        if path.startswith("\\\\"):
            # UNC path. Final path should look like \\?\UNC\...
            path = "UNC" + path[1:]
        path = WINDOWS_MAGIC_PREFIX + path

    return path


def samefile(p1: bytes, p2: bytes) -> bool:
    """Safer equality for paths."""
    if p1 == p2:
        return True
    return shutil._samefile(syspath(p1), syspath(p2))


def remove(path: Optional[bytes], soft: bool = True):
    """Remove the file. If `soft`, then no error will be raised if the
    file does not exist.
    """
    path = syspath(path)
    if not path or (soft and not os.path.exists(path)):
        return
    try:
        os.remove(path)
    except OSError as exc:
        raise FilesystemError(exc, "delete", (path,), traceback.format_exc())


def copy(path: bytes, dest: bytes, replace: bool = False):
    """Copy a plain file. Permissions are not copied. If `dest` already
    exists, raises a FilesystemError unless `replace` is True. Has no
    effect if `path` is the same as `dest`. Paths are translated to
    system paths before the syscall.
    """
    if samefile(path, dest):
        return
    path = syspath(path)
    dest = syspath(dest)
    if not replace and os.path.exists(dest):
        raise FilesystemError("file exists", "copy", (path, dest))
    try:
        shutil.copyfile(path, dest)
    except OSError as exc:
        raise FilesystemError(exc, "copy", (path, dest), traceback.format_exc())


def move(path: bytes, dest: bytes, replace: bool = False):
    """Rename a file. `dest` may not be a directory. If `dest` already
    exists, raises an OSError unless `replace` is True. Has no effect if
    `path` is the same as `dest`. If the paths are on different
    filesystems (or the rename otherwise fails), a copy is attempted
    instead, in which case metadata will *not* be preserved. Paths are
    translated to system paths.
    """
    if os.path.isdir(syspath(path)):
        raise FilesystemError("source is directory", "move", (path, dest))
    if os.path.isdir(syspath(dest)):
        raise FilesystemError("destination is directory", "move", (path, dest))
    if samefile(path, dest):
        return
    if os.path.exists(syspath(dest)) and not replace:
        raise FilesystemError("file exists", "rename", (path, dest))

    # First, try renaming the file.
    try:
        os.replace(syspath(path), syspath(dest))
    except OSError:
        # Copy the file to a temporary destination.
        basename = os.path.basename(bytestring_path(dest))
        dirname = os.path.dirname(bytestring_path(dest))
        tmp = tempfile.NamedTemporaryFile(
            suffix=syspath(b".beets", prefix=False),
            prefix=syspath(b"." + basename, prefix=False),
            dir=syspath(dirname),
            delete=False,
        )
        try:
            with open(syspath(path), "rb") as f:
                shutil.copyfileobj(f, tmp)
        finally:
            tmp.close()

        # Move the copied file into place.
        try:
            os.replace(tmp.name, syspath(dest))
            tmp = None
            os.remove(syspath(path))
        except OSError as exc:
            raise FilesystemError(
                exc, "move", (path, dest), traceback.format_exc()
            )
        finally:
            if tmp is not None:
                os.remove(tmp)


def link(path: bytes, dest: bytes, replace: bool = False):
    """Create a symbolic link from path to `dest`. Raises an OSError if
    `dest` already exists, unless `replace` is True. Does nothing if
    `path` == `dest`.
    """
    if samefile(path, dest):
        return

    if os.path.exists(syspath(dest)) and not replace:
        raise FilesystemError("file exists", "rename", (path, dest))
    try:
        os.symlink(syspath(path), syspath(dest))
    except NotImplementedError:
        # raised on python >= 3.2 and Windows versions before Vista
        raise FilesystemError(
            "OS does not support symbolic links." "link",
            (path, dest),
            traceback.format_exc(),
        )
    except OSError as exc:
        raise FilesystemError(exc, "link", (path, dest), traceback.format_exc())


def hardlink(path: bytes, dest: bytes, replace: bool = False):
    """Create a hard link from path to `dest`. Raises an OSError if
    `dest` already exists, unless `replace` is True. Does nothing if
    `path` == `dest`.
    """
    if samefile(path, dest):
        return

    if os.path.exists(syspath(dest)) and not replace:
        raise FilesystemError("file exists", "rename", (path, dest))
    try:
        os.link(syspath(path), syspath(dest))
    except NotImplementedError:
        raise FilesystemError(
            "OS does not support hard links." "link",
            (path, dest),
            traceback.format_exc(),
        )
    except OSError as exc:
        if exc.errno == errno.EXDEV:
            raise FilesystemError(
                "Cannot hard link across devices." "link",
                (path, dest),
                traceback.format_exc(),
            )
        else:
            raise FilesystemError(
                exc, "link", (path, dest), traceback.format_exc()
            )


def reflink(
    path: bytes,
    dest: bytes,
    replace: bool = False,
    fallback: bool = False,
):
    """Create a reflink from `dest` to `path`.

    Raise an `OSError` if `dest` already exists, unless `replace` is
    True. If `path` == `dest`, then do nothing.

    If reflinking fails and `fallback` is enabled, try copying the file
    instead. Otherwise, raise an error without trying a plain copy.

    May raise an `ImportError` if the `reflink` module is not available.
    """
    import reflink as pyreflink

    if samefile(path, dest):
        return

    if os.path.exists(syspath(dest)) and not replace:
        raise FilesystemError("file exists", "rename", (path, dest))

    try:
        pyreflink.reflink(path, dest)
    except (NotImplementedError, pyreflink.ReflinkImpossibleError):
        if fallback:
            copy(path, dest, replace)
        else:
            raise FilesystemError(
                "OS/filesystem does not support reflinks.",
                "link",
                (path, dest),
                traceback.format_exc(),
            )


def unique_path(path: bytes) -> bytes:
    """Returns a version of ``path`` that does not exist on the
    filesystem. Specifically, if ``path` itself already exists, then
    something unique is appended to the path.
    """
    if not os.path.exists(syspath(path)):
        return path

    base, ext = os.path.splitext(path)
    match = re.search(rb"\.(\d)+$", base)
    if match:
        num = int(match.group(1))
        base = base[: match.start()]
    else:
        num = 0
    while True:
        num += 1
        suffix = f".{num}".encode() + ext
        new_path = base + suffix
        if not os.path.exists(new_path):
            return new_path


# Note: The Windows "reserved characters" are, of course, allowed on
# Unix. They are forbidden here because they cause problems on Samba
# shares, which are sufficiently common as to cause frequent problems.
# https://msdn.microsoft.com/en-us/library/windows/desktop/aa365247.aspx
CHAR_REPLACE: List[Tuple[Pattern, str]] = [
    (re.compile(r"[\\/]"), "_"),  # / and \ -- forbidden everywhere.
    (re.compile(r"^\."), "_"),  # Leading dot (hidden files on Unix).
    (re.compile(r"[\x00-\x1f]"), ""),  # Control characters.
    (re.compile(r'[<>:"\?\*\|]'), "_"),  # Windows "reserved characters".
    (re.compile(r"\.$"), "_"),  # Trailing dots.
    (re.compile(r"\s+$"), ""),  # Trailing whitespace.
]


def sanitize_path(
    path: str,
    replacements: Optional[Sequence[Sequence[Union[Pattern, str]]]] = None,
) -> str:
    """Takes a path (as a Unicode string) and makes sure that it is
    legal. Returns a new path. Only works with fragments; won't work
    reliably on Windows when a path begins with a drive letter. Path
    separators (including altsep!) should already be cleaned from the
    path components. If replacements is specified, it is used *instead*
    of the default set of replacements; it must be a list of (compiled
    regex, replacement string) pairs.
    """
    replacements = replacements or CHAR_REPLACE

    comps = components(path)
    if not comps:
        return ""
    for i, comp in enumerate(comps):
        for regex, repl in replacements:
            comp = regex.sub(repl, comp)
        comps[i] = comp
    return os.path.join(*comps)


def truncate_path(path: AnyStr, length: int = MAX_FILENAME_LENGTH) -> AnyStr:
    """Given a bytestring path or a Unicode path fragment, truncate the
    components to a legal length. In the last component, the extension
    is preserved.
    """
    comps = components(path)

    out = [c[:length] for c in comps]
    base, ext = os.path.splitext(comps[-1])
    if ext:
        # Last component has an extension.
        base = base[: length - len(ext)]
        out[-1] = base + ext

    return os.path.join(*out)


def _legalize_stage(
    path: str,
    replacements: Optional[Sequence[Sequence[Union[Pattern, str]]]],
    length: int,
    extension: str,
    fragment: bool,
) -> Tuple[Bytes_or_String, bool]:
    """Perform a single round of path legalization steps
    (sanitation/replacement, encoding from Unicode to bytes,
    extension-appending, and truncation). Return the path (Unicode if
    `fragment` is set, `bytes` otherwise) and whether truncation was
    required.
    """
    # Perform an initial sanitization including user replacements.
    path = sanitize_path(path, replacements)

    # Encode for the filesystem.
    if not fragment:
        path = bytestring_path(path)  # type: ignore

    # Preserve extension.
    path += extension.lower()

    # Truncate too-long components.
    pre_truncate_path = path
    path = truncate_path(path, length)

    return path, path != pre_truncate_path


def legalize_path(
    path: str,
    replacements: Optional[Sequence[Sequence[Union[Pattern, str]]]],
    length: int,
    extension: bytes,
    fragment: bool,
) -> Tuple[Union[Bytes_or_String, bool]]:
    """Given a path-like Unicode string, produce a legal path. Return
    the path and a flag indicating whether some replacements had to be
    ignored (see below).

    The legalization process (see `_legalize_stage`) consists of
    applying the sanitation rules in `replacements`, encoding the string
    to bytes (unless `fragment` is set), truncating components to
    `length`, appending the `extension`.

    This function performs up to three calls to `_legalize_stage` in
    case truncation conflicts with replacements (as can happen when
    truncation creates whitespace at the end of the string, for
    example). The limited number of iterations iterations avoids the
    possibility of an infinite loop of sanitation and truncation
    operations, which could be caused by replacement rules that make the
    string longer. The flag returned from this function indicates that
    the path has to be truncated twice (indicating that replacements
    made the string longer again after it was truncated); the
    application should probably log some sort of warning.
    """

    if fragment:
        # Outputting Unicode.
        extension = extension.decode("utf-8", "ignore")

    first_stage_path, _ = _legalize_stage(
        path, replacements, length, extension, fragment
    )

    # Convert back to Unicode with extension removed.
    first_stage_path, _ = os.path.splitext(displayable_path(first_stage_path))

    # Re-sanitize following truncation (including user replacements).
    second_stage_path, retruncated = _legalize_stage(
        first_stage_path, replacements, length, extension, fragment
    )

    # If the path was once again truncated, discard user replacements
    # and run through one last legalization stage.
    if retruncated:
        second_stage_path, _ = _legalize_stage(
            first_stage_path, None, length, extension, fragment
        )

    return second_stage_path, retruncated


def py3_path(path: Union[bytes, str]) -> str:
    """Convert a bytestring path to Unicode.

    This helps deal with APIs on Python 3 that *only* accept Unicode
    (i.e., `str` objects). I philosophically disagree with this
    decision, because paths are sadly bytes on Unix, but that's the way
    it is. So this function helps us "smuggle" the true bytes data
    through APIs that took Python 3's Unicode mandate too seriously.
    """
    if isinstance(path, str):
        return path
    assert isinstance(path, bytes)
    return os.fsdecode(path)


def str2bool(value: str) -> bool:
    """Returns a boolean reflecting a human-entered string."""
    return value.lower() in ("yes", "1", "true", "t", "y")


def as_string(value: Any) -> str:
    """Convert a value to a Unicode object for matching with a query.
    None becomes the empty string. Bytestrings are silently decoded.
    """
    if value is None:
        return ""
    elif isinstance(value, memoryview):
        return bytes(value).decode("utf-8", "ignore")
    elif isinstance(value, bytes):
        return value.decode("utf-8", "ignore")
    else:
        return str(value)


def plurality(objs: Sequence[T]) -> T:
    """Given a sequence of hashble objects, returns the object that
    is most common in the set and the its number of appearance. The
    sequence must contain at least one object.
    """
    c = Counter(objs)
    if not c:
        raise ValueError("sequence must be non-empty")
    return c.most_common(1)[0]


def cpu_count() -> int:
    """Return the number of hardware thread contexts (cores or SMT
    threads) in the system.
    """
    # Adapted from the soundconverter project:
    # https://github.com/kassoulet/soundconverter
    if sys.platform == "win32":
        try:
            num = int(os.environ["NUMBER_OF_PROCESSORS"])
        except (ValueError, KeyError):
            num = 0
    elif sys.platform == "darwin":
        try:
            num = int(
                command_output(
                    [
                        "/usr/sbin/sysctl",
                        "-n",
                        "hw.ncpu",
                    ]
                ).stdout
            )
        except (ValueError, OSError, subprocess.CalledProcessError):
            num = 0
    else:
        try:
            num = os.sysconf("SC_NPROCESSORS_ONLN")
        except (ValueError, OSError, AttributeError):
            num = 0
    if num >= 1:
        return num
    else:
        return 1


def convert_command_args(args: List[bytes]) -> List[str]:
    """Convert command arguments, which may either be `bytes` or `str`
    objects, to uniformly surrogate-escaped strings."""
    assert isinstance(args, list)

    def convert(arg) -> str:
        if isinstance(arg, bytes):
            return os.fsdecode(arg)
        return arg

    return [convert(a) for a in args]


# stdout and stderr as bytes
CommandOutput = namedtuple("CommandOutput", ("stdout", "stderr"))


def command_output(
    cmd: List[Bytes_or_String],
    shell: bool = False,
) -> CommandOutput:
    """Runs the command and returns its output after it has exited.

    Returns a CommandOutput. The attributes ``stdout`` and ``stderr`` contain
    byte strings of the respective output streams.

    ``cmd`` is a list of arguments starting with the command names. The
    arguments are bytes on Unix and strings on Windows.
    If ``shell`` is true, ``cmd`` is assumed to be a string and passed to a
    shell to execute.

    If the process exits with a non-zero return code
    ``subprocess.CalledProcessError`` is raised. May also raise
    ``OSError``.

    This replaces `subprocess.check_output` which can have problems if lots of
    output is sent to stderr.
    """
    cmd = convert_command_args(cmd)

    devnull = subprocess.DEVNULL

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=devnull,
        close_fds=platform.system() != "Windows",
        shell=shell,
    )
    stdout, stderr = proc.communicate()
    if proc.returncode:
        raise subprocess.CalledProcessError(
            returncode=proc.returncode,
            cmd=" ".join(cmd),
            output=stdout + stderr,
        )
    return CommandOutput(stdout, stderr)


def max_filename_length(path: AnyStr, limit=MAX_FILENAME_LENGTH) -> int:
    """Attempt to determine the maximum filename length for the
    filesystem containing `path`. If the value is greater than `limit`,
    then `limit` is used instead (to prevent errors when a filesystem
    misreports its capacity). If it cannot be determined (e.g., on
    Windows), return `limit`.
    """
    if hasattr(os, "statvfs"):
        try:
            res = os.statvfs(path)
        except OSError:
            return limit
        return min(res[9], limit)
    else:
        return limit


def open_anything() -> str:
    """Return the system command that dispatches execution to the correct
    program.
    """
    sys_name = platform.system()
    if sys_name == "Darwin":
        base_cmd = "open"
    elif sys_name == "Windows":
        base_cmd = "start"
    else:  # Assume Unix
        base_cmd = "xdg-open"
    return base_cmd


def editor_command() -> str:
    """Get a command for opening a text file.

    First try environment variable `VISUAL` followed by `EDITOR`. As last resort
    fall back to `open_anything()`, the platform-specific tool for opening files
    in general.

    """
    return (
        os.environ.get("VISUAL") or os.environ.get("EDITOR") or open_anything()
    )


def interactive_open(targets: Sequence[str], command: str):
    """Open the files in `targets` by `exec`ing a new `command`, given
    as a Unicode string. (The new program takes over, and Python
    execution ends: this does not fork a subprocess.)

    Can raise `OSError`.
    """
    assert command

    # Split the command string into its arguments.
    try:
        args = shlex.split(command)
    except ValueError:  # Malformed shell tokens.
        args = [command]

    args.insert(0, args[0])  # for argv[0]

    args += targets

    return os.execlp(*args)


def case_sensitive(path: bytes) -> bool:
    """Check whether the filesystem at the given path is case sensitive.

    To work best, the path should point to a file or a directory. If the path
    does not exist, assume a case sensitive file system on every platform
    except Windows.

    Currently only used for absolute paths by beets; may have a trailing
    path separator.
    """
    # Look at parent paths until we find a path that actually exists, or
    # reach the root.
    while True:
        head, tail = os.path.split(path)
        if head == path:
            # We have reached the root of the file system.
            # By default, the case sensitivity depends on the platform.
            return platform.system() != "Windows"

        # Trailing path separator, or path does not exist.
        if not tail or not os.path.exists(path):
            path = head
            continue

        upper_tail = tail.upper()
        lower_tail = tail.lower()

        # In case we can't tell from the given path name, look at the
        # parent directory.
        if upper_tail == lower_tail:
            path = head
            continue

        upper_sys = syspath(os.path.join(head, upper_tail))
        lower_sys = syspath(os.path.join(head, lower_tail))

        # If either the upper-cased or lower-cased path does not exist, the
        # filesystem must be case-sensitive.
        # (Otherwise, we have more work to do.)
        if not os.path.exists(upper_sys) or not os.path.exists(lower_sys):
            return True

        # Original and both upper- and lower-cased versions of the path
        # exist on the file system. Check whether they refer to different
        # files by their inodes (or an alternative method on Windows).
        return not os.path.samefile(lower_sys, upper_sys)


def raw_seconds_short(string: str) -> float:
    """Formats a human-readable M:SS string as a float (number of seconds).

    Raises ValueError if the conversion cannot take place due to `string` not
    being in the right format.
    """
    match = re.match(r"^(\d+):([0-5]\d)$", string)
    if not match:
        raise ValueError("String not in M:SS format")
    minutes, seconds = map(int, match.groups())
    return float(minutes * 60 + seconds)


def asciify_path(path: str, sep_replace: str) -> str:
    """Decodes all unicode characters in a path into ASCII equivalents.

    Substitutions are provided by the unidecode module. Path separators in the
    input are preserved.

    Keyword arguments:
    path -- The path to be asciified.
    sep_replace -- the string to be used to replace extraneous path separators.
    """
    # if this platform has an os.altsep, change it to os.sep.
    if os.altsep:
        path = path.replace(os.altsep, os.sep)
    path_components: List[Bytes_or_String] = path.split(os.sep)
    for index, item in enumerate(path_components):
        path_components[index] = unidecode(item).replace(os.sep, sep_replace)
        if os.altsep:
            path_components[index] = unidecode(item).replace(
                os.altsep, sep_replace
            )
    return os.sep.join(path_components)


def par_map(transform: Callable, items: Iterable):
    """Apply the function `transform` to all the elements in the
    iterable `items`, like `map(transform, items)` but with no return
    value.

    The parallelism uses threads (not processes), so this is only useful
    for IO-bound `transform`s.
    """
    pool = ThreadPool()
    pool.map(transform, items)
    pool.close()
    pool.join()


def lazy_property(func: Callable) -> Callable:
    """A decorator that creates a lazily evaluated property. On first access,
    the property is assigned the return value of `func`. This first value is
    stored, so that future accesses do not have to evaluate `func` again.

    This behaviour is useful when `func` is expensive to evaluate, and it is
    not certain that the result will be needed.
    """
    field_name = "_" + func.__name__

    @property
    @functools.wraps(func)
    def wrapper(self):
        if hasattr(self, field_name):
            return getattr(self, field_name)

        value = func(self)
        setattr(self, field_name, value)
        return value

    return wrapper
