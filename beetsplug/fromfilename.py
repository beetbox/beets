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

def allSame(matchdict, tag):
    """Do all items in matchdict have the same value in tag? If they
    do it is probably not the title.
    """
    equalto = matchdict.itervalues().next().group(tag)
    for match in matchdict.viewvalues():
        if match.group(tag) != equalto:
            return False
    return True


def allMatches(names, pattern):
    """Do all filenames match the regex? If they do 
    """
    matches = dict()
    for item, name in names:
        m = re.match(pattern, name, re.IGNORECASE);
        if m:
            matches[item] = m
        else:
            return None
    return matches


def setNames(d, tag):
    """If the title is empty, set it to whatever we got from the
    filename. It is unlikely to be any worse than an empty title.
    """
    for item in d:
        if item.title == '':
            item.title = unicode(d[item].group(tag))
        if item.track == 0:
            item.track = int(d[item].group('track'))


def handle2fields(d):
    """We only have one value beside the track number.
    """
    setNames(d, 'title')


def handle3fields(d):
    """Some files are named <title>-<artist> and some  are named
    <artist>-<title>. If all item of the dict has the same value in
    either artist or title we assume the other field is the title.

    At present we don't know what to do about VA albums. Could set
    both artist and track, but which one is which?
    """
    if allSame(d, 'artist'):
        setNames(d, 'title')
    elif allSame(d, 'title'):
        setNames(d, 'artist')

    
def handle4fields(d):
    """Filenames matching the four field regex usually have a group
    tag at the end. Ignore it.
    """
    if allSame(d, 'tag'):
        handle3fields(d)


# Plugin structure and autotagging logic.


class FromFilenamePlugin(plugins.BeetsPlugin):
    def foo(self):
        return self

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
    names = []
    for item in items:
        _, tail = os.path.split(item.path)
        foundOne = True
        if tail[-4:].lower() == ".mp3":
            names.append((item, tail[:-4].lower().replace('_', ' ')))
            if item.title == '':
                foundOne = True
            elif re.match("\d+?\s?-?\s*track\s*\d+", item.title, re.IGNORECASE):
                foundOne = True
    if foundOne:
        #filter out stupid case: 01 - track 01 
        d = allMatches(names, '^(\d+)\s*-\s*track\s*\d$')
        if d:
            return
        #filter out stupid case: 01 
        d = allMatches(names, '^\d+$')
        if d:
            return

        d = allMatches(names, '^(?P<track>\d+)\s*-(?P<artist>.+)-(?P<title>.+)-(?P<tag>.*)$')
        if d:
            return handle4fields(d)

        d = allMatches(names, '^(?P<track>\d+)\s(?P<artist>.+)-(?P<title>.+)-(?P<tag>.*)$')
        if d:
            return handle4fields(d)

        d = allMatches(names, '^(?P<track>\d+)\.\s*(?P<artist>.+)-(?P<title>.+)$')
        if d:
            return handle3fields(d)

        d = allMatches(names, '^(?P<track>\d+)\s*-\s*(?P<artist>.+)-(?P<title>.+)$')
        if d:
            return handle3fields(d)

        d = allMatches(names, '^(?P<track>\d+)\s*-(?P<artist>.+)-(?P<title>.+)$')
        if d:
            return handle3fields(d)

        d = allMatches(names, '^(?P<track>\d+)\s(?P<artist>.+)-(?P<title>.+)$')
        if d:
            return handle3fields(d)

        d = allMatches(names, '^(?P<track>\d+)\.\s*(?P<title>.+)$')
        if d:
            return handle2fields(d)

        d = allMatches(names, '^(?P<track>\d+)\s*-\s*(?P<title>.+)$')
        if d:
            return handle2fields(d)

        d = allMatches(names, '^(?P<track>\d+)\s(?P<title>.+)$')
        if d:
            return handle2fields(d)

