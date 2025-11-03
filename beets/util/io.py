from __future__ import annotations

import errno
import fnmatch
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import traceback
from collections import Counter
from collections.abc import Iterable, Sequence
from contextlib import suppress
from enum import Enum
from functools import cache
from importlib import import_module
from pathlib import Path
from re import Pattern
from typing import IO, TYPE_CHECKING, AnyStr, NamedTuple, TypeVar

from typing_extensions import Final, Unpack, override
from unidecode import unidecode

from beets.config import config
from beets.util.exceptions import HumanReadableError, HumanReadableErrorArgs
from beets.util.hidden import is_hidden

if TYPE_CHECKING:
    from collections.abc import Iterator
    from logging import Logger

    from typing_extensions import TypeAlias


PathLike: TypeAlias = "str | bytes | Path"


class FilesystemErrorArgs(HumanReadableErrorArgs):
    paths: Sequence[bytes | str]


MAX_FILENAME_LENGTH = 200
WINDOWS_MAGIC_PREFIX = "\\\\?\\"
T = TypeVar("T")
_R_co = TypeVar("_R_co", covariant=True)
StrPath: TypeAlias = "str | Path"
Replacements: TypeAlias = Sequence[tuple[Pattern[str], str]]

# Here for now to allow for a easy replace later on
# once we can move to a PathLike (mainly used in importer)
PathBytes: TypeAlias = bytes


class FilesystemError(HumanReadableError):
    """An error that occurred while performing a filesystem manipulation
    via a function in this module. The `paths` field is a sequence of
    pathnames involved in the operation.
    """

    def __init__(self, **kwargs: Unpack[FilesystemErrorArgs]) -> None:
        self.paths: Sequence[bytes | str] = kwargs["paths"]
        super().__init__(
            reason=kwargs["reason"], verb=kwargs["verb"], tb=kwargs.get("tb")
        )

    @override
    def get_message(self):
        # Use a nicer English phrasing for some specific verbs.

        if self.verb in ("move", "copy", "rename"):
            clause = (
                f"while {self._gerund()} {displayable_path(self.paths[0])} to"
                f" {displayable_path(self.paths[1])}"
            )
        elif self.verb in ("delete", "write", "create", "read"):
            clause = f"while {self._gerund()} {displayable_path(self.paths[0])}"
        else:
            clause = (
                f"during {self.verb} of paths"
                f" {', '.join(displayable_path(p) for p in self.paths)}"
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


def normpath(path: PathLike) -> bytes:
    """Provide the canonical form of the path suitable for storing in
    the database.
    """
    str_path: str = syspath(path, prefix=False)
    str_path = os.path.normpath(os.path.abspath(os.path.expanduser(str_path)))
    return bytestring_path(str_path)


def ancestry(path: AnyStr) -> list[AnyStr]:
    """Return a list consisting of path's parent directory, its
    grandparent, and so on. For instance:

       >>> ancestry(b'/a/b/c')
       ['/', '/a', '/a/b']

    The argument should *not* be the result of a call to `syspath`.
    """
    out: list[AnyStr] = []
    last_path: AnyStr | None = None
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
    path: PathLike,
    ignore: Sequence[PathLike] = (),
    ignore_hidden: bool = False,
    logger: Logger | None = None,
) -> Iterator[tuple[bytes, Sequence[bytes], Sequence[bytes]]]:
    """Like `os.walk`, but yields things in case-insensitive sorted,
    breadth-first order.  Directory and file names matching any glob
    pattern in `ignore` are skipped. If `logger` is provided, then
    warning messages are logged there when a directory cannot be listed.
    """
    # Make sure the paths aren't Unicode strings.
    bytes_path: bytes = bytestring_path(path)
    ignore_bytes: list[
        bytes
    ] = [  # rename prevents mypy variable shadowing issue
        bytestring_path(i) for i in ignore
    ]

    # Get all the directories and files at this level.
    contents: list[str]
    try:
        contents = os.listdir(syspath(bytes_path))
    except OSError:
        if logger:
            logger.warning(
                "could not list directory {}",
                displayable_path(bytes_path),
                exc_info=True,
            )
        return
    dirs: list[bytes] = []
    files: list[bytes] = []
    str_base: str
    cur: bytes
    for str_base in contents:
        base: bytes = bytestring_path(str_base)

        # Skip ignored filenames.
        skip: bool = False
        pat: bytes
        for pat in ignore_bytes:
            if fnmatch.fnmatch(base, pat):
                if logger:
                    logger.debug(
                        "ignoring '{}' due to ignore rule '{}'", base, pat
                    )
                skip = True
                break
        if skip:
            continue

        # Add to output as either a file or a directory.
        cur = os.path.join(bytes_path, base)
        if (ignore_hidden and not is_hidden(cur)) or not ignore_hidden:
            if os.path.isdir(syspath(cur)):
                dirs.append(base)
            else:
                files.append(base)

    # Sort lists (case-insensitive) and yield the current level.
    dirs.sort(key=bytes.lower)
    files.sort(key=bytes.lower)
    yield (bytes_path, dirs, files)

    # Recurse into directories.
    for base in dirs:
        cur = os.path.join(bytes_path, base)
        yield from sorted_walk(cur, ignore_bytes, ignore_hidden, logger)


def path_as_posix(path: bytes) -> bytes:
    """Return the string representation of the path with forward (/)
    slashes.
    """
    return path.replace(b"\\", b"/")


def mkdirall(path: bytes) -> None:
    """Make all the enclosing directories of path (like mkdir -p on the
    parent).
    """
    ancestor: bytes
    for ancestor in ancestry(path):
        if not os.path.isdir(syspath(ancestor)):
            try:
                os.mkdir(syspath(ancestor))
            except OSError as exc:
                raise FilesystemError(
                    reason=exc,
                    verb="create",
                    paths=(ancestor,),
                    tb=traceback.format_exc(),
                )


def fnmatch_all(names: Sequence[bytes], patterns: Sequence[bytes]) -> bool:
    """Determine whether all strings in `names` match at least one of
    the `patterns`, which should be shell glob expressions.
    """
    name: bytes
    for name in names:
        matches: bool = False
        pattern: bytes
        for pattern in patterns:
            matches = fnmatch.fnmatch(name, pattern)
            if matches:
                break
        if not matches:
            return False
    return True


def prune_dirs(
    path: PathLike,
    root: PathLike | None = None,
    clutter: Sequence[str] = (".DS_Store", "Thumbs.db"),
) -> None:
    """If path is an empty directory, then remove it. Recursively remove
    path's ancestry up to root (which is never removed) where there are
    empty directories. If path is not contained in root, then nothing is
    removed. Glob patterns in clutter are ignored when determining
    emptiness. If root is not provided, then only path may be removed
    (i.e., no recursive removal).
    """
    path = normpath(path)
    root = normpath(root) if root else None
    ancestors: list[bytes] = ancestry(path)

    if root is None:
        # Only remove the top directory.
        ancestors = []
    elif root in ancestors:
        # Only remove directories below the root_bytes.
        ancestors = ancestors[ancestors.index(root) + 1 :]
    else:
        # Remove nothing.
        return

    bytes_clutter: list[bytes] = [bytestring_path(c) for c in clutter]

    # Traverse upward from path.
    ancestors.append(path)
    ancestors.reverse()
    directory: bytes
    for directory in ancestors:
        str_directory: str = syspath(directory)
        if not os.path.exists(directory):
            # Directory gone already.
            continue
        match_paths: list[bytes] = [
            bytestring_path(d) for d in os.listdir(str_directory)
        ]
        try:
            if fnmatch_all(match_paths, bytes_clutter):
                # Directory contains only clutter (or nothing).
                shutil.rmtree(str_directory)
            else:
                break
        except OSError:
            break


def components(path: AnyStr) -> list[AnyStr]:
    """Return a list of the path components in path. For instance:

       >>> components(b'/a/b/c')
       ['a', 'b', 'c']

    The argument should *not* be the result of a call to `syspath`.
    """
    comps: list[AnyStr] = []
    ances: list[AnyStr] = ancestry(path)
    for anc in ances:
        comp: AnyStr = os.path.basename(anc)
        if comp:
            comps.append(comp)
        else:  # root
            comps.append(anc)

    last: AnyStr = os.path.basename(path)
    if last:
        comps.append(last)

    return comps


def bytestring_path(path: PathLike) -> bytes:
    """Given a path, which is either a bytes or a unicode, returns a str
    path (ensuring that we never deal with Unicode pathnames). Path should be
    bytes but has safeguards for strings to be converted.
    """
    # Pass through bytestrings.
    if isinstance(path, bytes):
        return path

    str_path: str = str(path)

    # On Windows, remove the magic prefix added by `syspath`. This makes
    # ``bytestring_path(syspath(X)) == X``, i.e., we can safely
    # round-trip through `syspath`.
    if os.path.__name__ == "ntpath" and str_path.startswith(
        WINDOWS_MAGIC_PREFIX
    ):
        str_path = str_path[len(WINDOWS_MAGIC_PREFIX) :]

    return os.fsencode(str_path)


PATH_SEP: bytes = bytestring_path(os.sep)


def displayable_path(
    path: PathLike | Iterable[PathLike], separator: str = "; "
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

    return os.fsdecode(path)


def syspath(path: PathLike, prefix: bool = True) -> str:
    """Convert a path for use by the operating system. In particular,
    paths on Windows must receive a magic prefix and must be converted
    to Unicode before they are sent to the OS. To disable the magic
    prefix on Windows, set `prefix` to False---but only do this if you
    *really* know what you're doing.
    """
    str_path: str = os.fsdecode(path)
    # Don't do anything if we're not on windows
    if os.path.__name__ != "ntpath":
        return str_path

    # Add the magic prefix if it isn't already there.
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa365247.aspx
    if prefix and not str_path.startswith(WINDOWS_MAGIC_PREFIX):
        if str_path.startswith("\\\\"):
            # UNC path. Final path should look like \\?\UNC\...
            str_path = f"UNC{str_path[1:]}"
        str_path = f"{WINDOWS_MAGIC_PREFIX}{str_path}"

    return str_path


def samefile(p1: bytes, p2: bytes) -> bool:
    """Safer equality for paths."""
    if p1 == p2:
        return True
    with suppress(OSError):
        return os.path.samefile(syspath(p1), syspath(p2))

    return False


def remove(path: PathLike, soft: bool = True) -> None:
    """Remove the file. If `soft`, then no error will be raised if the
    file does not exist.
    """
    str_path: str = syspath(path)
    if not str_path or (soft and not os.path.exists(str_path)):
        return
    try:
        os.remove(str_path)
    except OSError as exc:
        raise FilesystemError(
            reason=exc,
            verb="delete",
            paths=(str_path,),
            tb=traceback.format_exc(),
        )


def copy(path: bytes, dest: bytes, replace: bool = False) -> None:
    """Copy a plain file. Permissions are not copied. If `dest` already
    exists, raises a FilesystemError unless `replace` is True. Has no
    effect if `path` is the same as `dest`. Paths are translated to
    system paths before the syscall.
    """
    if samefile(path, dest):
        return
    str_path: str = syspath(path)
    str_dest: str = syspath(dest)
    if not replace and os.path.exists(str_dest):
        raise FilesystemError(
            reason="file exists", verb="copy", paths=(str_path, str_dest)
        )
    try:
        _ = shutil.copyfile(str_path, str_dest)
    except OSError as exc:
        raise FilesystemError(
            reason=exc,
            verb="copy",
            paths=(str_path, str_dest),
            tb=traceback.format_exc(),
        )


def move(path: bytes, dest: bytes, replace: bool = False) -> None:
    """Rename a file. `dest` may not be a directory. If `dest` already
    exists, raises an OSError unless `replace` is True. Has no effect if
    `path` is the same as `dest`. Paths are translated to system paths.
    """
    if os.path.isdir(syspath(path)):
        raise FilesystemError(
            reason="source is directory", verb="move", paths=(path, dest)
        )
    if os.path.isdir(syspath(dest)):
        raise FilesystemError(
            reason="destination is directory", verb="move", paths=(path, dest)
        )
    if samefile(path, dest):
        return
    if os.path.exists(syspath(dest)) and not replace:
        raise FilesystemError(
            reason="file exists", verb="rename", paths=(path, dest)
        )

    # First, try renaming the file.
    try:
        os.replace(syspath(path), syspath(dest))
    except OSError:
        # Copy the file to a temporary destination.
        basename: bytes = os.path.basename(bytestring_path(dest))
        dirname: bytes = os.path.dirname(bytestring_path(dest))
        tmp: IO[bytes] = tempfile.NamedTemporaryFile(
            suffix=".beets",
            prefix=f".{os.fsdecode(basename)}.",
            dir=syspath(dirname),
            delete=False,
        )
        try:
            with open(syspath(path), "rb") as f:
                # mypy bug:
                # - https://github.com/python/mypy/issues/15031
                # - https://github.com/python/mypy/issues/14943
                # Fix not yet released:
                # - https://github.com/python/mypy/pull/14975
                shutil.copyfileobj(f, tmp)  # type: ignore[misc]
        finally:
            tmp.close()

        try:
            # Copy file metadata
            shutil.copystat(syspath(path), tmp.name)
        except OSError:
            # Ignore errors because it doesn't matter too much.  We may be on a
            # filesystem that doesn't support this.
            pass

        # Move the copied file into place.
        tmp_filename: str = tmp.name
        try:
            os.replace(tmp_filename, syspath(dest))
            tmp_filename = ""
            os.remove(syspath(path))
        except OSError as exc:
            raise FilesystemError(
                reason=exc,
                verb="move",
                paths=(path, dest),
                tb=traceback.format_exc(),
            )
        finally:
            if tmp_filename:
                os.remove(tmp_filename)


def link(path: bytes, dest: bytes, replace: bool = False) -> None:
    """Create a symbolic link from path to `dest`. Raises an OSError if
    `dest` already exists, unless `replace` is True. Does nothing if
    `path` == `dest`.
    """
    if samefile(path, dest):
        return

    if os.path.exists(syspath(dest)) and not replace:
        raise FilesystemError(
            reason="file exists", verb="rename", paths=(path, dest)
        )
    try:
        os.symlink(syspath(path), syspath(dest))
    except NotImplementedError:
        # raised on python >= 3.2 and Windows versions before Vista
        raise FilesystemError(
            reason="OS does not support symbolic links.link",
            verb="link",
            paths=(path, dest),
            tb=traceback.format_exc(),
        )
    except OSError as exc:
        raise FilesystemError(
            reason=exc,
            verb="link",
            paths=(path, dest),
            tb=traceback.format_exc(),
        )


def hardlink(path: bytes, dest: bytes, replace: bool = False) -> None:
    """Create a hard link from path to `dest`. Raises an OSError if
    `dest` already exists, unless `replace` is True. Does nothing if
    `path` == `dest`.
    """
    if samefile(path, dest):
        return

    if os.path.exists(syspath(dest)) and not replace:
        raise FilesystemError(
            reason="file exists", verb="rename", paths=(path, dest)
        )
    try:
        os.link(syspath(path), syspath(dest))
    except NotImplementedError:
        raise FilesystemError(
            reason="OS does not support hard links.link",
            verb="hardlink",
            paths=(path, dest),
            tb=traceback.format_exc(),
        )
    except OSError as exc:
        if exc.errno == errno.EXDEV:
            raise FilesystemError(
                reason="Cannot hard link across devices.link",
                verb="hardlink",
                paths=(path, dest),
                tb=traceback.format_exc(),
            )
        else:
            raise FilesystemError(
                reason=exc,
                verb="link",
                paths=(path, dest),
                tb=traceback.format_exc(),
            )


def reflink(
    path: bytes,
    dest: bytes,
    replace: bool = False,
    fallback: bool = False,
) -> None:
    """Create a reflink from `dest` to `path`.

    Raise an `OSError` if `dest` already exists, unless `replace` is
    True. If `path` == `dest`, then do nothing.

    If `fallback` is enabled, ignore errors and copy the file instead.
    Otherwise, errors are re-raised as FilesystemError with an explanation.
    """
    if samefile(path, dest):
        return

    if os.path.exists(syspath(dest)) and not replace:
        raise FilesystemError(
            reason="target exists", verb="rename", paths=(path, dest)
        )

    if fallback:
        with suppress(Exception):
            return import_module("reflink").reflink(path, dest)
        return copy(path, dest, replace)

    try:
        import_module("reflink").reflink(path, dest)
    except (ImportError, OSError):
        raise
    except Exception as exc:
        msg: str = {
            "EXDEV": "Cannot reflink across devices",
            "EOPNOTSUPP": "Device does not support reflinks",
        }.get(str(exc), "OS does not support reflinks")

        raise FilesystemError(
            reason=msg,
            verb="reflink",
            paths=(path, dest),
            tb=traceback.format_exc(),
        ) from exc


def unique_path(path: bytes) -> bytes:
    """Returns a version of ``path`` that does not exist on the
    filesystem. Specifically, if ``path` itself already exists, then
    something unique is appended to the path.
    """
    if not os.path.exists(syspath(path)):
        return path

    base: bytes
    ext: bytes
    base, ext = os.path.splitext(path)
    match: re.Match[bytes] | None = re.search(rb"\.(\d)+$", base)
    num: int
    if match:
        num = int(match.group(1))
        base = base[: match.start()]
    else:
        num = 0
    while True:
        num += 1
        suffix: bytes = f".{num}".encode() + ext
        new_path: bytes = base + suffix
        if not os.path.exists(new_path):
            return new_path


# Note: The Windows "reserved characters" are, of course, allowed on
# Unix. They are forbidden here because they cause problems on Samba
# shares, which are sufficiently common as to cause frequent problems.
# https://msdn.microsoft.com/en-us/library/windows/desktop/aa365247.aspx
CHAR_REPLACE: Final[list[tuple[re.Pattern[str], str]]] = [
    (re.compile(r"[\\/]"), "_"),  # / and \ -- forbidden everywhere.
    (re.compile(r"^\."), "_"),  # Leading dot (hidden files on Unix).
    (re.compile(r"[\x00-\x1f]"), ""),  # Control characters.
    (re.compile(r'[<>:"\?\*\|]'), "_"),  # Windows "reserved characters".
    (re.compile(r"\.$"), "_"),  # Trailing dots.
    (re.compile(r"\s+$"), ""),  # Trailing whitespace.
]


def sanitize_path(path: str, replacements: Replacements | None = None) -> str:
    """Takes a path (as a Unicode string) and makes sure that it is
    legal. Returns a new path. Only works with fragments; won't work
    reliably on Windows when a path begins with a drive letter. Path
    separators (including altsep!) should already be cleaned from the
    path components. If replacements is specified, it is used *instead*
    of the default set of replacements; it must be a list of (compiled
    regex, replacement string) pairs.
    """
    replacements = replacements or CHAR_REPLACE

    comps: list[str] = components(path)
    if not comps:
        return ""
    i: int
    comp: str
    for i, comp in enumerate(comps):
        regex: re.Pattern[str]
        repl: str
        for regex, repl in replacements:
            comp = regex.sub(repl, comp)
        comps[i] = comp
    return os.path.join(*comps)


def truncate_str(s: str, length: int) -> str:
    """Truncate the string to the given byte length.

    If we end up truncating a unicode character in the middle (rendering it invalid),
    it is removed:

    >>> s = "🎹🎶"  # 8 bytes
    >>> truncate_str(s, 6)
    '🎹'
    """
    return os.fsencode(s)[:length].decode(sys.getfilesystemencoding(), "ignore")


def truncate_path(str_path: str) -> str:
    """Truncate each path part to a legal length preserving the extension."""
    max_length: int = get_max_filename_length()
    path: Path = Path(str_path)
    parent_parts: list[str] = [
        truncate_str(p, max_length) for p in path.parts[:-1]
    ]
    stem: str = truncate_str(path.stem, max_length - len(path.suffix))
    return f"{Path(*parent_parts, stem)}{path.suffix}"


def _legalize_stage(
    path: str, replacements: Replacements | None, extension: str
) -> tuple[str, bool]:
    """Perform a single round of path legalization steps
    1. sanitation/replacement
    2. appending the extension
    3. truncation.

    Return the path and whether truncation was required.
    """
    # Perform an initial sanitization including user replacements.
    path = sanitize_path(path, replacements)

    # Preserve extension.
    path += extension.lower()

    # Truncate too-long components.
    pre_truncate_path: str = path
    path = truncate_path(path)

    return path, path != pre_truncate_path


def legalize_path(
    path: str, replacements: Replacements | None, extension: str
) -> tuple[str, bool]:
    """Given a path-like Unicode string, produce a legal path. Return the path
    and a flag indicating whether some replacements had to be ignored (see
    below).

    This function uses `_legalize_stage` function to legalize the path, see its
    documentation for the details of what this involves. It is called up to
    three times in case truncation conflicts with replacements (as can happen
    when truncation creates whitespace at the end of the string, for example).

    The limited number of iterations avoids the possibility of an infinite loop
    of sanitation and truncation operations, which could be caused by
    replacement rules that make the string longer.

    The flag returned from this function indicates that the path has to be
    truncated twice (indicating that replacements made the string longer again
    after it was truncated); the application should probably log some sort of
    warning.
    """
    suffix: str = as_string(extension)

    first_stage: str
    first_stage, _ = os.path.splitext(
        _legalize_stage(path, replacements, suffix)[0]
    )

    # Re-sanitize following truncation (including user replacements).
    second_stage: str
    truncated: bool
    second_stage, truncated = _legalize_stage(first_stage, replacements, suffix)

    if not truncated:
        return second_stage, False

    # If the path was truncated, discard user replacements
    # and run through one last legalization stage.
    return _legalize_stage(first_stage, None, suffix)[0], True


def str2bool(value: str) -> bool:
    """Returns a boolean reflecting a human-entered string."""
    return value.lower() in ("yes", "1", "true", "t", "y")


def as_string(value: object) -> str:
    """Convert a value to a Unicode object for matching with a query.
    None becomes the empty string. Bytestrings are silently decoded.
    """
    if value is None:
        return ""
    elif isinstance(value, memoryview):  # TODO: check
        return bytes(value).decode("utf-8", "ignore")
    elif isinstance(value, bytes):
        return value.decode("utf-8", "ignore")
    else:
        return str(value)


def plurality(objs: Iterable[T]) -> tuple[T, int]:
    """Given a sequence of hashble objects, returns the object that
    is most common in the set and the its number of appearance. The
    sequence must contain at least one object.
    """
    c: Counter[T] = Counter(objs)
    if not c:
        raise ValueError("sequence must be non-empty")
    return c.most_common(1)[0]


# stdout and stderr as bytes
class CommandOutput(NamedTuple):
    stdout: bytes
    stderr: bytes


def command_output(
    cmd: list[str] | list[bytes], shell: bool = False
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
    devnull: int = subprocess.DEVNULL

    proc: subprocess.Popen[bytes] = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=devnull,
        close_fds=platform.system() != "Windows",
        shell=shell,
    )
    stdout: bytes
    stderr: bytes
    stdout, stderr = proc.communicate()
    if proc.returncode:
        raise subprocess.CalledProcessError(
            returncode=proc.returncode,
            cmd=" ".join(map(os.fsdecode, cmd)),
            output=stdout + stderr,
        )
    return CommandOutput(stdout, stderr)


@cache
def get_max_filename_length() -> int:
    """Attempt to determine the maximum filename length for the
    filesystem containing `path`. If the value is greater than `limit`,
    then `limit` is used instead (to prevent errors when a filesystem
    misreports its capacity). If it cannot be determined (e.g., on
    Windows), return `limit`.
    """
    length: int
    if length := config["max_filename_length"].get(int):
        return length

    limit: int = MAX_FILENAME_LENGTH
    if hasattr(os, "statvfs"):
        try:
            res: os.statvfs_result = os.statvfs(config["directory"].as_str())
        except OSError:
            return limit
        return min(res[9], limit)
    else:
        return limit


def open_anything() -> str:
    """Return the system command that dispatches execution to the correct
    program.
    """
    sys_name: str = platform.system()
    base_cmd: str
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


def interactive_open(targets: Sequence[str], command: str) -> None:
    """Open the files in `targets` by `exec`ing a new `command`, given
    as a Unicode string. (The new program takes over, and Python
    execution ends: this does not fork a subprocess.)

    Can raise `OSError`.
    """
    assert command

    # Split the command string into its arguments.
    args: list[str]
    try:
        args = shlex.split(command)
    except ValueError:  # Malformed shell tokens.
        args = [command]

    args.insert(0, args[0])  # for argv[0]

    args += targets

    os.execlp(*args)


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
    path_components: list[str] = path.split(os.sep)
    for index, item in enumerate(path_components):
        path_components[index] = unidecode(item).replace(os.sep, sep_replace)
        if os.altsep:
            path_components[index] = unidecode(item).replace(
                os.altsep, sep_replace
            )
    return os.sep.join(path_components)


def get_module_tempdir(module: str) -> Path:
    """Return the temporary directory for the given module.

    The directory is created within the `/tmp/beets/<module>` directory on
    Linux (or the equivalent temporary directory on other systems).

    Dots in the module name are replaced by underscores.
    """
    module = module.replace("beets.", "").replace(".", "_")
    return Path(tempfile.gettempdir()) / "beets" / module


def clean_module_tempdir(module: str) -> None:
    """Clean the temporary directory for the given module."""
    tempdir = get_module_tempdir(module)
    shutil.rmtree(tempdir, ignore_errors=True)
    with suppress(OSError):
        # remove parent (/tmp/beets) directory if it is empty
        tempdir.parent.rmdir()


def get_temp_filename(
    module: str,
    prefix: str = "",
    path: PathLike | None = None,
    suffix: str = "",
) -> bytes:
    """Return temporary filename for the given module and prefix.

    The filename starts with the given `prefix`.
    If 'suffix' is given, it is used a the file extension.
    If 'path' is given, we use the same suffix.
    """
    if not suffix and path:
        suffix = Path(os.fsdecode(path)).suffix

    tempdir = get_module_tempdir(module)
    tempdir.mkdir(parents=True, exist_ok=True)

    descriptor, filename = tempfile.mkstemp(
        dir=tempdir, prefix=prefix, suffix=suffix
    )
    os.close(descriptor)
    return bytestring_path(filename)
