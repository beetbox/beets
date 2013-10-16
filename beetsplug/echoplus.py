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

# Global logger.
log = logging.getLogger('beets')

RETRY_INTERVAL = 10  # Seconds.
RETRIES = 10
ATTRIBUTES = ['energy', 'liveness', 'speechiness', 'acousticness',
    'danceability', 'valence', 'tempo' ]
ATTRIBUTES_WITH_STYLE = ['energy', 'liveness', 'speechiness', 'acousticness',
    'danceability', 'valence' ]

def _apply_style(style, custom, value):
    if style == 'raw':
        return value
    mapping = None
    if style == 'custom':
        mapping = [ m.strip() for m in custom.split(',') ]
    elif style == '1to5':
        mapping = [1, 2, 3, 4, 5]
    elif style == 'hr5': # human readable
        mapping = ['very low', 'low', 'neutral', 'high', 'very high']
    elif style == 'hr3': # human readable
        mapping = ['low', 'neutral', 'high']
    if mapping is None:
        log.error(u'Unsupported style setting: {}'.format(style))
        return value
    inc = 1.0 / len(mapping)
    cut = 0.0
    for i in range(len(mapping)):
      cut += inc
      if value < cut:
        return mapping[i]
    return mapping[i]

def _guess_mood(valence, energy):
    # for an explanation see:
    # http://developer.echonest.com/forums/thread/1297
    # i picked a Valence-Arousal space from here:
    # http://mat.ucsb.edu/~ivana/200a/background.htm

    # energy from 0.0 to 1.0.  valence < 0.5
    low_valence = [
        'fatigued', 'lethargic', 'depressed', 'sad',
        'upset', 'stressed', 'nervous', 'tense' ]
    # energy from 0.0 to 1.0.  valence > 0.5
    high_valence = [
        'calm', 'relaxed', 'serene', 'contented',
        'happy', 'elated', 'excited', 'alert' ]
    if valence < 0.5:
        mapping = low_valence
    else:
        mapping = high_valence
    inc = 1.0 / len(mapping)
    cut = 0.0
    for i in range(len(mapping)):
        cut += inc
        if energy < cut:
            return mapping[i]
    return mapping[i]


def fetch_item_attributes(lib, loglevel, item, write, force):
    """Fetch and store tempo for a single item. If ``write``, then the
    tempo will also be written to the file itself in the bpm field. The
    ``loglevel`` parameter controls the visibility of the function's
    status log messages.
    """
    # Check if we need to update
    guess_mood = config['echoplus']['guess_mood'].get(bool)
    allow_upload = config['echoplus']['upload'].get(bool)
    if force:
        require_update = True
    else:
        require_update = False
        for attr in ATTRIBUTES:
            if config['echoplus'][attr].get(str) == '':
                continue
            if item.get(attr, None) is None:
                require_update = True
                break
        if not require_update and guess_mood:
            if item.get('mood', None) is None:
                require_update = True
    if not require_update:
        log.log(loglevel, u'no update required for: {} - {}'.format(
            item.artist, item.title))
        return
    audio_summary = get_audio_summary(item.artist, item.title, item.length,
        allow_upload, item.path)
    global_style = config['echoplus']['style'].get()
    global_custom_style = config['echoplus']['custom_style'].get()
    if audio_summary:
        changed = False
        if guess_mood:
            attr = 'mood'
            if item.get(attr, None) is not None and not force:
                log.log(loglevel, u'{} already present, use the force Luke: {} - {} = {}'.format(
                    attr, item.artist, item.title, item.get(attr)))
            else:
                if 'valence' in audio_summary and 'energy' in audio_summary:
                    item[attr] = _guess_mood(audio_summary['valence'],
                        audio_summary['energy'])
                    changed = True
        for attr in ATTRIBUTES:
            if config['echoplus'][attr].get(str) == '':
                continue
            if item.get(attr, None) is not None and not force:
                log.log(loglevel, u'{} already present: {} - {} = {}'.format(
                    attr, item.artist, item.title, item.get(attr)))
            else:
                if not attr in audio_summary or audio_summary[attr] is None:
                    log.log(loglevel, u'{} not found: {} - {}'.format(
                        attr, item.artist, item.title))
                else:
                    log.debug(u'fetched {}: {} - {} = {}'.format(
                        attr, item.artist, item.title, audio_summary[attr]))
                    value = float(audio_summary[attr])
                    if attr in ATTRIBUTES_WITH_STYLE:
                        style = config['echoplus']['{}_style'.format(attr)].get()
                        custom_style = config['echoplus']['{}_custom_style'.format(attr)].get()
                        if style is None:
                            style = global_style
                        if custom_style is None:
                            custom_style = global_custom_style
                        value = _apply_style(style, custom_style, value)
                        log.debug(u'mapped {}: {} - {} = {}'.format(
                            attr, item.artist, item.title, value))
                    item[attr] = value
                    changed = True
        if changed:
            if write:
                item.write()
            item.store()


def get_audio_summary(artist, title, duration, upload, path):
    """Get the attribute for a song."""
    # We must have sufficient metadata for the lookup. Otherwise the API
    # will just complain.
    artist = artist.replace(u'\n', u' ').strip().lower()
    title = title.replace(u'\n', u' ').strip().lower()
    if not artist or not title:
        return None

    for i in range(RETRIES):
        try:
            # Unfortunately, all we can do is search by artist and title.
            # EchoNest supports foreign ids from MusicBrainz, but currently
            # only for artists, not individual tracks/recordings.
            results = pyechonest.song.search(
                artist=artist, title=title, results=100,
                buckets=['audio_summary']
            )
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

    # The Echo Nest API can return songs that are not perfect matches.
    # So we look through the results for songs that have the right
    # artist and title. The API also doesn't have MusicBrainz track IDs;
    # otherwise we could use those for a more robust match.
    min_distance = duration
    pick = None
    for result in results:
        distance = abs(duration - result.audio_summary['duration'])
        log.debug(
            u'echoplus: candidate {} - {} [dist({:2.2f}-{:2.2f})={:2.2f}]'.format(
                result.artist_name, result.title,
                result.audio_summary['duration'], duration, distance))
        if distance < min_distance:
            min_distance = distance
            pick = result
    log.debug(
        u'echoplus: picked {} - {} [dist({:2.2f}-{:2.2f})={:2.2f}] = {}'.format(
            pick.artist_name, pick.title,
            pick.audio_summary['duration'], duration, min_distance,
            pick.audio_summary))
    if min_distance > 1.0 and upload:
        log.debug(u'uploading file to EchoNest')
        t = pyechonest.track.track_from_filename(path)
        if t:
            log.debug(u'{} - {} [{:2.2f}]'.format(t.artist, t.title,
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
        else:
            log.debug(u'upload did not return a result')
    return pick.audio_summary


class EchoPlusPlugin(BeetsPlugin):
    def __init__(self):
        super(EchoPlusPlugin, self).__init__()
        self.import_stages = [self.imported]
        self.config.add({
            'apikey': u'NY2KTZHQ0QDSHBAP6',
            'auto': True,
            'style': 'hr5',
            'custom_style': None,
            'force': False,
            'printinfo': True,
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
                '{}_style'.format(attr):None,
                '{}_custom_style'.format(attr):None,
            })

        pyechonest.config.ECHO_NEST_API_KEY = \
                self.config['apikey'].get(unicode)

    def commands(self):
        cmd = ui.Subcommand('echoplus',
            help='fetch additional song information from the echonest')
        cmd.parser.add_option('-p', '--print', dest='printinfo',
            action='store_true', default=False,
            help='print fetched information to console')
        cmd.parser.add_option('-f', '--force', dest='force',
            action='store_true', default=False,
            help='re-download information from the EchoNest')
        def func(lib, opts, args):
            # The "write to files" option corresponds to the
            # import_write config value.
            write = config['import']['write'].get(bool)
            self.config.set_args(opts)

            for item in lib.items(ui.decargs(args)):
                fetch_item_attributes(lib, logging.INFO, item, write,
                    self.config['force'])
                if opts.printinfo:
                    attrs = [ a for a in ATTRIBUTES ]
                    if config['echoplus']['guess_mood'].get(bool):
                        attrs.append('mood')
                    d = []
                    for attr in attrs:
                        if item.get(attr, None) is not None:
                            d.append(u'{}={}'.format(attr, item.get(attr)))
                    s = u', '.join(d)
                    if s == u'':
                      s = u'no information received'
                    ui.print_(u'{}: {}'.format(item.path, s))
        cmd.func = func
        return [cmd]

    # Auto-fetch tempo on import.
    def imported(self, config, task):
        if self.config['auto']:
            for item in task.imported_items():
                fetch_item_attributes(config.lib, logging.DEBUG, item, False,
                    self.config['force'])

# eof
