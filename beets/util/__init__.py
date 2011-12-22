# This file is part of beets.
# Copyright 2011, Adrian Sampson.
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
import os
import sys
import re
import shutil
import fnmatch
from collections import defaultdict

MAX_FILENAME_LENGTH = 200

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
    for base in os.listdir(path):
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
        # yield from _sorted_walk(cur)
        for res in sorted_walk(cur, ignore):
            yield res

def mkdirall(path):
    """Make all the enclosing directories of path (like mkdir -p on the
    parent).
    """
    for ancestor in ancestry(path):
        if not os.path.isdir(syspath(ancestor)):
            os.mkdir(syspath(ancestor))

def prune_dirs(path, root, clutter=('.DS_Store', 'Thumbs.db')):
    """If path is an empty directory, then remove it. Recursively
    remove path's ancestry up to root (which is never removed) where
    there are empty directories. If path is not contained in root, then
    nothing is removed. Filenames in clutter are ignored when
    determining emptiness.
    """
    path = normpath(path)
    root = normpath(root)

    ancestors = ancestry(path)
    if root in ancestors:
        # Only remove directories below the root.
        ancestors = ancestors[ancestors.index(root)+1:]

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
        else: # root
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
        # Try to decode with default encodings, but fall back to UTF8.
        encoding = sys.getfilesystemencoding() or sys.getdefaultencoding()
        try:
            path = path.decode(encoding, 'replace')
        except UnicodeError:
            path = path.decode('utf8', 'replace')

    # Add the magic prefix if it isn't already there
    if not path.startswith(u'\\\\?\\'):
        path = u'\\\\?\\' + path

    return path

def samefile(p1, p2):
    """Safer equality for paths."""
    return shutil._samefile(syspath(p1), syspath(p2))

def soft_remove(path):
    """Remove the file if it exists."""
    path = syspath(path)
    if os.path.exists(path):
        os.remove(path)

def _assert_not_exists(path, pathmod=None):
    """Raises an OSError if the path exists."""
    pathmod = pathmod or os.path
    if pathmod.exists(path):
        raise OSError('file exists: %s' % path)

def copy(path, dest, replace=False, pathmod=None):
    """Copy a plain file. Permissions are not copied. If dest already
    exists, raises an OSError unless replace is True. Has no effect if
    path is the same as dest. Paths are translated to system paths
    before the syscall.
    """
    if samefile(path, dest):
        return
    path = syspath(path)
    dest = syspath(dest)
    _assert_not_exists(dest, pathmod)
    return shutil.copyfile(path, dest)

def move(path, dest, replace=False, pathmod=None):
    """Rename a file. dest may not be a directory. If dest already
    exists, raises an OSError unless replace is True. Hos no effect if
    path is the same as dest. Paths are translated to system paths.
    """
    if samefile(path, dest):
        return
    path = syspath(path)
    dest = syspath(dest)
    _assert_not_exists(dest, pathmod)
    return shutil.move(path, dest)

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

# Note: POSIX actually supports \ and : -- I just think they're
# a pain. And ? has caused problems for some.
CHAR_REPLACE = [
    (re.compile(r'[\\/\?"]|^\.'), '_'),
    (re.compile(r':'), '-'),
]
CHAR_REPLACE_WINDOWS = [
    (re.compile(r'["\*<>\|]|^\.|\.$|\s+$'), '_'),
]
def sanitize_path(path, pathmod=None, replacements=None):
    """Takes a path and makes sure that it is legal. Returns a new path.
    Only works with fragments; won't work reliably on Windows when a
    path begins with a drive letter. Path separators (including altsep!)
    should already be cleaned from the path components. If replacements
    is specified, it is used *instead* of the default set of
    replacements for the platform; it must be a list of (compiled regex,
    replacement string) pairs.
    """
    pathmod = pathmod or os.path
    windows = pathmod.__name__ == 'ntpath'

    # Choose the appropriate replacements.
    if not replacements:
        replacements = list(CHAR_REPLACE)
        if windows:
            replacements += CHAR_REPLACE_WINDOWS
    
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
        value = u'%02i' % value
    elif key == 'year':
        value = u'%04i' % value
    elif key in ('month', 'day'):
        value = u'%02i' % value
    elif key == 'bitrate':
        # Bitrate gets formatted as kbps.
        value = u'%ikbps' % (value / 1000)
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
