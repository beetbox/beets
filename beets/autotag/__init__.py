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
from beets.autotag import mb

# If the MusicBrainz length is more than this many seconds away from the
# track length, an error is reported. 30 seconds may seem like overkill,
# but tracks do seem to vary a lot in the wild and this is the
# threshold used by Picard before it even applies a penalty.
LENGTH_TOLERANCE = 30

class AutotagError(Exception): pass
class UnorderedTracksError(AutotagError): pass

def current_metadata(items):
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

def order_items(items):
    """Given a list of items, put them in album order.
    """
    # First, see if the current tags indicate an ordering.
    ordered_items = [None]*len(items)
    available_indices = set(range(len(items)))
    for item in items:
        if item.track:
            index = item.track - 1
            ordered_items[index] = item
            if index in available_indices:
                available_indices.remove(index)
            else:
                # Same index used twice.
                return None
        else:
            # If we have any item without an index, give up.
            return None
    if available_indices:
        # Not all indices were used.
        return None
   
    #fixme: Otherwise, match based on names and lengths of tracks
    # (confirm).
    
    return ordered_items

def distance(items, info):
    """Determines how "significant" an album metadata change would be.
    Returns a float in [0.0,1.0]. The list of items must be ordered.
    """
    cur_artist, cur_album = current_metadata(items)
    
    # These accumulate the possible distance components. The final
    # distance will be dist/dist_max.
    dist = 0.0
    dist_max = 0.0
    
    # If either tag is missing, change should be confirmed.
    if len(cur_artist) == 0 or len(cur_album) == 0:
        return 1.0
    
    # Check whether the new values differ from the old ones.
    #fixme edit distance instead of 1/0
    #fixme filter non-alphanum
    if cur_artist.lower() != info['artist'].lower() or \
       cur_album.lower()  != info['album'].lower():
        dist += 1.0
        dist_max += 1.0
    
    # Find track distances.
    for item, track_data in zip(items, info['tracks']):
        # Check track length.
        if 'length' not in track_data:
            # If there's no length to check, assume the worst.
            return 1.0
        elif abs(item.length - track_data['length']) > LENGTH_TOLERANCE:
            # Abort with maximum. (fixme, something softer?)
            return 1.0
        #fixme track name
    
    # Normalize distance, avoiding divide-by-zero.
    if dist_max == 0.0:
        return 0.0
    else:
        return dist/dist_max

def apply_metadata(items, info):
    """Set the items' metadata to match the data given in info. The
    list of items must be ordered.
    """
    for index, (item, track_data) in enumerate(zip(items,  info['tracks'])):
        item.artist = info['artist']
        item.album = info['album']
        item.tracktotal = len(items)
        
        if 'year' in info:
            item.year = info['year']
        if 'month' in info:
            item.month = info['month']
        if 'day' in info:
            item.day = info['day']
        
        item.title = track_data['title']
        item.track = index + 1
        
        #fixme Set MusicBrainz IDs

def tag_album(items):
    """Bundles together the functionality used to infer tags for a
    set of items comprised by an album. Returns everything relevant
    and a little bit more:
        - The list of items, possibly reordered.
        - The current metadata: an (artist, album) tuple.
        - The inferred metadata dictionary.
        - The distance between the current and new metadata.
    May raise an UnorderedTracksError if existing metadata is
    insufficient.
    """
    # Get current and candidate metadata.
    cur_artist, cur_album = current_metadata(items)
    info = mb.match_album(cur_artist, cur_album, len(items))
    
    # Put items in order.
    items = order_items(items)
    if not items:
        raise UnorderedTracksError()
    
    # Get the change distance.
    dist = distance(items, info)
    
    return items, (cur_artist, cur_album), info, dist

