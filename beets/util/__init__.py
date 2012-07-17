# This file is part of beets.
# Copyright 2012, Adrian Sampson.
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
from __future__ import division

import os
import sys
import re
import shutil
import fnmatch
from collections import defaultdict
import traceback

MAX_FILENAME_LENGTH = 200

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
    error_kind = 'Error'  # Human-readable description of error type.

    def __init__(self, reason, verb, tb=None):
        self.reason = reason
        self.verb = verb
        self.tb = tb
        super(HumanReadableException, self).__init__(self.get_message())

    def _gerund(self):
        """Generate a (likely) gerund form of the English verb.
        """
        if ' ' in self.verb:
            return self.verb
        gerund = self.verb[:-1] if self.verb.endswith('e') else self.verb
        gerund += 'ing'
        return gerund
    
    def _reasonstr(self):
        """Get the reason as a string."""
        if isinstance(self.reason, basestring):
            return self.reason
        elif hasattr(self.reason, 'strerror'):  # i.e., EnvironmentError
            return self.reason.strerror
        else:
            return u'"{0}"'.format(self.reason)

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
        logger.error(u'{0}: {1}'.format(self.error_kind, self.args[0]))

class FilesystemError(HumanReadableException):
    """An error that occurred while performing a filesystem manipulation
    via a function in this module. The `paths` field is a sequence of
    pathnames involved in the operation.
    """
    def __init__(self, reason, verb, paths, tb=None):
        self.paths = paths
        super(FilesystemError, self).__init__(reason, verb, tb)

    def get_message(self):
        # Use a nicer English phrasing for some specific verbs.
        if self.verb in ('move', 'copy', 'rename'):
            clause = 'while {0} {1} to {2}'.format(
                self._gerund(), repr(self.paths[0]), repr(self.paths[1])
            )
        elif self.verb in ('delete',):
            clause = 'while {0} {1}'.format(
                self._gerund(), repr(self.paths[0])
            )
        else:
            clause = 'during {0} of paths {1}'.format(
                self.verb, u', '.join(repr(p) for p in self.paths)
            )

        return u'{0} {1}'.format(self._reasonstr(), clause)

def normpath(path):
    """Provide the canonical form of the path suitable for storing in
    the database.
    """
    return os.path.normpath(os.path.abspath(os.path.expanduser(path)))

def ancestry(path, pathmod=None):
    """Return a list consisting of path's parent directory, its
    grandparent, and so on. For instance:
       >>> ancestry('/a/b/c')
       ['/', '/a', '/a/b']
    """
    pathmod = pathmod or os.path
    out = []
    last_path = None
    while path:
        path = pathmod.dirname(path)

        if path == last_path:
            break
        last_path = path

        if path: # don't yield ''
            out.insert(0, path)
    return out

def sorted_walk(path, ignore=()):
    """Like ``os.walk``, but yields things in sorted, breadth-first
    order.  Directory and file names matching any glob pattern in
    ``ignore`` are skipped.
    """
    # Make sure the path isn't a Unicode string.
    path = bytestring_path(path)

    # Get all the directories and files at this level.
    dirs = []
    files = []
    for base in os.listdir(syspath(path)):
        base = bytestring_path(base)

        # Skip ignored filenames.
        skip = False
        for pat in ignore:
            if fnmatch.fnmatch(base, pat):
                skip = True
                break
        if skip:
            continue

        # Add to output as either a file or a directory.
        cur = os.path.join(path, base)
        if os.path.isdir(syspath(cur)):
            dirs.append(base)
        else:
            files.append(base)

    # Sort lists and yield the current level.
    dirs.sort()
    files.sort()
    yield (path, dirs, files)

    # Recurse into directories.
    for base in dirs:
        cur = os.path.join(path, base)
        # yield from sorted_walk(...)
        for res in sorted_walk(cur, ignore):
            yield res

def mkdirall(path):
    """Make all the enclosing directories of path (like mkdir -p on the
    parent).
    """
    for ancestor in ancestry(path):
        if not os.path.isdir(syspath(ancestor)):
            os.mkdir(syspath(ancestor))

def prune_dirs(path, root=None, clutter=('.DS_Store', 'Thumbs.db')):
    """If path is an empty directory, then remove it. Recursively remove
    path's ancestry up to root (which is never removed) where there are
    empty directories. If path is not contained in root, then nothing is
    removed. Filenames in clutter are ignored when determining
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
        ancestors = ancestors[ancestors.index(root)+1:]
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

        if all(fn in clutter for fn in os.listdir(directory)):
            # Directory contains only clutter (or nothing).
            try:
                shutil.rmtree(directory)
            except OSError:
                break
        else:
            break

def components(path, pathmod=None):
    """Return a list of the path components in path. For instance:
       >>> components('/a/b/c')
       ['a', 'b', 'c']
    """
    pathmod = pathmod or os.path
    comps = []
    ances = ancestry(path, pathmod)
    for anc in ances:
        comp = pathmod.basename(anc)
        if comp:
            comps.append(comp)
        else:  # root
            comps.append(anc)

    last = pathmod.basename(path)
    if last:
        comps.append(last)

    return comps

def bytestring_path(path):
    """Given a path, which is either a str or a unicode, returns a str
    path (ensuring that we never deal with Unicode pathnames).
    """
    # Pass through bytestrings.
    if isinstance(path, str):
        return path

    # Try to encode with default encodings, but fall back to UTF8.
    encoding = sys.getfilesystemencoding() or sys.getdefaultencoding()
    if encoding == 'mbcs':
        # On Windows, a broken encoding known to Python as "MBCS" is
        # used for the filesystem. However, we only use the Unicode API
        # for Windows paths, so the encoding is actually immaterial so
        # we can avoid dealing with this nastiness. We arbitrarily
        # choose UTF-8.
        encoding = 'utf8'
    try:
        return path.encode(encoding)
    except (UnicodeError, LookupError):
        return path.encode('utf8')

def displayable_path(path):
    """Attempts to decode a bytestring path to a unicode object for the
    purpose of displaying it to the user.
    """
    if isinstance(path, unicode):
        return path
    elif not isinstance(path, str):
        # A non-string object: just get its unicode representation.
        return unicode(path)

    encoding = sys.getfilesystemencoding() or sys.getdefaultencoding()
    try:
        return path.decode(encoding, 'ignore')
    except (UnicodeError, LookupError):
        return path.decode('utf8', 'ignore')

def syspath(path, pathmod=None):
    """Convert a path for use by the operating system. In particular,
    paths on Windows must receive a magic prefix and must be converted
    to unicode before they are sent to the OS.
    """
    pathmod = pathmod or os.path
    windows = pathmod.__name__ == 'ntpath'

    # Don't do anything if we're not on windows
    if not windows:
        return path

    if not isinstance(path, unicode):
        # Beets currently represents Windows paths internally with UTF-8
        # arbitrarily. But earlier versions used MBCS because it is
        # reported as the FS encoding by Windows. Try both.
        try:
            path = path.decode('utf8')
        except UnicodeError:
            # The encoding should always be MBCS, Windows' broken
            # Unicode representation.
            encoding = sys.getfilesystemencoding() or sys.getdefaultencoding()
            path = path.decode(encoding, 'replace')

    # Add the magic prefix if it isn't already there
    if not path.startswith(u'\\\\?\\'):
        path = u'\\\\?\\' + path

    return path

def samefile(p1, p2):
    """Safer equality for paths."""
    return shutil._samefile(syspath(p1), syspath(p2))

def remove(path, soft=True):
    """Remove the file. If `soft`, then no error will be raised if the
    file does not exist.
    """
    path = syspath(path)
    if soft and not os.path.exists(path):
        return
    try:
        os.remove(path)
    except (OSError, IOError) as exc:
        raise FilesystemError(exc, 'delete', (path,), traceback.format_exc())

def copy(path, dest, replace=False, pathmod=os.path):
    """Copy a plain file. Permissions are not copied. If `dest` already
    exists, raises a FilesystemError unless `replace` is True. Has no
    effect if `path` is the same as `dest`. Paths are translated to
    system paths before the syscall.
    """
    if samefile(path, dest):
        return
    path = syspath(path)
    dest = syspath(dest)
    if not replace and pathmod.exists(dest):
        raise FilesystemError('file exists', 'copy', (path, dest))
    try:
        shutil.copyfile(path, dest)
    except (OSError, IOError) as exc:
        raise FilesystemError(exc, 'copy', (path, dest),
                              traceback.format_exc())

def move(path, dest, replace=False, pathmod=os.path):
    """Rename a file. `dest` may not be a directory. If `dest` already
    exists, raises an OSError unless `replace` is True. Has no effect if
    `path` is the same as `dest`. If the paths are on different
    filesystems (or the rename otherwise fails), a copy is attempted
    instead, in which case metadata will *not* be preserved. Paths are
    translated to system paths.
    """
    if samefile(path, dest):
        return
    path = syspath(path)
    dest = syspath(dest)
    if pathmod.exists(dest):
        raise FilesystemError('file exists', 'rename', (path, dest),
                              traceback.format_exc())

    # First, try renaming the file.
    try:
        os.rename(path, dest)
    except OSError:
        # Otherwise, copy and delete the original.
        try:
            shutil.copyfile(path, dest)
            os.remove(path)
        except (OSError, IOError) as exc:
            raise FilesystemError(exc, 'move', (path, dest),
                                  traceback.format_exc())

def unique_path(path):
    """Returns a version of ``path`` that does not exist on the
    filesystem. Specifically, if ``path` itself already exists, then
    something unique is appended to the path.
    """
    if not os.path.exists(syspath(path)):
        return path

    base, ext = os.path.splitext(path)
    match = re.search(r'\.(\d)+$', base)
    if match:
        num = int(match.group(1))
        base = base[:match.start()]
    else:
        num = 0
    while True:
        num += 1
        new_path = '%s.%i%s' % (base, num, ext)
        if not os.path.exists(new_path):
            return new_path

# Note: The Windows "reserved characters" are, of course, allowed on
# Unix. They are forbidden here because they cause problems on Samba
# shares, which are sufficiently common as to cause frequent problems.
# http://msdn.microsoft.com/en-us/library/windows/desktop/aa365247.aspx
CHAR_REPLACE = [
    (re.compile(ur'[\\/]'), u'_'),  # / and \ -- forbidden everywhere.
    (re.compile(ur'^\.'), u'_'),  # Leading dot (hidden files on Unix).
    (re.compile(ur'[\x00-\x1f]'), u''),  # Control characters.
    (re.compile(ur'[<>:"\?\*\|]'), u'_'),  # Windows "reserved characters".
    (re.compile(ur'\.$'), u'_'),  # Trailing dots.
    (re.compile(ur'\s+$'), u''),  # Trailing whitespace.
]
def sanitize_path(path, pathmod=None, replacements=None):
    """Takes a path (as a Unicode string) and makes sure that it is
    legal. Returns a new path. Only works with fragments; won't work
    reliably on Windows when a path begins with a drive letter. Path
    separators (including altsep!) should already be cleaned from the
    path components. If replacements is specified, it is used *instead*
    of the default set of replacements for the platform; it must be a
    list of (compiled regex, replacement string) pairs.
    """
    pathmod = pathmod or os.path

    # Choose the appropriate replacements.
    if not replacements:
        replacements = list(CHAR_REPLACE)

    comps = components(path, pathmod)
    if not comps:
        return ''
    for i, comp in enumerate(comps):
        # Replace special characters.
        for regex, repl in replacements:
            comp = regex.sub(repl, comp)

        # Truncate each component.
        comp = comp[:MAX_FILENAME_LENGTH]

        comps[i] = comp
    return pathmod.join(*comps)

def sanitize_for_path(value, pathmod, key=None):
    """Sanitize the value for inclusion in a path: replace separators
    with _, etc. Doesn't guarantee that the whole path will be valid;
    you should still call sanitize_path on the complete path.
    """
    if isinstance(value, basestring):
        for sep in (pathmod.sep, pathmod.altsep):
            if sep:
                value = value.replace(sep, u'_')
    elif key in ('track', 'tracktotal', 'disc', 'disctotal'):
        # Pad indices with zeros.
        value = u'%02i' % (value or 0)
    elif key == 'year':
        value = u'%04i' % (value or 0)
    elif key in ('month', 'day'):
        value = u'%02i' % (value or 0)
    elif key == 'bitrate':
        # Bitrate gets formatted as kbps.
        value = u'%ikbps' % ((value or 0) // 1000)
    elif key == 'samplerate':
        # Sample rate formatted as kHz.
        value = u'%ikHz' % ((value or 0) // 1000)
    else:
        value = unicode(value)
    return value

def str2bool(value):
    """Returns a boolean reflecting a human-entered string."""
    if value.lower() in ('yes', '1', 'true', 't', 'y'):
        return True
    else:
        return False

def levenshtein(s1, s2):
    """A nice DP edit distance implementation from Wikibooks:
    http://en.wikibooks.org/wiki/Algorithm_implementation/Strings/
    Levenshtein_distance#Python
    """
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if not s1:
        return len(s2)

    previous_row = xrange(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]

def plurality(objs):
    """Given a sequence of comparable objects, returns the object that
    is most common in the set and the frequency of that object. The
    sequence must contain at least one object.
    """
    # Calculate frequencies.
    freqs = defaultdict(int)
    for obj in objs:
        freqs[obj] += 1

    if not freqs:
        raise ValueError('sequence must be non-empty')

    # Find object with maximum frequency.
    max_freq = 0
    res = None
    for obj, freq in freqs.items():
        if freq > max_freq:
            max_freq = freq
            res = obj

    return res, max_freq
