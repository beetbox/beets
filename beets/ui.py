# This file is part of beets.
# Copyright 2010, Adrian Sampson.
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

import os
import logging

from beets import autotag
from beets import library
from beets.mediafile import FileTypeError
from beets.player import bpd

# Utilities.

def _print(txt):
    """Print the text encoded using UTF-8."""
    print txt.encode('utf-8')

def _input_options(prompt, options, default=None,
                   fallback_prompt=None, numrange=None):
    """Prompts a user for input. The input must be one of the single
    letters in options, a list of single-letter strings, or an integer
    in numrange, which is a (low, high) tuple. If nothing is entered,
    assume the input is default (if provided). Returns the value
    entered, a single-letter string or an integer. If an incorrect
    input occurs, fallback_prompt is used (by default identical to
    the initial prompt).
    """
    fallback_prompt = fallback_prompt or prompt
    
    resp = raw_input(prompt + ' ')
    while True:
        resp = resp.strip().lower()
        
        # Try default option.
        if default is not None and not resp:
            resp = default
        
        # Try an integer input if available.
        if numrange is not None:
            try:
                resp = int(resp)
            except ValueError:
                pass
            else:
                low, high = numrange
                if low <= resp <= high:
                    return resp
                else:
                    resp = None
        
        # Try a normal letter input.
        if resp:
            resp = resp[0]
            if resp in options:
                return resp
        
        # Prompt for new input.
        resp = raw_input(fallback_prompt + ' ')

def _input_yn(prompt, require=False):
    """Prompts user for a "yes" or "no" response where an empty response
    is treated as "yes". Keeps prompting until acceptable input is
    given; returns a boolean. If require is True, then an empty response
    is not accepted.
    """
    sel = _input_options(
        prompt,
        ('y', 'n'),
        None if require else 'y',
        "Type 'y' or 'n':"
    )
    return (sel == 'y')

# Autotagging interface.

def show_change(cur_artist, cur_album, items, info, dist):
    """Print out a representation of the changes that will be made if
    tags are changed from (cur_artist, cur_album, items) to info with
    distance dist.
    """
    if cur_artist != info['artist'] or cur_album != info['album']:
        print "Correcting tags from:"
        print '     %s - %s' % (cur_artist, cur_album)
        print "To:"
        print '     %s - %s' % (info['artist'], info['album'])
    else:
        print "Tagging: %s - %s" % (info['artist'], info['album'])
    print '(Distance: %f)' % dist
    for item, track_data in zip(items, info['tracks']):
        if item.title != track_data['title']:
            print " * %s -> %s" % (item.title, track_data['title'])

CHOICE_SKIP = 'CHOICE_SKIP'
CHOICE_ASIS = 'CHOICE_ASIS'
CHOICE_MANUAL = 'CHOICE_MANUAL'
def choose_candidate(cur_artist, cur_album, candidates, rec):
    """Given current metadata and a sorted list of
    (distance, candidate) pairs, ask the user for a selection
    of which candidate to use. Returns the selected candidate.
    If user chooses to skip, use as-is, or search manually, returns
    CHOICE_SKIP, CHOICE_ASIS, or CHOICE_MANUAL.
    """
    # Is the change good enough?
    top_dist, _, _ = candidates[0]
    bypass_candidates = False
    if rec != autotag.RECOMMEND_NONE:
        dist, items, info = candidates[0]
        bypass_candidates = True
        
    while True:
        # Display and choose from candidates.
        if not bypass_candidates:
            print 'Finding tags for "%s - %s".' % (cur_artist, cur_album)
            print 'Candidates:'
            for i, (dist, items, info) in enumerate(candidates):
                print '%i. %s - %s (%f)' % (i+1, info['artist'],
                                            info['album'], dist)
                                            
            # Ask the user for a choice.
            sel = _input_options(
                '# selection (default 1), Skip, Use as-is, or '
                'Enter manual search?',
                ('s', 'u', 'e'), '1',
                'Enter a numerical selection, S, U, or E:',
                (1, len(candidates))
            )
            if sel == 's':
                return CHOICE_SKIP
            elif sel == 'u':
                return CHOICE_ASIS
            elif sel == 'e':
                return CHOICE_MANUAL
            else: # Numerical selection.
                dist, items, info = candidates[sel-1]
        bypass_candidates = False
    
        # Show what we're about to do.
        show_change(cur_artist, cur_album, items, info, dist)
    
        # Exact match => tag automatically.
        if rec == autotag.RECOMMEND_STRONG:
            return info
        
        # Ask for confirmation.
        sel = _input_options(
            '[A]pply, More candidates, Skip, Use as-is, or '
            'Enter manual search? ',
            ('a', 'm', 's', 'u', 'e'), 'a',
            'Enter A, M, S, U, or E:'
        )
        if sel == 'a':
            return info
        elif sel == 'm':
            pass
        elif sel == 's':
            return CHOICE_SKIP
        elif sel == 'u':
            return CHOICE_ASIS
        elif sel == 'e':
            return CHOICE_MANUAL

def manual_search():
    """Input an artist and album for manual search."""
    artist = raw_input('Artist: ')
    album = raw_input('Album: ')
    return artist.strip(), album.strip()

def tag_album(items, lib, copy=True, write=True):
    """Import items into lib, tagging them as an album. If copy, then
    items are copied into the destination directory. If write, then
    new metadata is written back to the files' tags.
    """
    # Try to get candidate metadata.
    search_artist, search_album = None, None
    chose_asis = False
    while True:
        # Infer tags.
        try:
            cur_artist, cur_album, candidates, rec = \
                    autotag.tag_album(items, search_artist, search_album)
        except autotag.AutotagError:
            print "No match found for:", os.path.dirname(items[0].path)
            sel = _input_options(
                "[U]se as-is, Skip, or Enter manual search?",
                ('u', 's', 'e'), 'u',
                'Enter U, S, or E:'
            )
            if sel == 'u':
                chose_asis = True
            elif sel == 'e':
                search_artist, search_album = manual_search()
            elif sel == 's':
                return
    
        # Choose which tags to use.
        if chose_asis:
            info = CHOICE_ASIS
        else:
            info = choose_candidate(cur_artist, cur_album, candidates, rec)
        if info is CHOICE_SKIP:
            # Skip entirely.
            return
        elif info is CHOICE_MANUAL:
            # Try again with manual search terms.
            search_artist, search_album = manual_search()
        else:
            # Got a candidate. Continue tagging.
            break
    
    # Ensure that we don't have the album already.
    if not chose_asis:
        if info is CHOICE_ASIS:
            artist = cur_artist
            album = cur_album
        else:
            artist = info['artist']
            album = info['album']
        q = library.AndQuery((library.MatchQuery('artist', artist),
                              library.MatchQuery('album',  album)))
        count, _ = q.count(lib)
        if count >= 1:
            print "This album (%s - %s) is already in the library!" % \
                  (artist, album)
            return
    
    # Change metadata and add to library.
    if info is not CHOICE_ASIS:
        autotag.apply_metadata(items, info)
    for item in items:
        if copy:
            item.move(lib, True)
        lib.add(item)
        if write and info is not CHOICE_ASIS:
            item.write()


# Top-level commands.

def import_files(lib, paths, copy=True, write=True, autot=True):
    """Import the files in the given list of paths, tagging each leaf
    directory as an album. If copy, then the files are copied into
    the library folder. If write, then new metadata is written to the
    files themselves. If not autot, then just import the files
    without attempting to tag.
    """
    first = True
    for path in paths:
        for album in autotag.albums_in_dir(os.path.expanduser(path)):
            if not first:
                print
            first = False

            if autot:
                # Infer tags.
                tag_album(album, lib, copy, write)
            else:
                # Leave tags as-is.
                for item in album:
                    if copy:
                        item.move(lib, True)
                    lib.add(item)
            lib.save()

def list_items(lib, query, album):
    """Print out items in lib matching query. If album, then search for
    albums instead of single items.
    """
    if album:
        for artist, album in lib.albums(query=query):
            _print(artist + ' - ' + album)
    else:
        for item in lib.items(query=query):
            _print(item.artist + ' - ' + item.album + ' - ' + item.title)

def remove_items(lib, query, album, delete=False):
    """Remove items matching query from lib. If album, then match and
    remove whole albums. If delete, also remove files from disk.
    """
    # Get the matching items.
    if album:
        items = []
        for artist, album in lib.albums(query=query):
            items += list(lib.items(artist=artist, album=album))
    else:
        items = list(lib.items(query=query))

    # Show all the items.
    for item in items:
        _print(item.artist + ' - ' + item.album + ' - ' + item.title)

    # Confirm with user.
    print
    if delete:
        prompt = 'Really DELETE %i files (y/n)? ' % len(items)
    else:
        prompt = 'Really remove %i items from the library (y/n)? ' % \
                 len(items)
    if not _input_yn(prompt, True):
        return

    # Remove and delete.
    for item in items:
        lib.remove(item)
        if delete:
            os.unlink(item.path)
    lib.save()

def device_add(lib, query, name):
    """Add items matching query from lib to a device with the given
    name.
    """
    items = self.lib.items(query=query)

    from beets import device
    pod = device.PodLibrary.by_name(name)
    for item in items:
        pod.add(item)
    pod.save()

def start_bpd(lib, host, port, password, debug):
    """Starts a BPD server."""
    log = logging.getLogger('beets.player.bpd')
    if debug:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.WARNING)
    try:
        bpd.Server(lib, host, port, password).run()    
    except bpd.NoGstreamerError:
        print 'Gstreamer Python bindings not found.'
        print 'Install "python-gst0.10", "py26-gst-python", or similar ' \
              'package to use BPD.'
        return
