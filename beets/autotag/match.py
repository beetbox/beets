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

# A configuration view for the distance weights.
weights = config['match']['distance_weights']

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

class Distance(object):
    """Keeps track of multiple distance penalties. Provides a single weighted
    distance for all penalties as well as a weighted distance for each
    individual penalty.
    """
    def __cmp__(self, other):
        return cmp(self.distance, other)

    def __float__(self):
        return self.distance

    def __getitem__(self, key):
        """Returns the weighted distance for a named penalty.
        """
        dist = sum(self._penalties[key]) * weights[key].as_number()
        dist_max = self.max_distance
        if dist_max:
            return dist / dist_max
        return 0.0

    def __init__(self):
        self._penalties = {}

    def __iter__(self):
        return iter(self.sorted)

    def __len__(self):
        return len(self.sorted)

    def __sub__(self, other):
        return self.distance - other

    def __rsub__(self, other):
        return other - self.distance

    def _eq(self, value1, value2):
        """Returns True if `value1` is equal to `value2`. `value1` may be a
        compiled regular expression, in which case it will be matched against
        `value2`.
        """
        if isinstance(value1, re._pattern_type):
            return bool(value1.match(value2))
        return value1 == value2

    def add(self, key, dist):
        """Adds a distance penalty. `key` must correspond with a configured
        weight setting. `dist` must be a float between 0.0 and 1.0, and will be
        added to any existing distance penalties for the same key.
        """
        if not 0.0 <= dist <= 1.0:
            raise ValueError(
                    '`dist` must be between 0.0 and 1.0. It is: %r' % dist)
        self._penalties.setdefault(key, []).append(dist)

    def add_equality(self, key, value, options):
        """Adds a distance penalty of 1.0 if `value` doesn't match any of the
        values in `options`. If an option is a compiled regular expression, it
        will be considered equal if it matches against `value`.
        """
        if not isinstance(options, (list, tuple)):
            options = [options]
        for opt in options:
            if self._eq(opt, value):
                dist = 0.0
                break
        else:
            dist = 1.0
        self.add(key, dist)

    def add_expr(self, key, expr):
        """Adds a distance penalty of 1.0 if `expr` evaluates to True, or 0.0.
        """
        if expr:
            self.add(key, 1.0)
        else:
            self.add(key, 0.0)

    def add_number(self, key, number1, number2):
        """Adds a distance penalty of 1.0 for each number of difference between
        `number1` and `number2`, or 0.0 when there is no difference. Use this
        when there is no upper limit on the difference between the two numbers.
        """
        diff = abs(number1 - number2)
        if diff:
            for i in range(diff):
                self.add(key, 1.0)
        else:
            self.add(key, 0.0)

    def add_priority(self, key, value, options):
        """Adds a distance penalty that corresponds to the position at which
        `value` appears in `options`. A distance penalty of 0.0 for the first
        option, or 1.0 if there is no matching option. If an option is a
        compiled regular expression, it will be considered equal if it matches
        against `value`.
        """
        if not isinstance(options, (list, tuple)):
            options = [options]
        unit = 1.0 / (len(options) or 1)
        for i, opt in enumerate(options):
            if self._eq(opt, value):
                dist = i * unit
                break
        else:
            dist = 1.0
        self.add(key, dist)

    def add_ratio(self, key, number1, number2):
        """Adds a distance penalty for `number1` as a ratio of `number2`.
        `number1` is bound at 0 and `number2`.
        """
        number = float(max(min(number1, number2), 0))
        if number2:
            dist = number / number2
        else:
            dist = 0.0
        self.add(key, dist)

    def add_string(self, key, str1, str2):
        """Adds a distance penalty based on the edit distance between `str1`
        and `str2`.
        """
        dist = string_dist(str1, str2)
        self.add(key, dist)

    @property
    def distance(self):
        """Returns a weighted and normalised distance across all penalties.
        """
        dist_max = self.max_distance
        if dist_max:
            return self.raw_distance / self.max_distance
        return 0.0

    @property
    def max_distance(self):
        """Returns the maximum distance penalty.
        """
        dist_max = 0.0
        for key, penalty in self._penalties.iteritems():
            dist_max += len(penalty) * weights[key].as_number()
        return dist_max

    @property
    def raw_distance(self):
        """Returns the raw (denormalised) distance.
        """
        dist_raw = 0.0
        for key, penalty in self._penalties.iteritems():
            dist_raw += sum(penalty) * weights[key].as_number()
        return dist_raw

    @property
    def sorted(self):
        """Returns a list of (dist, key) pairs, with `dist` being the weighted
        distance, sorted from highest to lowest. Does not include penalties
        with a zero value.
        """
        list_ = []
        for key in self._penalties:
            dist = self[key]
            if dist:
                list_.append((dist, key))
        # Convert distance into a negative float we can sort items in ascending
        # order (for keys, when the penalty is equal) and still get the items
        # with the biggest distance first.
        return sorted(list_, key=lambda (dist, key): (0-dist, key))

    def update(self, dist):
        """Adds all the distance penalties from `dist`.
        """
        if not isinstance(dist, Distance):
            raise ValueError(
                    '`dist` must be a Distance object. It is: %r' % dist)
        for key, penalties in dist._penalties.iteritems():
            self._penalties.setdefault(key, []).extend(penalties)

def track_distance(item, track_info, incl_artist=False):
    """Determines the significance of a track metadata change. Returns a
    Distance object. `incl_artist` indicates that a distance component should
    be included for the track artist (i.e., for various-artist releases).
    """
    dist = Distance()

    # Length.
    if track_info.length:
        diff = abs(item.length - track_info.length) - \
               weights['track_length_grace'].as_number()
        dist.add_ratio('track_length', diff,
                       weights['track_length_max'].as_number())

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

    dist = Distance()

    # Artist, if not various.
    if not album_info.va:
        dist.add_string('artist', likelies['artist'], album_info.artist)

    # Album.
    dist.add_string('album', likelies['album'], album_info.album)

    # Preferred media.
    patterns = config['match']['preferred']['media'].as_str_seq()
    options = [re.compile(r'(\d+x)?(%s)' % pat, re.I) for pat in patterns]
    if album_info.media and options:
        dist.add_priority('media', album_info.media, options)
    # Media.
    elif likelies['media'] and album_info.media:
        dist.add_string('media', likelies['media'], album_info.media)

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
    keys = set(key for _, key in min_dist)
    if isinstance(results[0], hooks.AlbumMatch):
        for track_dist in min_dist.tracks.values():
            keys.update(key for _, key in track_dist)
    for key in keys:
        max_rec = config['match']['max_rec'][key].as_choice({
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
