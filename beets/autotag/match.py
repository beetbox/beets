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

"""Matches existing metadata with canonical information to identify
releases and tracks.
"""
import logging
import re
from munkres import Munkres
from unidecode import unidecode

from beets import plugins
from beets.util import levenshtein, plurality
from beets.autotag import hooks

# Distance parameters.
# Text distance weights: proportions on the normalized intuitive edit
# distance.
ARTIST_WEIGHT = 3.0
ALBUM_WEIGHT = 3.0
# The weight of the entire distance calculated for a given track.
TRACK_WEIGHT = 1.0
# The weight of a missing track.
MISSING_WEIGHT = 0.9
# These distances are components of the track distance (that is, they
# compete against each other but not ARTIST_WEIGHT and ALBUM_WEIGHT;
# the overall TRACK_WEIGHT does that).
TRACK_TITLE_WEIGHT = 3.0
# Used instead of a global artist penalty for various-artist matches.
TRACK_ARTIST_WEIGHT = 2.0
# Added when the indices of tracks don't match.
TRACK_INDEX_WEIGHT = 1.0
# Track length weights: no penalty before GRACE, maximum (WEIGHT)
# penalty at GRACE+MAX discrepancy.
TRACK_LENGTH_GRACE = 10
TRACK_LENGTH_MAX = 30
TRACK_LENGTH_WEIGHT = 2.0
# MusicBrainz track ID matches.
TRACK_ID_WEIGHT = 5.0

# Parameters for string distance function.
# Words that can be moved to the end of a string using a comma.
SD_END_WORDS = ['the', 'a', 'an']
# Reduced weights for certain portions of the string.
SD_PATTERNS = [
    (r'^the ', 0.1),
    (r'[\[\(]?(ep|single)[\]\)]?', 0.0),
    (r'[\[\(]?(featuring|feat|ft)[\. :].+', 0.1),
    (r'\(.*?\)', 0.3),
    (r'\[.*?\]', 0.3),
    (r'(, )?(pt\.|part) .+', 0.2),
]
# Replacements to use before testing distance.
SD_REPLACE = [
    (r'&', 'and'),
]

# Recommendation constants.
RECOMMEND_STRONG = 'RECOMMEND_STRONG'
RECOMMEND_MEDIUM = 'RECOMMEND_MEDIUM'
RECOMMEND_NONE = 'RECOMMEND_NONE'
# Thresholds for recommendations.
STRONG_REC_THRESH = 0.04
MEDIUM_REC_THRESH = 0.25
REC_GAP_THRESH = 0.25

# Artist signals that indicate "various artists".
VA_ARTISTS = (u'', u'various artists', u'va', u'unknown')

# Autotagging exceptions.
class AutotagError(Exception):
    pass

# Global logger.
log = logging.getLogger('beets')


# Primary matching functionality.

def _string_dist_basic(str1, str2):
    """Basic edit distance between two strings, ignoring
    non-alphanumeric characters and case. Comparisons are based on a
    transliteration/lowering to ASCII characters. Normalized by string
    length.
    """
    str1 = unidecode(str1)
    str2 = unidecode(str2)
    str1 = re.sub(r'[^a-z0-9]', '', str1.lower())
    str2 = re.sub(r'[^a-z0-9]', '', str2.lower())
    if not str1 and not str2:
        return 0.0
    return levenshtein(str1, str2) / float(max(len(str1), len(str2)))

def string_dist(str1, str2):
    """Gives an "intuitive" edit distance between two strings. This is
    an edit distance, normalized by the string length, with a number of
    tweaks that reflect intuition about text.
    """
    str1 = str1.lower()
    str2 = str2.lower()
    
    # Don't penalize strings that move certain words to the end. For
    # example, "the something" should be considered equal to
    # "something, the".
    for word in SD_END_WORDS:
        if str1.endswith(', %s' % word):
            str1 = '%s %s' % (word, str1[:-len(word)-2])
        if str2.endswith(', %s' % word):
            str2 = '%s %s' % (word, str2[:-len(word)-2])

    # Perform a couple of basic normalizing substitutions.
    for pat, repl in SD_REPLACE:
        str1 = re.sub(pat, repl, str1)
        str2 = re.sub(pat, repl, str2)
    
    # Change the weight for certain string portions matched by a set
    # of regular expressions. We gradually change the strings and build
    # up penalties associated with parts of the string that were
    # deleted.
    base_dist = _string_dist_basic(str1, str2)
    penalty = 0.0
    for pat, weight in SD_PATTERNS:
        # Get strings that drop the pattern.
        case_str1 = re.sub(pat, '', str1)
        case_str2 = re.sub(pat, '', str2)
        
        if case_str1 != str1 or case_str2 != str2:
            # If the pattern was present (i.e., it is deleted in the
            # the current case), recalculate the distances for the
            # modified strings.
            case_dist = _string_dist_basic(case_str1, case_str2)
            case_delta = max(0.0, base_dist - case_dist)
            if case_delta == 0.0:
                continue
            
            # Shift our baseline strings down (to avoid rematching the
            # same part of the string) and add a scaled distance
            # amount to the penalties.
            str1 = case_str1
            str2 = case_str2
            base_dist = case_dist
            penalty += weight * case_delta
    dist = base_dist + penalty
    
    return dist

def current_metadata(items):
    """Returns the most likely artist and album for a set of Items.
    Each is determined by tag reflected by the plurality of the Items.
    """
    keys = 'artist', 'album'
    likelies = {}
    consensus = {}
    for key in keys:
        values = [getattr(item, key) for item in items if item]
        likelies[key], freq = plurality(values)
        consensus[key] = (freq == len(values))
    return likelies['artist'], likelies['album'], consensus['artist']

def order_items(items, trackinfo):
    """Orders the items based on how they match some canonical track
    information. Returns a list of Items whose length is equal to the
    length of ``trackinfo``. This always produces a result if the
    numbers of items is at most the number of TrackInfo objects
    (otherwise, returns None). In the case of a partial match, the
    returned list may contain None in some positions.
    """
    # Make sure lengths match: If there is less items, it might just be that
    # there is some tracks missing.
    if len(items) > len(trackinfo):
        return None

    # Construct the cost matrix.
    costs = []
    for cur_item in items:
        row = []
        for i, canon_item in enumerate(trackinfo):
            row.append(track_distance(cur_item, canon_item, i+1))
        costs.append(row)
    
    # Find a minimum-cost bipartite matching.
    matching = Munkres().compute(costs)

    # Order items based on the matching.
    ordered_items = [None]*len(trackinfo)
    for cur_idx, canon_idx in matching:
        ordered_items[canon_idx] = items[cur_idx]
    return ordered_items

def track_distance(item, track_info, track_index=None, incl_artist=False):
    """Determines the significance of a track metadata change. Returns
    a float in [0.0,1.0]. `track_index` is the track number of the
    `track_info` metadata set. If `track_index` is provided and
    item.track is set, then these indices are used as a component of
    the distance calculation. `incl_artist` indicates that a distance
    component should be included for the track artist (i.e., for
    various-artist releases).
    """
    # Distance and normalization accumulators.
    dist, dist_max = 0.0, 0.0

    # Check track length.
    # If there's no length to check, apply no penalty.
    if track_info.length:
        diff = abs(item.length - track_info.length)
        diff = max(diff - TRACK_LENGTH_GRACE, 0.0)
        diff = min(diff, TRACK_LENGTH_MAX)
        dist += (diff / TRACK_LENGTH_MAX) * TRACK_LENGTH_WEIGHT
    dist_max += TRACK_LENGTH_WEIGHT
    
    # Track title.
    dist += string_dist(item.title, track_info.title) * TRACK_TITLE_WEIGHT
    dist_max += TRACK_TITLE_WEIGHT

    # Track artist, if included.
    # Attention: MB DB does not have artist info for all compilations,
    # so only check artist distance if there is actually an artist in
    # the MB track data.
    if incl_artist and track_info.artist:
        dist += string_dist(item.artist, track_info.artist) * \
                TRACK_ARTIST_WEIGHT
        dist_max += TRACK_ARTIST_WEIGHT

    # Track index.
    if track_index and item.track:
        if track_index != item.track:
            dist += TRACK_INDEX_WEIGHT
        dist_max += TRACK_INDEX_WEIGHT
    
    # MusicBrainz track ID.
    if item.mb_trackid:
        if item.mb_trackid != track_info.track_id:
            dist += TRACK_ID_WEIGHT
        dist_max += TRACK_ID_WEIGHT

    # Plugin distances.
    plugin_d, plugin_dm = plugins.track_distance(item, track_info)
    dist += plugin_d
    dist_max += plugin_dm

    return dist / dist_max

def distance(items, album_info):
    """Determines how "significant" an album metadata change would be.
    Returns a float in [0.0,1.0]. The list of items must be ordered.
    """
    cur_artist, cur_album, _ = current_metadata(items)
    cur_artist = cur_artist or ''
    cur_album = cur_album or ''
    
    # These accumulate the possible distance components. The final
    # distance will be dist/dist_max.
    dist = 0.0
    dist_max = 0.0
    
    # Artist/album metadata.
    if not album_info.va:
        dist += string_dist(cur_artist, album_info.artist) * ARTIST_WEIGHT
        dist_max += ARTIST_WEIGHT
    dist += string_dist(cur_album,  album_info.album) * ALBUM_WEIGHT
    dist_max += ALBUM_WEIGHT
    
    # Track distances.
    for i, (item, track_info) in enumerate(zip(items, album_info.tracks)):
        if item:
            dist += track_distance(item, track_info, i+1, album_info.va) * \
                    TRACK_WEIGHT
            dist_max += TRACK_WEIGHT
        else:
            dist += MISSING_WEIGHT
            dist_max += MISSING_WEIGHT

    # Plugin distances.
    plugin_d, plugin_dm = plugins.album_distance(items, album_info)
    dist += plugin_d
    dist_max += plugin_dm

    # Normalize distance, avoiding divide-by-zero.
    if dist_max == 0.0:
        return 0.0
    else:
        return dist/dist_max

def match_by_id(items):
    """If the items are tagged with a MusicBrainz album ID, returns an
    info dict for the corresponding album. Otherwise, returns None.
    """
    # Is there a consensus on the MB album ID?
    albumids = [item.mb_albumid for item in items if item.mb_albumid]
    if not albumids:
        log.debug('No album IDs found.')
        return None
    
    # If all album IDs are equal, look up the album.
    if bool(reduce(lambda x,y: x if x==y else (), albumids)):
        albumid = albumids[0]
        log.debug('Searching for discovered album ID: ' + albumid)
        return hooks._album_for_id(albumid)
    else:
        log.debug('No album ID consensus.')
        return None
    
    #fixme In the future, at the expense of performance, we could use
    # other IDs (i.e., track and artist) in case the album tag isn't
    # present, but that event seems very unlikely.

def recommendation(results):
    """Given a sorted list of result tuples, returns a recommendation
    flag (RECOMMEND_STRONG, RECOMMEND_MEDIUM, RECOMMEND_NONE) based
    on the results' distances.
    """
    if not results:
        # No candidates: no recommendation.
        rec = RECOMMEND_NONE
    else:
        min_dist = results[0][0]
        if min_dist < STRONG_REC_THRESH:
            # Strong recommendation level.
            rec = RECOMMEND_STRONG
        elif len(results) == 1:
            # Only a single candidate. Medium recommendation.
            rec = RECOMMEND_MEDIUM
        elif min_dist <= MEDIUM_REC_THRESH:
            # Medium recommendation level.
            rec = RECOMMEND_MEDIUM
        elif results[1][0] - min_dist >= REC_GAP_THRESH:
            # Gap between first two candidates is large.
            rec = RECOMMEND_MEDIUM
        else:
            # No conclusion.
            rec = RECOMMEND_NONE
    return rec

def validate_candidate(items, tuple_dict, info):
    """Given a candidate info dict, attempt to add the candidate to
    the output dictionary of result tuples. This involves checking
    the track count, ordering the items, checking for duplicates, and
    calculating the distance.
    """
    log.debug('Candidate: %s - %s' % (info.artist, info.album))

    # Don't duplicate.
    if info.album_id in tuple_dict:
        log.debug('Duplicate.')
        return

    # Make sure the album has the correct number of tracks.
    if len(items) > len(info.tracks):
        log.debug('Too many items to match: %i > %i.' %
                  (len(items), len(info.tracks)))
        return

    # Put items in order.
    ordered = order_items(items, info.tracks)
    if not ordered:
        log.debug('Not orderable.')
        return

    # Get the change distance.
    dist = distance(ordered, info)
    log.debug('Success. Distance: %f' % dist)

    tuple_dict[info.album_id] = dist, ordered, info

def tag_album(items, timid=False, search_artist=None, search_album=None,
              search_id=None):
    """Bundles together the functionality used to infer tags for a
    set of items comprised by an album. Returns everything relevant:
        - The current artist.
        - The current album.
        - A list of (distance, items, info) tuples where info is a
          dictionary containing the inferred tags and items is a
          reordered version of the input items list. The candidates are
          sorted by distance (i.e., best match first).
        - A recommendation, one of RECOMMEND_STRONG, RECOMMEND_MEDIUM,
          or RECOMMEND_NONE; indicating that the first candidate is
          very likely, it is somewhat likely, or no conclusion could
          be reached.
    If search_artist and search_album or search_id are provided, then
    they are used as search terms in place of the current metadata.
    May raise an AutotagError if existing metadata is insufficient.
    """
    # Get current metadata.
    cur_artist, cur_album, artist_consensus = current_metadata(items)
    log.debug('Tagging %s - %s' % (cur_artist, cur_album))
    
    # The output result tuples (keyed by MB album ID).
    out_tuples = {}
    
    # Try to find album indicated by MusicBrainz IDs.
    if search_id:
        log.debug('Searching for album ID: ' + search_id)
        id_info = hooks._album_for_id(search_id)
    else:
        id_info = match_by_id(items)
    if id_info:
        validate_candidate(items, out_tuples, id_info)
        rec = recommendation(out_tuples.values())
        log.debug('Album ID match recommendation is ' + str(rec))
        if out_tuples and not timid:
            # If we have a very good MBID match, return immediately.
            # Otherwise, this match will compete against metadata-based
            # matches.
            if rec == RECOMMEND_STRONG:
                log.debug('ID match.')
                return cur_artist, cur_album, out_tuples.values(), rec

    # If searching by ID, don't continue to metadata search.
    if search_id is not None:
        if out_tuples:
            return cur_artist, cur_album, out_tuples.values(), rec
        else:
            return cur_artist, cur_album, [], RECOMMEND_NONE
    
    # Search terms.
    if not (search_artist and search_album):
        # No explicit search terms -- use current metadata.
        search_artist, search_album = cur_artist, cur_album
    log.debug(u'Search terms: %s - %s' % (search_artist, search_album))
    
    # Is this album likely to be a "various artist" release?
    va_likely = ((not artist_consensus) or
                 (search_artist.lower() in VA_ARTISTS) or
                 any(item.comp for item in items))
    log.debug(u'Album might be VA: %s' % str(va_likely))

    # Get the results from the data sources.
    candidates = hooks._album_candidates(items, search_artist, search_album,
                                         va_likely)
    
    # Get the distance to each candidate.
    log.debug(u'Evaluating %i candidates.' % len(candidates))
    for info in candidates:
        validate_candidate(items, out_tuples, info)
    
    # Sort by distance.
    out_tuples = out_tuples.values()
    out_tuples.sort()
    
    rec = recommendation(out_tuples)
    return cur_artist, cur_album, out_tuples, rec

def tag_item(item, timid=False, search_artist=None, search_title=None,
             search_id=None):
    """Attempts to find metadata for a single track. Returns a
    `(candidates, recommendation)` pair where `candidates` is a list
    of `(distance, track_info)` pairs. `search_artist` and 
    `search_title` may be used to override the current metadata for
    the purposes of the MusicBrainz title; likewise `search_id`.
    """
    candidates = []

    # First, try matching by MusicBrainz ID.
    trackid = search_id or item.mb_trackid
    if trackid:
        log.debug('Searching for track ID: ' + trackid)
        track_info = hooks._track_for_id(trackid)
        if track_info:
            dist = track_distance(item, track_info, incl_artist=True)
            candidates.append((dist, track_info))
            # If this is a good match, then don't keep searching.
            rec = recommendation(candidates)
            if rec == RECOMMEND_STRONG and not timid:
                log.debug('Track ID match.')
                return candidates, rec

    # If we're searching by ID, don't proceed.
    if search_id is not None:
        if candidates:
            return candidates, rec
        else:
            return [], RECOMMEND_NONE
    
    # Search terms.
    if not (search_artist and search_title):
        search_artist, search_title = item.artist, item.title
    log.debug(u'Item search terms: %s - %s' % (search_artist, search_title))

    # Get and evaluate candidate metadata.
    for track_info in hooks._item_candidates(item, search_artist, search_title):
        dist = track_distance(item, track_info, incl_artist=True)
        candidates.append((dist, track_info))

    # Sort by distance and return with recommendation.
    log.debug('Found %i candidates.' % len(candidates))
    candidates.sort()
    rec = recommendation(candidates)
    return candidates, rec
