# This file is part of beets.
# Copyright 2013, Jan-Erik Dahlin
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

"""If the title is empty, try to extract track and title from the
filename.
"""
from beets import plugins
import os
import re


PATTERNS = [
    # "01 - Track 01" and "01": do nothing
    r'^(\d+)\s*-\s*track\s*\d$',
    r'^\d+$',

    # Useful patterns.
    r'^(?P<track>\d+)\s*-(?P<artist>.+)-(?P<title>.+)-(?P<tag>.*)$',
    r'^(?P<track>\d+)\s(?P<artist>.+)-(?P<title>.+)-(?P<tag>.*)$',
    r'^(?P<track>\d+)\.\s*(?P<artist>.+)-(?P<title>.+)$',
    r'^(?P<track>\d+)\s*-\s*(?P<artist>.+)-(?P<title>.+)$',
    r'^(?P<track>\d+)\s*-(?P<artist>.+)-(?P<title>.+)$',
    r'^(?P<track>\d+)\s(?P<artist>.+)-(?P<title>.+)$',
    r'^(?P<track>\d+)\.\s*(?P<title>.+)$',
    r'^(?P<track>\d+)\s*-\s*(?P<title>.+)$',
    r'^(?P<track>\d+)\s(?P<title>.+)$',
]


def equal(seq):
    """Determine whether a sequence holds identical elements.
    """
    return len(set(seq)) <= 1


def equal_fields(matchdict, tag):
    """Do all items in `matchdict`, whose values are regular expression
    match objects, have the same value for `tag`? (If they do, the tag
    is probably not the title.)
    """
    return equal(m[tag] for m in matchdict.values())


def all_matches(names, pattern):
    """If all the filenames in the item/filename pair list match the
    pattern, return a dictionary mapping the items to dictionaries
    giving the value for each named subpattern in the match. Otherwise,
    return None.
    """
    matches = {}
    for item, name in names:
        m = re.match(pattern, name, re.IGNORECASE)
        if m:
            matches[item] = m.groupdict()
        else:
            return None
    return matches


def set_title_and_track(d, title_tag):
    """If the title is empty, set it to whatever we got from the
    filename. It is unlikely to be any worse than an empty title.
    """
    for item in d:
        if item.title == '':  # FIXME
            item.title = unicode(d[item][title_tag])
        if item.track == 0:
            item.track = int(d[item]['track'])


def apply_matches(d):
    """Given a mapping from items to field dicts, apply the fields to
    the objects.
    """
    keys = d.values()[0].keys()

    # Only proceed if the "tag" field is equal across all filenames.
    if 'tag' in keys and not equal_fields(d, 'tag'):
        return

    # Given both an "artist" and "title" field, assume that one is
    # *actually* the artist, which must be uniform, and use the other
    # for the title. This, of course, won't work for VA albums.
    if 'artist' in keys:
        if equal_fields(d, 'artist'):
            set_title_and_track(d, 'title')
            # FIXME set artist
        elif equal_fields(d, 'title'):
            set_title_and_track(d, 'artist')
        else:
            return

    set_title_and_track(d, 'title')


# Plugin structure and autotagging logic.

class FromFilenamePlugin(plugins.BeetsPlugin):
    pass

# Hooks into import process.

@FromFilenamePlugin.listen('import_task_start')
def filename_task(task, session):
    """Examine each item in the task to see if we can extract a title
    from the filename. Try to match all filenames to a number of
    regexps, starting with the most complex patterns and successively
    trying less complex patterns. As soon as all filenames match the
    same regex we can make an educated guess of which part of the
    regex that contains the title.
    """
    items = task.items if task.is_album else [task.item]

    # Look for suspicious (empty or meaningless) titles.
    names = []
    missing_titles = 0
    for item in items:
        name, _ = os.path.splitext(os.path.basename(item.path))
        name = name.lower().replace('_', ' ')
        names.append((item, name))
        if item.title == '':
            missing_titles += 1
        elif re.match("\d+?\s?-?\s*track\s*\d+", item.title, re.IGNORECASE):
            missing_titles += 1

    if missing_titles:
        for pattern in PATTERNS:
            d = all_matches(names, pattern)
            if d:
                apply_matches(d)
