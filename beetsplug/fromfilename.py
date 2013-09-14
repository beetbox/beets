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


def equal(seq):
    """Determine whether a sequence holds identical elements.
    """
    return len(set(seq)) <= 1


def equal_fields(matchdict, tag):
    """Do all items in `matchdict`, whose values are regular expression
    match objects, have the same value for `tag`? (If they do, the tag
    is probably not the title.)
    """
    return equal(m.group(tag) for m in matchdict.values())


def all_matches(names, pattern):
    """If all the filenames in the item/filename pair list match the
    pattern, return a dictionary mapping the items to their match
    objects. Otherwise, return None.
    """
    matches = {}
    for item, name in names:
        m = re.match(pattern, name, re.IGNORECASE)
        if m:
            matches[item] = m
        else:
            return None
    return matches


def set_title_and_track(d, title_tag):
    """If the title is empty, set it to whatever we got from the
    filename. It is unlikely to be any worse than an empty title.
    """
    for item in d:
        if item.title == '':  # FIXME
            item.title = unicode(d[item].group(title_tag))
        if item.track == 0:
            item.track = int(d[item].group('track'))


def handle2fields(d):
    """We only have one value beside the track number.
    """
    set_title_and_track(d, 'title')


def handle3fields(d):
    """Some files are named <title>-<artist> and some  are named
    <artist>-<title>. If all item of the dict has the same value in
    either artist or title we assume the other field is the title.

    At present we don't know what to do about VA albums. Could set
    both artist and track, but which one is which?
    """
    if equal_fields(d, 'artist'):
        set_title_and_track(d, 'title')
    elif equal_fields(d, 'title'):
        set_title_and_track(d, 'artist')


def handle4fields(d):
    """Filenames matching the four field regex usually have a group
    tag at the end. Ignore it.
    """
    if equal_fields(d, 'tag'):
        handle3fields(d)


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
        #filter out stupid case: 01 - track 01
        d = all_matches(names, '^(\d+)\s*-\s*track\s*\d$')
        if d:
            return
        #filter out stupid case: 01
        d = all_matches(names, '^\d+$')
        if d:
            return

        d = all_matches(names, '^(?P<track>\d+)\s*-(?P<artist>.+)-(?P<title>.+)-(?P<tag>.*)$')
        if d:
            return handle4fields(d)

        d = all_matches(names, '^(?P<track>\d+)\s(?P<artist>.+)-(?P<title>.+)-(?P<tag>.*)$')
        if d:
            return handle4fields(d)

        d = all_matches(names, '^(?P<track>\d+)\.\s*(?P<artist>.+)-(?P<title>.+)$')
        if d:
            return handle3fields(d)

        d = all_matches(names, '^(?P<track>\d+)\s*-\s*(?P<artist>.+)-(?P<title>.+)$')
        if d:
            return handle3fields(d)

        d = all_matches(names, '^(?P<track>\d+)\s*-(?P<artist>.+)-(?P<title>.+)$')
        if d:
            return handle3fields(d)

        d = all_matches(names, '^(?P<track>\d+)\s(?P<artist>.+)-(?P<title>.+)$')
        if d:
            return handle3fields(d)

        d = all_matches(names, '^(?P<track>\d+)\.\s*(?P<title>.+)$')
        if d:
            return handle2fields(d)

        d = all_matches(names, '^(?P<track>\d+)\s*-\s*(?P<title>.+)$')
        if d:
            return handle2fields(d)

        d = all_matches(names, '^(?P<track>\d+)\s(?P<title>.+)$')
        if d:
            return handle2fields(d)

