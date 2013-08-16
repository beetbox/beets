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

from beets import plugins
from beets import config
from beets.util import plurality
from beets.util.enumeration import enum
from beets.autotag import hooks

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

def current_metadata(items):
    """Extract the likely current metadata for an album given a list of its
    items. Return two dictionaries:
     - The most common value for each field.
     - Whether each field's value was unanimous (values are booleans).
    """
    assert items  # Must be nonempty.

    likelies = {}
    consensus = {}
    fields = ['artist', 'album', 'albumartist', 'year', 'disctotal',
              'mb_albumid', 'label', 'catalognum', 'country', 'media',
              'albumdisambig']
    for key in fields:
        values = [getattr(item, key) for item in items if item]
        likelies[key], freq = plurality(values)
        consensus[key] = (freq == len(values))

    # If there's an album artist consensus, use this for the artist.
    if consensus['albumartist'] and likelies['albumartist']:
        likelies['artist'] = likelies['albumartist']

    return likelies, consensus

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
    Distance object. `incl_artist` indicates that a distance component should
    be included for the track artist (i.e., for various-artist releases).
    """
    dist = hooks.Distance()

    # Length.
    if track_info.length:
        diff = abs(item.length - track_info.length) - \
               config['match']['track_length_grace'].as_number()
        dist.add_ratio('track_length', diff,
                       config['match']['track_length_max'].as_number())

    # Title.
    dist.add_string('track_title', item.title, track_info.title)

    # Artist. Only check if there is actually an artist in the track data.
    if incl_artist and track_info.artist and \
            item.artist.lower() not in VA_ARTISTS:
        dist.add_string('track_artist', item.artist, track_info.artist)

    # Track index.
    if track_info.index and item.track:
        dist.add_expr('track_index', track_index_changed(item, track_info))

    # Track ID.
    if item.mb_trackid:
        dist.add_expr('track_id', item.mb_trackid != track_info.track_id)

    # Plugins.
    dist.update(plugins.track_distance(item, track_info))

    return dist

def distance(items, album_info, mapping):
    """Determines how "significant" an album metadata change would be.
    Returns a Distance object. `album_info` is an AlbumInfo object
    reflecting the album to be compared. `items` is a sequence of all
    Item objects that will be matched (order is not important).
    `mapping` is a dictionary mapping Items to TrackInfo objects; the
    keys are a subset of `items` and the values are a subset of
    `album_info.tracks`.
    """
    likelies, _ = current_metadata(items)

    dist = hooks.Distance()

    # Artist, if not various.
    if not album_info.va:
        dist.add_string('artist', likelies['artist'], album_info.artist)

    # Album.
    dist.add_string('album', likelies['album'], album_info.album)

    # Current or preferred media.
    if album_info.media:
        # Preferred media options.
        patterns = config['match']['preferred']['media'].as_str_seq()
        options = [re.compile(r'(\d+x)?(%s)' % pat, re.I) for pat in patterns]
        if options:
            dist.add_priority('media', album_info.media, options)
        # Current media.
        elif likelies['media']:
            dist.add_equality('media', album_info.media, likelies['media'])

    # Mediums.
    if likelies['disctotal'] and album_info.mediums:
        dist.add_number('mediums', likelies['disctotal'], album_info.mediums)

    # Prefer earliest release.
    if album_info.year and config['match']['preferred']['original_year']:
        # Assume 1889 (earliest first gramophone discs) if we don't know the
        # original year.
        original = album_info.original_year or 1889
        diff = abs(album_info.year - original)
        diff_max = abs(datetime.date.today().year - original)
        dist.add_ratio('year', diff, diff_max)
    # Year.
    elif likelies['year'] and album_info.year:
        if likelies['year'] in (album_info.year, album_info.original_year):
            # No penalty for matching release or original year.
            dist.add('year', 0.0)
        elif album_info.original_year:
            # Prefer matchest closest to the release year.
            diff = abs(likelies['year'] - album_info.year)
            diff_max = abs(datetime.date.today().year -
                           album_info.original_year)
            dist.add_ratio('year', diff, diff_max)
        else:
            # Full penalty when there is no original year.
            dist.add('year', 1.0)

    # Preferred countries.
    patterns = config['match']['preferred']['countries'].as_str_seq()
    options = [re.compile(pat, re.I) for pat in patterns]
    if album_info.country and options:
        dist.add_priority('country', album_info.country, options)
    # Country.
    elif likelies['country'] and album_info.country:
        dist.add_string('country', likelies['country'], album_info.country)

    # Label.
    if likelies['label'] and album_info.label:
        dist.add_string('label', likelies['label'], album_info.label)

    # Catalog number.
    if likelies['catalognum'] and album_info.catalognum:
        dist.add_string('catalognum', likelies['catalognum'],
                        album_info.catalognum)

    # Disambiguation.
    if likelies['albumdisambig'] and album_info.albumdisambig:
        dist.add_string('albumdisambig', likelies['albumdisambig'],
                        album_info.albumdisambig)

    # Album ID.
    if likelies['mb_albumid']:
        dist.add_equality('album_id', likelies['mb_albumid'],
                          album_info.album_id)

    # Tracks.
    dist.tracks = {}
    for item, track in mapping.iteritems():
        dist.tracks[track] = track_distance(item, track, album_info.va)
        dist.add('tracks', dist.tracks[track].distance)

    # Missing tracks.
    for i in range(len(album_info.tracks) - len(mapping)):
        dist.add('missing_tracks', 1.0)

    # Unmatched tracks.
    for i in range(len(items) - len(mapping)):
        dist.add('unmatched_tracks', 1.0)

    # Plugins.
    dist.update(plugins.album_distance(items, album_info, mapping))

    return dist

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
        return hooks.album_for_mbid(albumid)
    else:
        log.debug('No album ID consensus.')

def _recommendation(results):
    """Given a sorted list of AlbumMatch or TrackMatch objects, return a
    recommendation based on the results' distances.

    If the recommendation is higher than the configured maximum for
    an applied penalty, the recommendation will be downgraded to the
    configured maximum for that penalty.
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
        # No conclusion. Return immediately. Can't be downgraded any further.
        return recommendation.none

    # Downgrade to the max rec if it is lower than the current rec for an
    # applied penalty.
    keys = set(min_dist.keys())
    if isinstance(results[0], hooks.AlbumMatch):
        for track_dist in min_dist.tracks.values():
            keys.update(track_dist.keys())
    max_rec_view = config['match']['max_rec']
    for key in keys:
        if key in max_rec_view.keys():
            max_rec = max_rec_view[key].as_choice({
                'strong': recommendation.strong,
                'medium': recommendation.medium,
                'low': recommendation.low,
                'none': recommendation.none,
            })
            rec = min(rec, max_rec)

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

    # Skip matches with ignored penalties.
    penalties = [key for _, key in dist]
    for penalty in config['match']['ignored'].as_str_seq():
        if penalty in penalties:
            log.debug('Ignored. Penalty: %s' % penalty)
            return

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
    likelies, consensus = current_metadata(items)
    cur_artist = likelies['artist']
    cur_album = likelies['album']
    log.debug('Tagging %s - %s' % (cur_artist, cur_album))

    # The output result (distance, AlbumInfo) tuples (keyed by MB album
    # ID).
    candidates = {}

    # Search by explicit ID.
    if search_id is not None:
        log.debug('Searching for album ID: ' + search_id)
        search_cands = hooks.albums_for_id(search_id)

    # Use existing metadata or text search.
    else:
        # Try search based on current ID.
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

        # Search terms.
        if not (search_artist and search_album):
            # No explicit search terms -- use current metadata.
            search_artist, search_album = cur_artist, cur_album
        log.debug(u'Search terms: %s - %s' % (search_artist, search_album))

        # Is this album likely to be a "various artist" release?
        va_likely = ((not consensus['artist']) or
                    (search_artist.lower() in VA_ARTISTS) or
                    any(item.comp for item in items))
        log.debug(u'Album might be VA: %s' % str(va_likely))

        # Get the results from the data sources.
        search_cands = hooks.album_candidates(items, search_artist,
                                              search_album, va_likely)

    log.debug(u'Evaluating %i candidates.' % len(search_cands))
    for info in search_cands:
        _add_candidate(items, candidates, info)

    # Sort and get the recommendation.
    candidates = sorted(candidates.itervalues())
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
        for track_info in hooks.tracks_for_id(trackid):
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
    for track_info in hooks.item_candidates(item, search_artist, search_title):
        dist = track_distance(item, track_info, incl_artist=True)
        candidates[track_info.track_id] = hooks.TrackMatch(dist, track_info)

    # Sort by distance and return with recommendation.
    log.debug('Found %i candidates.' % len(candidates))
    candidates = sorted(candidates.itervalues())
    rec = _recommendation(candidates)
    return candidates, rec
