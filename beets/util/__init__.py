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

def sorted_walk(path):
    """Like os.walk, but yields things in sorted, breadth-first
    order.
    """
    # Make sure the path isn't a Unicode string.
    path = bytestring_path(path)

    # Get all the directories and files at this level.
    dirs = []
    files = []
    for base in os.listdir(path):
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
        for res in sorted_walk(cur):
            yield res

def mkdirall(path):
    """Make all the enclosing directories of path (like mkdir -p on the
    parent).
    """
    for ancestor in ancestry(path):
        if not os.path.isdir(syspath(ancestor)):
            os.mkdir(syspath(ancestor))

def prune_dirs(path, root):
    """If path is an empty directory, then remove it. Recursively
    remove path's ancestry up to root (which is never removed) where
    there are empty directories. If path is not contained in root, then
    nothing is removed.
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
            try:
                os.rmdir(syspath(directory))
            except OSError:
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
    except UnicodeError:
        return path.encode('utf8')

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

def soft_remove(path):
    """Remove the file if it exists."""
    path = syspath(path)
    if os.path.exists(path):
        os.remove(path)

# Note: POSIX actually supports \ and : -- I just think they're
# a pain. And ? has caused problems for some.
CHAR_REPLACE = [
    (re.compile(r'[\\/\?]|^\.'), '_'),
    (re.compile(r':'), '-'),
]
CHAR_REPLACE_WINDOWS = re.compile('["\*<>\|]|^\.|\.$| +$'), '_'
def sanitize_path(path, pathmod=None):
    """Takes a path and makes sure that it is legal. Returns a new path.
    Only works with fragments; won't work reliably on Windows when a
    path begins with a drive letter. Path separators (including altsep!)
    should already be cleaned from the path components.
    """
    pathmod = pathmod or os.path
    windows = pathmod.__name__ == 'ntpath'
    
    comps = components(path, pathmod)
    if not comps:
        return ''
    for i, comp in enumerate(comps):
        # Replace special characters.
        for regex, repl in CHAR_REPLACE:
            comp = regex.sub(repl, comp)
        if windows:
            regex, repl = CHAR_REPLACE_WINDOWS
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
        # pad with zeros
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
