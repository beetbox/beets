# This file is part of beets.
# Copyright 2013, Peter Schnebel <pschnebel.a.gmail>
#
# Original 'echonest_tempo' plugin is copyright 2013, David Brenner
# <david.a.brenner gmail>
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

"""Gets additional information for imported music from the EchoNest API. Requires
version >= 8.0.1 of the pyechonest library (https://github.com/echonest/pyechonest).
"""
import time
import logging
from beets.plugins import BeetsPlugin
from beets import ui
from beets import config
import pyechonest.config
import pyechonest.song
import pyechonest.track
import socket
import math

# Global logger.
log = logging.getLogger('beets')

RETRY_INTERVAL = 10  # Seconds.
RETRIES = 10
ATTRIBUTES = ['energy', 'liveness', 'speechiness', 'acousticness',
    'danceability', 'valence', 'tempo', 'mood' ]
MAPPED_ATTRIBUTES = ['energy', 'liveness', 'speechiness', 'acousticness',
    'danceability', 'valence', 'mood' ]

PI_2 = math.pi / 2.0
MAX_LEN = math.sqrt(2.0 * 0.5 * 0.5)

def _picker(value, rang, mapping):
    inc = rang / len(mapping)
    i = 0.0
    for m in mapping:
      i += inc
      if value < i:
        return m
    return m # in case of floating point precision problems

def _mapping(mapstr):
    """Split mapstr at comma and returned the stripped values as array."""
    return [ m.strip() for m in mapstr.split(u',') ]

def _guess_mood(valence, energy):
    """Based on the valence [0.0 .. 1.0]and energy [0.0 .. 1.0] of a song, we
    try to guess the mood.

    For an explanation see:
        http://developer.echonest.com/forums/thread/1297

    We use the Valence-Arousal space from here:
        http://mat.ucsb.edu/~ivana/200a/background.htm
    """

    # move center to 0.0/0.0
    valence -= 0.5
    energy -= 0.5

    # we use the length of the valence / energy vector to determine the
    # strength of the emotion
    length = math.sqrt(valence * valence + energy * energy)

    # FIXME: do we want the next 3 as config options?
    strength = [u'slightly', u'', u'very' ]
    # energy from -0.5 to 0.5,  valence < 0.0
    low_valence = [
            u'fatigued', u'lethargic', u'depressed', u'sad',
            u'upset', u'stressed', u'nervous', u'tense' ]
    # energy from -0.5 to 0.5,  valence >= 0.0
    high_valence = [
            u'calm', u'relaxed', u'serene', u'contented',
            u'happy', u'elated', u'excited', u'alert' ]
    if length == 0.0:
        # FIXME: what now?  return a fallback?  config?
        return u'neutral'

    angle = math.asin(energy / length) + PI_2
    if valence < 0.0:
        moods = low_valence
    else:
        moods = high_valence
    mood = _picker(angle, math.pi, moods)
    strength = _picker(length, MAX_LEN, strength)
    if strength == u'':
      return mood
    return u'{} {}'.format(strength, mood)

def fetch_item_attributes(lib, item, write, force, re_apply):
    """Fetches audio_summary from the EchoNest and writes it to item.
    """

    log.debug(u'echoplus: {} - {} [{}] force:{} re_apply:{}'.format(
        item.artist, item.title, item.length, force, re_apply))
    # permanently store the raw values?
    store_raw = config['echoplus']['store_raw'].get(bool)

    # if we want to set mood, we need to make sure, that valence and energy
    # are imported
    if config['echoplus']['mood'].get(str):
        if config['echoplus']['valence'].get(str) == '':
            log.warn(u'echoplus: "valence" is required to guess the mood')
            config['echoplus']['mood'].set('') # disable mood

        if config['echoplus']['energy'].get(str) == '':
            log.warn(u'echoplus: "energy" is required to guess the mood')
            config['echoplus']['mood'].set('') # disable mood

    # force implies re_apply
    if force:
        re_apply = True

    allow_upload = config['echoplus']['upload'].get(bool)
    # the EchoNest only supports these file formats
    if allow_upload and \
          item.format.lower() not in ['wav', 'mp3', 'au', 'ogg', 'mp4', 'm4a']:
        log.warn(u'echoplus: format {} not supported for upload'.format(item.format))
        allow_upload = False

    # Check if we need to update
    need_update = False
    if force:
        need_update = True
    else:
        need_update = False
        for attr in ATTRIBUTES:
            # do we want this attribute?
            target = config['echoplus'][attr].get(str)
            if target == '':
                continue

             # check if the raw values are present.  'mood' has no direct raw
             # representation and 'tempo' is stored raw anyway
            if (store_raw or re_apply) and not attr in ['mood', 'tempo']:
                target = '{}_raw'.format(target)

            if item.get(target, None) is None:
                need_update = True
                break

    if need_update:
        log.debug(u'echoplus: fetching data')
        re_apply = True

        # (re-)fetch audio_summary and store it to the raw values.  if we do
        # not want to keep the raw values, we clean them up later

        audio_summary = get_audio_summary(item.artist, item.title,
                item.length, allow_upload, item.path)
        changed = False
        if not audio_summary:
            return None
        else:
            for attr in ATTRIBUTES:
                if attr == 'mood': # no raw representation
                    continue

                # do we want this attribute?
                target = config['echoplus'][attr].get(str)
                if target == '':
                    continue
                if attr != 'tempo':
                    target = '{}_raw'.format(target)

                if item.get(target, None) is not None and not force:
                    log.info(u'{} already present: {} - {} = {:2.2f}'.format(
                            attr, item.artist, item.title, item.get(target)))
                else:
                    if not attr in audio_summary or audio_summary[attr] is None:
                        log.info(u'{} not found: {} - {}'.format( attr,
                                item.artist, item.title))
                    else:
                        value = float(audio_summary[attr])
                        item[target] = float(audio_summary[attr])
                        changed = True
    if re_apply:
        log.debug(u'echoplus: reapplying data')
        global_mapping = _mapping(config['echoplus']['mapping'].get())
        for attr in ATTRIBUTES:
            # do we want this attribute?
            target = config['echoplus'][attr].get(str)
            if target == '':
                continue
            if attr == 'mood':
                # we validated above, that valence and energy are
                # included, so this should not fail
                valence = \
                    float(item.get('{}_raw'.format(config['echoplus']['valence'].get(str))))
                energy = \
                    float(item.get('{}_raw'.format(config['echoplus']['energy'].get(str))))
                item[target] = _guess_mood(valence, energy)
                log.debug(u'echoplus: mapped {}: {:2.2f}x{:2.2f} = {}'.format(
                        attr, valence, energy, item[target]))
                changed = True
            elif attr in MAPPED_ATTRIBUTES:
                mapping = global_mapping
                map_str = config['echoplus']['{}_mapping'.format(attr)].get()
                if map_str is not None:
                    mapping = _mapping(map_str)
                value = float(item.get('{}_raw'.format(target)))
                mapped_value = _picker(value, 1.0, mapping)
                log.debug(u'echoplus: mapped {}: {:2.2f} > {}'.format(
                    attr, value, mapped_value))
                item[attr] = mapped_value
                changed = True

        if changed:
            if write:
                item.write()
            item.store()

def _echonest_fun(function, **kwargs):
    for i in range(RETRIES):
        try:
            # Unfortunately, all we can do is search by artist and title.
            # EchoNest supports foreign ids from MusicBrainz, but currently
            # only for artists, not individual tracks/recordings.
            results = function(**kwargs)
        except pyechonest.util.EchoNestAPIError as e:
            if e.code == 3:
                # Wait and try again.
                time.sleep(RETRY_INTERVAL)
            else:
                log.warn(u'echoplus: {0}'.format(e.args[0][0]))
                return None
        except (pyechonest.util.EchoNestIOError, socket.error) as e:
            log.debug(u'echoplus: IO error: {0}'.format(e))
            time.sleep(RETRY_INTERVAL)
        else:
            break
    else:
        # If we exited the loop without breaking, then we used up all
        # our allotted retries.
        log.debug(u'echoplus: exceeded retries')
        return None
    return results

def get_audio_summary(artist, title, duration, upload, path):
    """Get the attribute for a song."""
    # We must have sufficient metadata for the lookup. Otherwise the API
    # will just complain.
    artist = artist.replace(u'\n', u' ').strip().lower()
    title = title.replace(u'\n', u' ').strip().lower()
    if not artist or not title:
        return None

    results = _echonest_fun(pyechonest.song.search,
                artist=artist, title=title, results=100,
                buckets=['audio_summary'])
    pick = None
    min_distance = duration
    if results:
        # The Echo Nest API can return songs that are not perfect matches.
        # So we look through the results for songs that have the right
        # artist and title. The API also doesn't have MusicBrainz track IDs;
        # otherwise we could use those for a more robust match.
        for result in results:
            if result.artist_name.lower() == artist \
                  and result.title.lower() == title:
                distance = abs(duration - result.audio_summary['duration'])
                log.debug(
                    u'echoplus: candidate {} - {} [dist({:2.2f})={:2.2f}]'.format(
                        result.artist_name, result.title,
                        result.audio_summary['duration'], distance))
                if distance < min_distance:
                    min_distance = distance
                    pick = result
        if pick:
            log.debug(
                u'echoplus: picked {} - {} [dist({:2.2f}-{:2.2f})={:2.2f}]'.format(
                    pick.artist_name, pick.title,
                    pick.audio_summary['duration'], duration, min_distance))

    if (not pick or min_distance > 1.0) and upload:
        log.debug(u'echoplus: uploading file "{}" to EchoNest'.format(path))
        # FIXME: same loop as above...  make this better
        for i in range(RETRIES):
            t = _echonest_fun(pyechonest.track.track_from_filename, filename=path)
            if t:
                log.debug(u'echoplus: track {} - {} [{:2.2f}]'.format(t.artist, t.title,
                    t.duration))
                # FIXME:  maybe make pyechonest "nicer"?
                result = {}
                result['energy'] = t.energy
                result['liveness'] = t.liveness
                result['speechiness'] = t.speechiness
                result['acousticness'] = t.acousticness
                result['danceability'] = t.danceability
                result['valence'] = t.valence
                result['tempo'] = t.tempo
                return result
    elif not pick:
        return None
    return pick.audio_summary


class EchoPlusPlugin(BeetsPlugin):
    def __init__(self):
        super(EchoPlusPlugin, self).__init__()
        self.import_stages = [self.imported]
        self.config.add({
            'apikey': u'NY2KTZHQ0QDSHBAP6',
            'auto': True,
            'mapping': 'very low,low,neutral,high,very high',
            'store_raw': True,
            'guess_mood': False,
            'upload': False,
        })
        for attr in ATTRIBUTES:
          if attr == 'tempo':
            target = 'bpm'
            self.config.add({attr:target})
          else:
            target = attr
            self.config.add({attr:target,
                '{}_mapping'.format(attr): None,
            })

        pyechonest.config.ECHO_NEST_API_KEY = \
                self.config['apikey'].get(unicode)

    def commands(self):
        cmd = ui.Subcommand('echoplus',
            help='fetch additional song information from the echonest')
        cmd.parser.add_option('-f', '--force', dest='force',
            action='store_true', default=False,
            help='re-download information from the EchoNest')
        cmd.parser.add_option('-r', '--re_apply', dest='re_apply',
            action='store_true', default=False,
            help='re_apply mappings')
        def func(lib, opts, args):
            # The "write to files" option corresponds to the
            # import_write config value.
            write = config['import']['write'].get(bool)
            self.config.set_args(opts)

            for item in lib.items(ui.decargs(args)):
                log.debug(u'{} {}'.format(
                    self.config['force'],
                    self.config['re_apply']))
                fetch_item_attributes(lib, item, write,
                    self.config['force'],
                    self.config['re_apply'])
        cmd.func = func
        return [cmd]

    # Auto-fetch info on import.
    def imported(self, session, task):
        if self.config['auto']:
            if task.is_album:
                album = session.lib.get_album(task.album_id)
                for item in album.items():
                    fetch_item_attributes(session.lib, item, False, True,
                        True)
            else:
                item = task.item
                fetch_item_attributes(session.lib, item, False, True, True)

# eof
