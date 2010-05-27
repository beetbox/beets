# This file is part of beets.
# Copyright 2009, Adrian Sampson.
# 
# Beets is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Beets is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with beets.  If not, see <http://www.gnu.org/licenses/>.

import os

from beets import autotag
from beets import library
from beets.mediafile import FileTypeError

# Utilities.

def _print(txt):
    """Print the text encoded using UTF-8."""
    print txt.encode('utf-8')

def _input_yn(prompt, require=False):
    """Prompts user for a "yes" or "no" response where an empty response
    is treated as "yes". Keeps prompting until acceptable input is
    given; returns a boolean. If require is True, then an empty response
    is not accepted.
    """
    resp = raw_input(prompt).strip()
    while True:
        if resp or not require:
            if not resp or resp[0].lower() == 'y':
                return True
            elif len(resp) > 0 and resp[0].lower() == 'n':
                return False
        resp = raw_input("Type 'y' or 'n': ").strip()


# Autotagging interface.

def choose_candidate(items, cur_artist, cur_album, candidates):
    """Given current metadata and a sorted list of
    (distance, candidate) pairs, ask the user for a selection
    of which candidate to use. Returns the selected candidate. If no
    candidate is judged good enough, returns None.
    """
    # Is the change good enough?
    THRESH = 0.1 #fixme
    top_dist, top_info = candidates[0]
    bypass_candidates = False
    if top_dist <= THRESH:
        dist, info = top_dist, top_info
        bypass_candidates = True
        
    while True:
        # Display and choose from candidates.
        if not bypass_candidates:
            print 'Candidates:'
            for i, (dist, info) in enumerate(candidates):
                print '%i. %s - %s (%f)' % (i+1, info['artist'],
                                            info['album'], dist)
            sel = None
            while not sel:
                # Ask the user for a choice.
                inp = raw_input('Enter a number or "s" to skip: ')
                inp = inp.strip()
                if inp.lower().startswith('s'):
                    return None
                try:
                    sel = int(inp)
                except ValueError:
                    pass
                if not (1 <= sel <= len(candidates)):
                    sel = None
            dist, info = candidates[sel-1]
        bypass_candidates = False
    
        # Show what we're about to do.
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
    
        # Warn if change is significant.
        if dist > 0.0:
            if _input_yn("Apply change ([y]/n)? "):
                return info

def tag_album(items, lib, copy=True, write=True):
    """Import items into lib, tagging them as an album. If copy, then
    items are copied into the destination directory. If write, then
    new metadata is written back to the files' tags.
    """
    # Infer tags.
    try:
        items,(cur_artist,cur_album),candidates = autotag.tag_album(items)
    except autotag.AutotagError:
        print "Untaggable album:", os.path.dirname(items[0].path)
        return
    
    # Choose which tags to use.
    info = choose_candidate(items, cur_artist, cur_album, candidates)
    if not info:
        return
    
    # Ensure that we don't have the album already.
    q = library.AndQuery((library.MatchQuery('artist', info['artist']),
                          library.MatchQuery('album',  info['album'])))
    count, _ = q.count(lib)
    if count >= 1:
        print "This album (%s - %s) is already in the library!" % \
              (info['artist'], info['album'])
        return
    
    # Change metadata and add to library.
    autotag.apply_metadata(items, info)
    for item in items:
        if copy:
            item.move(lib, True)
        lib.add(item)
        if write:
            item.write()


# Top-level commands.

def import_files(lib, paths, copy=True, write=True):
    """Import the files in the given list of paths, tagging each leaf
    directory as an album. If copy, then the files are copied into
    the library folder. If write, then new metadata is written to the
    files themselves.
    """
    first = True
    for path in paths:
        for album in autotag.albums_in_dir(os.path.expanduser(path)):
            if not first:
                print
            first = False

            tag_album(album, lib, copy, write)
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

def start_bpd(lib, host, port, password):
    """Starts a BPD server."""
    from beets.player.bpd import Server
    Server(lib, host, port, password).run()
