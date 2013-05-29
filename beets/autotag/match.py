# This file is part of beets.
# Copyright 2013, Adrian Sampson.
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
from __future__ import division

import datetime
import logging
import re
from munkres import Munkres
from unidecode import unidecode

from beets import plugins
from beets import config
from beets.util import levenshtein, plurality
from beets.util.enumeration import enum
from beets.autotag import hooks

# Distance parameters.
# Text distance weights: proportions on the normalized intuitive edit
# distance.
ARTIST_WEIGHT = config['match']['weight']['artist'].as_number()
ALBUM_WEIGHT = config['match']['weight']['album'].as_number()
# MusicBrainz album ID matches.
ALBUM_ID_WEIGHT = config['match']['weight']['album_id'].as_number()
# The distance between the tagged year and the suggested year.
YEAR_WEIGHT = config['match']['weight']['year'].as_number()
# Difference between actual or preferred media.
MEDIA_WEIGHT = config['match']['weight']['media'].as_number()
# Differences in minor metadata, disctotal, label, etc.
MINOR_WEIGHT = config['match']['weight']['minor'].as_number()
# The weight of the entire distance calculated for a given track.
TRACK_WEIGHT = config['match']['weight']['track'].as_number()
# The weight of a missing track.
MISSING_WEIGHT = config['match']['weight']['missing'].as_number()
# The weight of an extra (unmatched) track.
UNMATCHED_WEIGHT = config['match']['weight']['unmatched'].as_number()
# These distances are components of the track distance (that is, they
# compete against each other but not ARTIST_WEIGHT and ALBUM_WEIGHT;
# the overall TRACK_WEIGHT does that).
TRACK_TITLE_WEIGHT = config['match']['weight']['track_title'].as_number()
# Used instead of a global artist penalty for various-artist matches.
TRACK_ARTIST_WEIGHT = config['match']['weight']['track_artist'].as_number()
# Added when the indices of tracks don't match.
TRACK_INDEX_WEIGHT = config['match']['weight']['track_index'].as_number()
# Track length weights: no penalty before GRACE, maximum (WEIGHT)
# penalty at GRACE+MAX discrepancy.
TRACK_LENGTH_GRACE = config['match']['weight']['track_length_grace'].as_number()
TRACK_LENGTH_MAX = config['match']['weight']['track_length_max'].as_number()
TRACK_LENGTH_WEIGHT = config['match']['weight']['track_length'].as_number()
# MusicBrainz track ID matches.
TRACK_ID_WEIGHT = config['match']['weight']['track_id'].as_number()

# Preferred media.
PREFERRED_MEDIA = config['match']['preferred_media'].get()

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

# Recommendation enumeration.
recommendation = enum('none', 'low', 'medium', 'strong', name='recommendation')

# Artist signals that indicate "various artists". These are used at the
# album level to determine whether a given release is likely a VA
# release and also on the track level to to remove the penalty for
# differing artists.
VA_ARTISTS = (u'', u'various artists', u'various', u'va', u'unknown')

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
    likelies = {}
    consensus = {}
    fields = ['artist', 'album', 'albumartist', 'year', 'disctotal',
              'mb_albumid', 'label', 'catalognum', 'country', 'media',
              'albumdisambig']
    for key in fields:
        values = [getattr(item, key) for item in items if item]
        likelies[key], freq = plurality(values)
        consensus[key] = (freq == len(values))

    if consensus['albumartist'] and likelies['albumartist']:
        artist = likelies['albumartist']
    else:
        artist = likelies['artist']

    return artist, likelies['album'], consensus['artist'], likelies

def assign_items(items, tracks):
    """Given a list of Items and a list of TrackInfo objects, find the
    best mapping between them. Returns a mapping from Items to TrackInfo
    objects, a set of extra Items, and a set of extra TrackInfo
    objects. These "extra" objects occur when there is an unequal number
    of objects of the two types.
    """
    # Construct the cost matrix.
    costs = []
    for item in items:
        row = []
        for i, track in enumerate(tracks):
            row.append(track_distance(item, track))
        costs.append(row)

    # Find a minimum-cost bipartite matching.
    matching = Munkres().compute(costs)

    # Produce the output matching.
    mapping = dict((items[i], tracks[j]) for (i, j) in matching)
    extra_items = list(set(items) - set(mapping.keys()))
    extra_items.sort(key=lambda i: (i.disc, i.track, i.title))
    extra_tracks = list(set(tracks) - set(mapping.values()))
    extra_tracks.sort(key=lambda t: (t.index, t.title))
    return mapping, extra_items, extra_tracks

def track_index_changed(item, track_info):
    """Returns True if the item and track info index is different. Tolerates
    per disc and per release numbering.
    """
    return item.track not in (track_info.medium_index, track_info.index)

def track_distance(item, track_info, incl_artist=False):
    """Determines the significance of a track metadata change. Returns a
    float in [0.0,1.0]. `incl_artist` indicates that a distance
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
    if incl_artist and track_info.artist and \
            item.artist.lower() not in VA_ARTISTS:
        dist += string_dist(item.artist, track_info.artist) * \
                TRACK_ARTIST_WEIGHT
        dist_max += TRACK_ARTIST_WEIGHT

    # Track index.
    if track_info.index and item.track:
        if track_index_changed(item, track_info):
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

def distance(items, album_info, mapping):
    """Determines how "significant" an album metadata change would be.
    Returns a float in [0.0,1.0]. `album_info` is an AlbumInfo object
    reflecting the album to be compared. `items` is a sequence of all
    Item objects that will be matched (order is not important).
    `mapping` is a dictionary mapping Items to TrackInfo objects; the
    keys are a subset of `items` and the values are a subset of
    `album_info.tracks`.
    """
    cur_artist, cur_album, _, likelies = current_metadata(items)
    cur_artist = cur_artist or u''
    cur_album = cur_album or u''

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

    # Year. No penalty for matching release or original year.
    if likelies['year'] and album_info.year:
        if likelies['year'] not in (album_info.year, album_info.original_year):
            diff = abs(album_info.year - likelies['year'])
            if diff:
                dist += (1.0 - 1.0 / diff) * YEAR_WEIGHT
        dist_max += YEAR_WEIGHT

    # Actual or preferred media.
    if likelies['media'] and album_info.media:
        dist += string_dist(likelies['media'], album_info.media) * MEDIA_WEIGHT
        dist_max += MEDIA_WEIGHT
    elif album_info.media and PREFERRED_MEDIA:
        dist += string_dist(album_info.media, PREFERRED_MEDIA) * MEDIA_WEIGHT
        dist_max += MEDIA_WEIGHT

    # MusicBrainz album ID.
    if likelies['mb_albumid']:
        if likelies['mb_albumid'] != album_info.album_id:
            dist += ALBUM_ID_WEIGHT
        dist_max += ALBUM_ID_WEIGHT

    # Apply a small penalty for differences across many minor metadata. This
    # helps prioritise releases that are nearly identical.

    if likelies['disctotal']:
        if likelies['disctotal'] != album_info.mediums:
            dist += MINOR_WEIGHT
        dist_max += MINOR_WEIGHT

    if likelies['label'] and album_info.label:
        dist += string_dist(likelies['label'], album_info.label) * MINOR_WEIGHT
        dist_max += MINOR_WEIGHT

    if likelies['catalognum'] and album_info.catalognum:
        dist += string_dist(likelies['catalognum'],
                            album_info.catalognum) * MINOR_WEIGHT
        dist_max += MINOR_WEIGHT

    if likelies['country'] and album_info.country:
        dist += string_dist(likelies['country'],
                            album_info.country) * MINOR_WEIGHT
        dist_max += MINOR_WEIGHT

    if likelies['albumdisambig'] and album_info.albumdisambig:
        dist += string_dist(likelies['albumdisambig'],
                            album_info.albumdisambig) * MINOR_WEIGHT
        dist_max += MINOR_WEIGHT

    # Matched track distances.
    for item, track in mapping.iteritems():
        dist += track_distance(item, track, album_info.va) * TRACK_WEIGHT
        dist_max += TRACK_WEIGHT

    # Extra and unmatched tracks.
    for track in set(album_info.tracks) - set(mapping.values()):
        dist += MISSING_WEIGHT
        dist_max += MISSING_WEIGHT
    for item in set(items) - set(mapping.keys()):
        dist += UNMATCHED_WEIGHT
        dist_max += UNMATCHED_WEIGHT

    # Plugin distances.
    plugin_d, plugin_dm = plugins.album_distance(items, album_info, mapping)
    dist += plugin_d
    dist_max += plugin_dm

    # Normalize distance, avoiding divide-by-zero.
    if dist_max == 0.0:
        return 0.0
    else:
        return dist / dist_max

def match_by_id(items):
    """If the items are tagged with a MusicBrainz album ID, returns an
    AlbumInfo object for the corresponding album. Otherwise, returns
    None.
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

def _recommendation(results):
    """Given a sorted list of AlbumMatch or TrackMatch objects, return a
    recommendation based on the results' distances.

    If the recommendation is higher than the configured maximum for
    certain situations, the recommendation will be downgraded to the
    configured maximum.
    """
    if not results:
        # No candidates: no recommendation.
        return recommendation.none

    # Basic distance thresholding.
    min_dist = results[0].distance
    if min_dist < config['match']['strong_rec_thresh'].as_number():
        # Strong recommendation level.
        rec = recommendation.strong
    elif min_dist <= config['match']['medium_rec_thresh'].as_number():
        # Medium recommendation level.
        rec = recommendation.medium
    elif len(results) == 1:
        # Only a single candidate.
        rec = recommendation.low
    elif results[1].distance - min_dist >= \
            config['match']['rec_gap_thresh'].as_number():
        # Gap between first two candidates is large.
        rec = recommendation.low
    else:
        # No conclusion.
        rec = recommendation.none

    # "Downgrades" in certain configured situations.
    if isinstance(results[0], hooks.AlbumMatch):
        # Load the configured recommendation maxima.
        max_rec = {}
        for trigger in 'non_mb_source', 'partial', 'tracklength', 'tracknumber':
            max_rec[trigger] = \
                config['match']['max_rec'][trigger].as_choice({
                    'strong': recommendation.strong,
                    'medium': recommendation.medium,
                    'low': recommendation.low,
                    'none': recommendation.none,
                })

        # Non-MusicBrainz source.
        if rec > max_rec['non_mb_source'] and \
                results[0].info.data_source != 'MusicBrainz':
            rec = max_rec['non_mb_source']

        # Partial match.
        if rec > max_rec['partial'] and \
                (results[0].extra_items or results[0].extra_tracks):
            rec = max_rec['partial']

        # Check track number and duration for each item.
        for item, track_info in results[0].mapping.items():
            # Track length differs.
            if rec > max_rec['tracklength'] and \
                    item.length and track_info.length and \
                    abs(item.length - track_info.length) > TRACK_LENGTH_GRACE:
                rec = max_rec['tracklength']

            # Track number differs.
            if rec > max_rec['tracknumber'] and \
                    track_index_changed(item, track_info):
                rec = max_rec['tracknumber']

    return rec

def _add_candidate(items, results, info):
    """Given a candidate AlbumInfo object, attempt to add the candidate
    to the output dictionary of AlbumMatch objects. This involves
    checking the track count, ordering the items, checking for
    duplicates, and calculating the distance.
    """
    log.debug('Candidate: %s - %s' % (info.artist, info.album))

    # Don't duplicate.
    if info.album_id in results:
        log.debug('Duplicate.')
        return

    # Find mapping between the items and the track info.
    mapping, extra_items, extra_tracks = assign_items(items, info.tracks)

    # Get the change distance.
    dist = distance(items, info, mapping)
    log.debug('Success. Distance: %f' % dist)

    results[info.album_id] = hooks.AlbumMatch(dist, info, mapping,
                                              extra_items, extra_tracks)

def tag_album(items, search_artist=None, search_album=None,
              search_id=None):
    """Bundles together the functionality used to infer tags for a
    set of items comprised by an album. Returns everything relevant:
        - The current artist.
        - The current album.
        - A list of AlbumMatch objects. The candidates are sorted by
        distance (i.e., best match first).
        - A recommendation.
    If search_artist and search_album or search_id are provided, then
    they are used as search terms in place of the current metadata.
    """
    # Get current metadata.
    cur_artist, cur_album, artist_consensus, _ = current_metadata(items)
    log.debug('Tagging %s - %s' % (cur_artist, cur_album))

    # The output result (distance, AlbumInfo) tuples (keyed by MB album
    # ID).
    candidates = {}

    # Try to find album indicated by MusicBrainz IDs.
    if search_id:
        log.debug('Searching for album ID: ' + search_id)
        id_info = hooks._album_for_id(search_id)
    else:
        id_info = match_by_id(items)
    if id_info:
        _add_candidate(items, candidates, id_info)
        rec = _recommendation(candidates.values())
        log.debug('Album ID match recommendation is ' + str(rec))
        if candidates and not config['import']['timid']:
            # If we have a very good MBID match, return immediately.
            # Otherwise, this match will compete against metadata-based
            # matches.
            if rec == recommendation.strong:
                log.debug('ID match.')
                return cur_artist, cur_album, candidates.values(), rec

    # If searching by ID, don't continue to metadata search.
    if search_id is not None:
        if candidates:
            return cur_artist, cur_album, candidates.values(), rec
        else:
            return cur_artist, cur_album, [], recommendation.none

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
    search_cands = hooks._album_candidates(items, search_artist, search_album,
                                           va_likely)
    log.debug(u'Evaluating %i candidates.' % len(search_cands))
    for info in search_cands:
        _add_candidate(items, candidates, info)

    # Sort and get the recommendation.
    candidates = sorted(candidates.itervalues(),
            key=lambda i: (i.distance, i.info.data_source != 'MusicBrainz'))
    rec = _recommendation(candidates)
    return cur_artist, cur_album, candidates, rec

def tag_item(item, search_artist=None, search_title=None,
             search_id=None):
    """Attempts to find metadata for a single track. Returns a
    `(candidates, recommendation)` pair where `candidates` is a list of
    TrackMatch objects. `search_artist` and `search_title` may be used
    to override the current metadata for the purposes of the MusicBrainz
    title; likewise `search_id`.
    """
    # Holds candidates found so far: keys are MBIDs; values are
    # (distance, TrackInfo) pairs.
    candidates = {}

    # First, try matching by MusicBrainz ID.
    trackid = search_id or item.mb_trackid
    if trackid:
        log.debug('Searching for track ID: ' + trackid)
        track_info = hooks._track_for_id(trackid)
        if track_info:
            dist = track_distance(item, track_info, incl_artist=True)
            candidates[track_info.track_id] = \
                    hooks.TrackMatch(dist, track_info)
            # If this is a good match, then don't keep searching.
            rec = _recommendation(candidates.values())
            if rec == recommendation.strong and not config['import']['timid']:
                log.debug('Track ID match.')
                return candidates.values(), rec

    # If we're searching by ID, don't proceed.
    if search_id is not None:
        if candidates:
            return candidates.values(), rec
        else:
            return [], recommendation.none

    # Search terms.
    if not (search_artist and search_title):
        search_artist, search_title = item.artist, item.title
    log.debug(u'Item search terms: %s - %s' % (search_artist, search_title))

    # Get and evaluate candidate metadata.
    for track_info in hooks._item_candidates(item, search_artist, search_title):
        dist = track_distance(item, track_info, incl_artist=True)
        candidates[track_info.track_id] = hooks.TrackMatch(dist, track_info)

    # Sort by distance and return with recommendation.
    log.debug('Found %i candidates.' % len(candidates))
    candidates = sorted(candidates.itervalues())
    rec = _recommendation(candidates)
    return candidates, rec
