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

"""Facilities for automatically determining files' correct metadata.
"""

import os
from collections import defaultdict
from beets.autotag.mb import match_album
from beets import library
from beets.mediafile import FileTypeError

# If the MusicBrainz length is more than this many seconds away from the
# track length, an error is reported.
LENGTH_TOLERANCE = 2

def likely_metadata(items):
    """Returns the most likely artist and album for a set of Items.
    Each is determined by tag reflected by the plurality of the Items.
    """
    # The tags we'll try to determine.
    keys = 'artist', 'album'

    # Make dictionaries in which to count the freqencies of different
    # artist and album tags. We'll use this to find the most likely
    # artist and album. Defaultdicts let the frequency default to zero.
    freqs = {}
    for key in keys:
        freqs[key] = defaultdict(int)

    # Count the frequencies.
    for item in items:
        for key in keys:
            value = getattr(item, key)
            if value: # Don't count empty tags.
                freqs[key][value] += 1

    # Find max-frequency tags.
    likelies = {}
    for key in keys:
        max_freq = 0
        likelies[key] = None
        for tag, freq in freqs[key].items():
            if freq > max_freq:
                max_freq = freq
                likelies[key] = tag
    
    return (likelies['artist'], likelies['album'])

def _input_yn(prompt):
    """Prompts user for a "yes" or "no" response where an empty response
    is treated as "yes". Keeps prompting until acceptable input is
    given; returns a boolean.
    """
    resp = raw_input(prompt)
    while True:
        if len(resp) == 0 or resp[0].tolower() == 'y':
            return True
        elif len(resp) > 0 and resp[0].tolower() == 'n':
            return False
        resp = raw_input("Type 'y' or 'n': ")

def tag_album_dir(path, lib):
    # Read items from directory.
    items = []
    for filename in os.listdir(path):
        filepath = library._normpath(os.path.join(path, filename))
        try:
            i = library.Item.from_path(filepath, lib)
        except FileTypeError:
            continue
        items.append(i)
    
    #fixme Check if MB tags are already present.
    
    # Find existing metadata.
    cur_artist, cur_album = likely_metadata(items)
    
    # Find "correct" metadata.
    info = match_album(cur_artist, cur_album, len(items))
    if len(cur_artist) == 0 or len(cur_album) == 0 or \
                cur_artist.lower() != info['artist'].lower() or \
                cur_album.lower()  != info['album'].lower():
        # If we're making a "significant" change (changing the artist or
        # album), confirm with the user to avoid mistakes.
        print "Correcting tags from:"
        print '%s - %s' % (cur_artist, cur_album)
        print "To:"
        print '%s - %s' % (info['artist'], info['album'])
        if not _input_yn("Apply change ([y]/n)? "):
            return
    
    else:
        print 'Tagging album: %s - %s' % (info['artist'], info['album'])
    
    
    # Ensure that we don't have the album already.
    q = library.AndQuery((library.MatchQuery('artist', info['artist']),
                          library.MatchQuery('album',  info['album'])))
    count, _ = q.count(lib)
    if count >= 1:
        print "This album (%s - %s) is already in the library!" % \
              (info['artist'], info['album'])
        return
    
    # Determine order of existing tracks.
    # First, see if the current tags indicate an ordering.
    ordered_items = [None]*len(items)
    available_indices = set(range(len(items)))
    for item in items:
        if item.track:
            index = item.track - 1
            ordered_items[index] = item
            available_indices.remove(index)
        else:
            # If we have any item without an index, give up.
            break
    if available_indices:
        print "Tracks are not correctly ordered."
        return
        #fixme:
        # Otherwise, match based on names and lengths of tracks (confirm).
    
    # Apply new metadata.
    for index, (item, track_data) in enumerate(zip(ordered_items,
                                                   info['tracks']
                                              )):
        
        # For safety, ensure track lengths match.
        if not (item.length - LENGTH_TOLERANCE <
                track_data['length'] <
                item.length + LENGTH_TOLERANCE):
            print "Length mismatch on track %i: actual length is %f and MB " \
                  "length is %f." % (index, item.length, track_data['length'])
            return
            
        if item.title != track_data['title']:
            print "%s -> %s" % (item.title, track_data['title'])
        
        item.artist = info['artist']
        item.album = info['album']
        item.track_total = len(items)
        item.year = info['year']
        if 'month' in info:
            item.month = info['month']
        if 'day' in info:
            item.day = info['day']
        
        item.title = track_data['title']
        item.track = index + 1
        
        #fixme Set MusicBrainz IDs!
    
    # Add items to library and write their tags.
    for item in ordered_items:
        item.move(True)
        item.add()
        item.write()


if __name__ == '__main__':
    import sys
    lib = library.Library()
    path = os.path.expanduser(sys.argv[1])
    tag_album_dir(path, lib)
    lib.save()

