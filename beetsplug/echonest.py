# This file is part of beets.
import time
import logging
import socket
import math

from beets import util, config, plugins, ui, library
import pyechonest
import pyechonest.song
import pyechonest.track

log = logging.getLogger('beets')

# If a request at the EchoNest fails, we want to retry the request RETRIES
# times and wait between retries for RETRY_INTERVAL seconds.
RETRIES = 10
RETRY_INTERVAL = 10

# for converting files
import os
import tempfile
from string import Template
from subprocess import Popen
DEVNULL = open(os.devnull, 'wb')

# The attributes we can import and where to store them
# Note:  We use echonest_id (song_id) and echonest_fingerprint to speed up
# lookups.  They are not listed as attributes here.
ATTRIBUTES = {
        'energy'        : 'energy',
        'liveness'      : 'liveness',
        'speechiness'   : 'speechiness',
        'acousticness'  : 'acousticness',
        'danceability'  : 'danceability',
        'valence'       : 'valence',
        'tempo'         : 'bpm',
    }

def _splitstrip(string):
    """Split string at comma and return the stripped values as array."""
    return [ s.strip() for s in string.split(u',') ]

class EchonestMetadataPlugin(plugins.BeetsPlugin):
    _songs = {}
    _attributes = []
    _no_mapping = []

    def __init__(self):
        super(EchonestMetadataPlugin, self).__init__()
        self.config.add({
                'auto'          : True,
                'apikey'        : u'NY2KTZHQ0QDSHBAP6',
                'codegen'       : None,
                'upload'        : True,
                'convert'       : True,
            })
        for k, v in ATTRIBUTES.iteritems():
            self.config.add({k:v})

        pyechonest.config.ECHO_NEST_API_KEY = \
            config['echonest']['apikey'].get(unicode)

        if config['echonest']['codegen'].get() is not None:
            pyechonest.config.CODEGEN_BINARY_OVERRIDE = \
                config['echonest']['codegen'].get(unicode)

        self.register_listener('import_task_start', self.fetch_song_task)
        self.register_listener('import_task_apply', self.apply_metadata_task)

    def _echofun(self, func, **kwargs):
        """Wrapper for requests to the EchoNest API.  Will retry up to RETRIES
        times and wait between retries for RETRY_INTERVAL seconds.
        """
        for i in range(RETRIES):
            try:
                result = func(**kwargs)
            except pyechonest.util.EchoNestAPIError as e:
                if e.code == 3:
                    # reached access limit per minute
                    time.sleep(RETRY_INTERVAL)
                elif e.code == 5:
                    # specified identifier does not exist
                    # no use in trying again.
                    log.debug(u'echonest: {}'.format(e))
                    return None
                else:
                    log.error(u'echonest: {0}'.format(e.args[0][0]))
                    return None
            except (pyechonest.util.EchoNestIOError, socket.error) as e:
                log.warn(u'echonest: IO error: {0}'.format(e))
                time.sleep(RETRY_INTERVAL)
            else:
                break
        else:
            # If we exited the loop without breaking, then we used up all
            # our allotted retries.
            raise Exception(u'exceeded retries')
            return None
        return result

    def fingerprint(self, item):
        """Get the fingerprint for this item from the EchoNest.  If we already
        have a fingerprint, return it and don't calculate it again.
        """
        if item.get('echonest_fingerprint', None) is None:
            try:
                code = self._echofun(pyechonest.util.codegen, filename=item.path.decode('utf-8'))
                item['echonest_fingerprint'] = code[0]['code']
                item.write()
            except Exception as exc:
                log.error(u'echonest: fingerprinting failed: {0}'
                        .format(str(exc)))
                return None
        return item.get('echonest_fingerprint')

    def convert(self, item):
        """Converts an item in an unsupported media format to ogg.  Config
        pending.
        This is stolen from Jakob Schnitzers convert plugin.
        """
        fd, dest = tempfile.mkstemp(u'.ogg')
        os.close(fd)
        source = item.path
        # FIXME: use avconv?
        command = u'ffmpeg -i $source -y -acodec libvorbis -vn -aq 2 $dest'.split(u' ')
        log.info(u'echonest: encoding {0} to {1}'
                .format(util.displayable_path(source),
                util.displayable_path(dest)))
        opts = []
        for arg in command:
            arg = arg.encode('utf-8')
            opts.append(Template(arg).substitute({
                'source':   source,
                'dest':     dest
            }))

        try:
            encode = Popen(opts, close_fds=True, stderr=DEVNULL)
            encode.wait()
        except Exception as exc:
            log.error(u'echonest: encode failed: {0}'.format(str(exc)))
            util.remove(dest)
            util.prune_dirs(os.path.dirname(dest))
            return None

        if encode.returncode != 0:
            log.info(u'echonest: encoding {0} failed ({1}). Cleaning up...'
                     .format(util.displayable_path(source), encode.returncode))
            util.remove(dest)
            util.prune_dirs(os.path.dirname(dest))
            return None
        log.info(u'Finished encoding {0}'.format(util.displayable_path(source)))
        return dest

    def analyze(self, item):
        """Upload the item to the EchoNest for analysis.  May require to
        convert the item to a supported media format.
        """
        try:
            source = item.path
            if item.format.lower() not in ['wav', 'mp3', 'au', 'ogg', 'mp4', 'm4a']:
                if not config['echonest']['convert'].get(bool):
                    raise Exception(u'format {} not supported for upload'
                            .format(item.format))
                else:
                    source = self.convert(item)
                    if source is None:
                        raise Exception(u'failed to convert file'
                                .format(item.format))
            log.info(u'echonest: uploading file, be patient')
            track = self._echofun(pyechonest.track.track_from_filename,
                    filename=source)
            if track is None:
                raise Exception(u'failed to upload file')

            # Sometimes we have a track but no song.  I guess this happens for
            # new / unverified songs.  We need to 'extract' the audio_summary
            # from the track object 'manually'.  I don't know why the
            # pyechonest API handles tracks (merge audio_summary to __dict__)
            # and songs (keep audio_summary in an extra attribute)
            # differently.
            # Maybe a patch for pyechonest could help?
            from_track = {}
            from_track['energy'] = track.energy
            from_track['liveness'] = track.liveness
            from_track['speechiness'] = track.speechiness
            from_track['acousticness'] = track.acousticness
            from_track['danceability'] = track.danceability
            from_track['valence'] = track.valence
            from_track['tempo'] = track.tempo
            from_track['duration'] = track.duration
            ids = []
            try:
                ids = [track.song_id]
            except Exception:
                return from_track
            songs = self._echofun(pyechonest.song.profile,
                    ids=ids, track_ids=[track.id],
                    buckets=['audio_summary'])
            if songs is None:
                raise Exception(u'failed to retrieve info from upload')
            pick = self._pick_song(songs, item)
            if pick is None:
                return from_track
            return pick
        except Exception as exc:
            log.error(u'echonest: analysis failed: {0}'.format(str(exc)))
            return None

    def identify(self, item):
        """Try to identify the song at the EchoNest.
        """
        try:
            code = self.fingerprint(item)
            if code is None:
                raise Exception(u'can not identify without a fingerprint')
            songs = self._echofun(pyechonest.song.identify, code=code)
            if not songs:
                raise Exception(u'no songs found')
            return max(songs, key=lambda s: s.score)
        except Exception as exc:
            log.error(u'echonest: identification failed: {0}'.format(str(exc)))
            return None

    def _pick_song(self, songs, item):
        """Helper method to pick the best matching song from a list of songs
        returned by the EchoNest.  Compares artist, title and duration.  If
        the artist and title match and the duration difference is <= 1.0
        seconds, it's considered a match.
        """
        pick = None
        if songs:
            min_dist = item.length
            for song in songs:
                if song.artist_name.lower() == item.artist.lower() \
                        and song.title.lower() == item.title.lower():
                    dist = abs(item.length - song.audio_summary['duration'])
                    if dist < min_dist:
                        min_dist = dist
                        pick = song
            if min_dist > 2.5:
                return None
        return pick

    def search(self, item):
        """Search the item at the EchoNest by artist and title.
        """
        try:
            songs = self._echofun(pyechonest.song.search, title=item.title,
                    results=100, artist=item.artist,
                    buckets=['id:musicbrainz', 'tracks'])
            pick = self._pick_song(songs, item)
            if pick is None:
                raise Exception(u'no (matching) songs found')
            return pick
        except Exception as exc:
            log.error(u'echonest: search failed: {0}'.format(str(exc)))
            return None

    def profile(self, item):
        """Do a lookup on the EchoNest by MusicBrainz ID.
        """
        try:
            if item.get('echonest_id', None) is None:
                if not item.mb_trackid:
                    raise Exception(u'musicbrainz ID not available')
                mbid = 'musicbrainz:track:{0}'.format(item.mb_trackid)
                track = self._echofun(pyechonest.track.track_from_id, identifier=mbid)
                if not track:
                    raise Exception(u'could not get track from ID')
                ids = track.song_id
            else:
                ids = item.get('echonest_id')
            songs = self._echofun(pyechonest.song.profile, ids=ids,
                    buckets=['id:musicbrainz', 'audio_summary'])
            if not songs:
                raise Exception(u'could not get songs from track ID')
            return self._pick_song(songs, item)
        except Exception as exc:
            log.debug(u'echonest: profile failed: {0}'.format(str(exc)))
            return None

    def fetch_song(self, item):
        """Try all methods, to get a matching song object from the EchoNest.
        """
        methods = [self.profile, self.search]
        if config['echonest']['codegen'].get() is not None:
            methods.append(self.identify)
        if config['echonest']['upload'].get(bool):
            methods.append(self.analyze)
        for method in methods:
            try:
                song = method(item)
                if not song is None:
                    if isinstance(song, pyechonest.song.Song):
                        log.debug(u'echonest: got song through {0}: {1} - {2} [{3}]'
                                  .format(method.im_func.func_name,
                                  song.artist_name, song.title,
                                  song.audio_summary['duration']))
                    else: # it's our dict filled from a track object
                        log.debug(u'echonest: got song through {0}: {1} - {2} [{3}]'
                                  .format(method.im_func.func_name,
                                  item.artist, item.title,
                                  song['duration']))
                    return song
            except Exception as exc:
                log.debug(u'echonest: profile failed: {0}'.format(str(exc)))
        return None

    def apply_metadata(self, item):
        """Copy the metadata from the EchoNest to the item.
        """
        if item.path in self._songs:
            # song can be a dict
            if isinstance(self._songs[item.path], pyechonest.song.Song):
                log.debug(u'echonest: metadata: echonest_id = {0}'
                        .format(self._songs[item.path].id))
                item.echonest_id = self._songs[item.path].id
                values = self._songs[item.path].audio_summary
            else:
                values = self._songs[item.path]
            for k, v in values.iteritems():
                if ATTRIBUTES.has_key(k) and ATTRIBUTES[k] is not None:
                    log.debug(u'echonest: metadata: {0} = {1}'
                            .format(ATTRIBUTES[k], v))
                    item[ATTRIBUTES[k]] = v
            if config['import']['write'].get(bool):
                log.info(u'echonest: writing metadata: {0}'
                         .format(util.displayable_path(item.path)))
                item.write()
                if item._lib:
                    item.store()
        else:
            log.warn(u'echonest: no metadata available')

    def requires_update(self, item):
        """Check if this item requires an update from the EchoNest aka data is
        missing.
        """
        for k, v in ATTRIBUTES.iteritems():
            if v is None:
                continue
            if item.get(v, None) is None:
                return True
        log.info(u'echonest: no update required')
        return False

    def fetch_song_task(self, task, session):
        items = task.items if task.is_album else [task.item]
        for item in items:
            song = self.fetch_song(item)
            if not song is None:
                self._songs[item.path] = song

    def apply_metadata_task(self, task, session):
        for item in task.imported_items():
            self.apply_metadata(item)

    def commands(self):
        cmd = ui.Subcommand('echonest',
            help='Fetch metadata from the EchoNest')
        cmd.parser.add_option('-f', '--force', dest='force',
            action='store_true', default=False,
            help='(re-)download information from the EchoNest')

        def func(lib, opts, args):
            self.config.set_args(opts)
            for item in lib.items(ui.decargs(args)):
                log.info(u'echonest: {0} - {1} [{2}]'.format(item.artist,
                        item.title, item.length))
                if self.config['force'] or self.requires_update(item):
                    song = self.fetch_song(item)
                    if not song is None:
                        self._songs[item.path] = song
                    self.apply_metadata(item)

        cmd.func = func
        return [cmd]

def diff(item1, item2, attributes):
    result = 0.0
    for attr in attributes:
        try:
            result += abs(
                    float(item1.get(attr, None)) -
                    float(item2.get(attr, None))
                    )
        except TypeError:
            result += 1.0
    return result

def similar(lib, src_item, threshold=0.15):
    attributes = []
    for attr in ['energy', 'danceability', 'valence', 'speechiness',
                 'acousticness', 'liveness']:
        if ATTRIBUTES[attr] is not None:
            attributes.append(ATTRIBUTES[attr])
    for item in lib.items():
        if not item.path == src_item.path:
            d = diff(item, src_item, attributes)
            if d < threshold:
                print(u'{1:2.2f}: {0}'.format(item.path, d))

class EchonestSimilarPlugin(plugins.BeetsPlugin):
    def commands(self):
        cmd = ui.Subcommand('echosim', help='show related files')

        def func(lib, opts, args):
            self.config.set_args(opts)
            for item in lib.items(ui.decargs(args)):
                similar(lib, item)

        cmd.func = func
        return [cmd]

# eof
