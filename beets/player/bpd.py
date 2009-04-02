#!/usr/bin/env python

"""A clone of the Music Player Daemon (MPD) that plays music from a
Beets library. Attempts to implement a compatible protocol to allow
use of the wide range of MPD clients.
"""

import eventlet.api
import re
from string import Template
import beets
import traceback
import logging
import time


DEFAULT_PORT = 6600
PROTOCOL_VERSION = '0.13.0'
BUFSIZE = 1024

HELLO = 'OK MPD %s' % PROTOCOL_VERSION
CLIST_BEGIN = 'command_list_begin'
CLIST_VERBOSE_BEGIN = 'command_list_ok_begin'
CLIST_END = 'command_list_end'
RESP_OK = 'OK'
RESP_CLIST_VERBOSE = 'list_OK'
RESP_ERR = 'ACK'

NEWLINE = "\n"

ERROR_NOT_LIST = 1
ERROR_ARG = 2
ERROR_PASSWORD = 3
ERROR_PERMISSION = 4
ERROR_UNKNOWN = 5
ERROR_NO_EXIST = 50
ERROR_PLAYLIST_MAX = 51
ERROR_SYSTEM = 52
ERROR_PLAYLIST_LOAD = 53
ERROR_UPDATE_ALREADY = 54
ERROR_PLAYER_SYNC = 55
ERROR_EXIST = 56

VOLUME_MIN = 0
VOLUME_MAX = 100


# Logger.
log = logging.getLogger('bpd')
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())


# Error-handling, exceptions, parameter parsing.

class BPDError(Exception):
    """An error that should be exposed to the client to the BPD
    server.
    """
    def __init__(self, code, message, cmd_name='', index=0):
        self.code = code
        self.message = message
        self.cmd_name = cmd_name
        self.index = index
        
    template = Template('$resp [$code@$index] {$cmd_name} $message')
    def response(self):
        """Returns a string to be used as the response code for the
        erring command.
        """
        return self.template.substitute({'resp':     RESP_ERR,
                                         'code':     self.code,
                                         'index':    self.index,
                                         'cmd_name': self.cmd_name,
                                         'message':  self.message
                                       })

def make_bpd_error(s_code, s_message):
    """Create a BPDError subclass for a static code and message.
    """
    class NewBPDError(BPDError):
        code = s_code
        message = s_message
        cmd_name = ''
        index = 0
        def __init__(self): pass
    return NewBPDError

ArgumentTypeError = make_bpd_error(ERROR_ARG, 'invalid type for argument')
ArgumentIndexError = make_bpd_error(ERROR_ARG, 'argument out of range')
ArgumentNotFoundError = make_bpd_error(ERROR_NO_EXIST, 'argument not found')

def cast_arg(t, val):
    """Attempts to call t on val, raising a CommandArgumentError
    on ValueError.
    
    If 't' is the special string 'intbool', attempts to cast first
    to an int and then to a bool (i.e., 1=True, 0=False).
    """
    if t == 'intbool':
        return cast_arg(bool, cast_arg(int, val))
    else:
        try:
            return t(val)
        except ValueError:
            raise CommandArgumentError()

class BPDClose(Exception):
    """Raised by a command invocation to indicate that the connection
    should be closed.
    """


# Path-like encoding of string sequences. We use this to simulate the
# directory structure required by the MPD protocol to browse music in
# the library.

def seq_to_path(seq):
    """Encodes a sequence of strings as a path-like string. The
    sequence can be recovered exactly using path_to_list.
    """
    
    out = []
    for s in seq:
        out.append(s.replace('\\', '\\\\').replace('/', '\\/'))
    return '/'.join(out)

path_to_list_pattern = re.compile(r'(?:\\/|[^/])*')
def path_to_list(path):
    """Takes a path-like string (probably encoded by seq_to_path) and
    returns the list of strings it represents.
    """
    
    # To simplify parsing, ensure that everything is terminated by a
    # slash. Note that seq_to_path never added a trailing slash, so
    # they are "disallowed" by this encoding.
    path += '/'
    
    out = []
    while path:
        
        # Search for one path component.
        m = path_to_list_pattern.match(path)
        if not m: break # Should never happen.
        component = m.group(0)
        
        # Chop off this component and the / that follows it.
        path = path[len(component):]
        if len(path) >= 1 and path[0] == '/': # Should always be true.
            path = path[1:]
        
        out.append(component.replace('\\/', '/').replace('\\\\', '\\'))
    
    return out


# Generic server infrastructure, implementing the basic protocol.

class BaseServer(object):
    """A MPD-compatible music player server.
    
    The generators with the `cmd_` prefix are invoked in response to
    client commands. For instance, if the client says `status`,
    `cmd_status` will be invoked. The arguments to the client's commands
    are used as function arguments (*args). The generators should yield
    strings or sequences of strings as many times as necessary.
    They may also raise BPDError exceptions to report errors.
    
    This is a generic superclass and doesn't support many commands.
    """
    
    def __init__(self, host='', port=DEFAULT_PORT):
        """Create a new server bound to address `host` and listening
        on port `port`.
        """
        self.host, self.port = host, port
        
        # Default server values.
        self.random = False
        self.repeat = False
        self.volume = VOLUME_MAX
        self.crossfade = 0
        self.playlist = []
        self.playlist_version = 0
        self.current_index = -1
        self.paused = False
    
    def run(self):
        """Block and start listening for connections from clients. An
        interrupt (^C) closes the server.
        """
        self.startup_time = time.time()
        try:
            self.listener = eventlet.api.tcp_listener((self.host, self.port))
            while True:
                sock, address = self.listener.accept()
                eventlet.api.spawn(Connection.handle, sock, self)
        except KeyboardInterrupt:
            pass # ^C ends the server.

    def _item_info(self, item):
        """An abstract method that should response lines containing a
        single song's metadata.
        """
        raise NotImplementedError
    
    def _item_id(self, item):
        """An abstract method returning the integer id for an item.
        """
        raise NotImplementedError

    def _id_to_index(self, track_id):
        """Searches the playlist for a song with the given id and
        returns its index in the playlist.
        """
        track_id = cast_arg(int, track_id)
        for index, track in enumerate(self.playlist):
            if self._item_id(track) == track_id:
                return index
        # Loop finished with no track found.
        raise ArgumentNotFoundError()

    def cmd_ping(self):
        """Succeeds."""
        pass
    
    def cmd_kill(self):
        """Exits the server process."""
        self.listener.close()
        exit(0)
    
    def cmd_close(self):
        """Closes the connection."""
        raise BPDClose()
    
    def cmd_commands(self):
        """Just lists the commands available to the user. For the time
        being, lists all commands because no authentication is present.
        """
        out = []
        for key in dir(self):
            if key.startswith('cmd_'):
                yield 'command: ' + key[4:]
    
    def cmd_notcommands(self):
        """Lists all unavailable commands. Because there's currently no
        authentication, returns no commands.
        """
        pass
    
    def cmd_status(self):
        """Returns some status information for use with an
        implementation of cmd_status.
        
        Gives a list of response-lines for: volume, repeat, random,
        playlist, playlistlength, and xfade.
        """
        yield ('volume: ' + str(self.volume),
               'repeat: ' + str(int(self.repeat)),
               'random: ' + str(int(self.random)),
               'playlist: ' + str(self.playlist_version),
               'playlistlength: ' + str(len(self.playlist)),
               'xfade: ' + str(self.crossfade),
              )
        
        if self.current_index == -1:
            state = 'stop'
        elif self.paused:
            state = 'pause'
        else:
            state = 'play'
        yield 'state: ' + state
        
        if self.current_index != -1: # i.e., paused or playing
            current_id = self._item_id(self.playlist[self.current_index])
            yield 'song: ' + str(self.current_index)
            yield 'songid: ' + str(current_id)
        
        #fixme Still missing: time, bitrate, audio, updating_db, error
    
    def cmd_random(self, state):
        """Set or unset random (shuffle) mode."""
        self.random = cast_arg('intbool', state)
    
    def cmd_repeat(self, state):
        """Set or unset repeat mode."""
        self.repeat = cast_arg('intbool', state)
    
    def cmd_setvol(self, vol):
        """Set the player's volume level (0-100)."""
        vol = cast_arg(int, vol)
        if vol < VOLUME_MIN or vol > VOLUME_MAX:
            raise BPDError(ERROR_ARG, 'volume out of range')
        self.volume = vol
    
    def cmd_crossfade(self, crossfade):
        """Set the number of seconds of crossfading."""
        crossfade = cast_arg(int, crossfade)
        if crossfade < 0:            
            raise BPDError(ERROR_ARG, 'crossfade time must be nonnegative')
    
    def cmd_clear(self):
        """Clear the playlist."""
        self.playlist = []
        self.playlist_version += 1
    
    def cmd_delete(self, index):
        """Remove the song at index from the playlist."""
        index = cast_arg(int, index)
        try:
            del(self.playlist[index])
        except IndexError:
            raise ArgumentIndexError()
        self.playlist_version += 1

        if self.current_index == index: # Deleted playing song.
            self.cmd_stop()
        elif index < self.current_index: # Deleted before playing.
            # Shift playing index down.
            self.current_index -= 1

    def cmd_deleteid(self, track_id):
        self.cmd_delete(self._id_to_index(track_id))
    
    def cmd_move(self, idx_from, idx_to):
        """Move a track in the playlist."""
        idx_from = cast_arg(int, idx_from)
        idx_to = cast_arg(int, idx_to)
        try:
            track = self.playlist.pop(idx_from)
            self.playlist.insert(idx_to, track)
        except IndexError:
            raise ArgumentIndexError()
    def cmd_moveid(self, id_from, idx_to):
        idx_from = self._id_to_index(idx_from)
        for l in self.cmd_move(idx_from, idx_to): yield l
    
    def cmd_swap(self, i, j):
        """Swaps two tracks in the playlist."""
        i = cast_arg(int, i)
        j = cast_arg(int, j)
        try:
            track_i = self.playlist[i]
            track_j = self.playlist[j]
        except IndexError:
            raise ArgumentIndexError()
        self.playlist[j] = track_i
        self.playlist[i] = track_j
    def cmd_swapid(self, i_id, j_id):
        i = self._id_to_index(i_id)
        j = self._id_to_index(j_id)
        for l in self.cmd_swap(i, j): yield l
    
    def cmd_urlhandlers(self):
        """Indicates supported URL schemes. None by default."""
        pass
    
    def cmd_playlistinfo(self, index=-1):
        """Gives metadata information about the entire playlist or a
        single track, given by its index.
        """
        index = cast_arg(int, index)
        if index == -1:
            for track in self.playlist:
                yield self._item_info(track)
        else:
            try:
                track = self.playlist[index]
            except IndexError:
                raise ArgumentIndexError()
            yield self._item_info(track)
    def cmd_playlistid(self, track_id=-1):
        for l in self.cmd_playlistinfo(self._id_to_index(track_id)):
            yield l
    
    def cmd_plchanges(self, version):
        """Yields playlist changes since the given version.
        
        This is a "fake" implementation that ignores the version and
        just returns the entire playlist (rather like version=0). This
        seems to satisfy many clients.
        """
        for l in self.cmd_playlistinfo(): yield l
    
    def cmd_currentsong(self):
        """Yields information about the currently-playing song.
        """
        if self.current_index != -1: # -1 means stopped.
            track = self.playlist[self.current_index]
            yield self._item_info(track)
    
    def cmd_next(self):
        """Advance to the next song in the playlist."""
        self.current_index += 1
        if self.current_index >= len(self.playlist):
            # Fallen off the end. Just move to stopped state.
            self.cmd_stop()
        else:
            self.cmd_play()
    
    def cmd_previous(self):
        """Step back to the last song."""
        self.current_index -= 1
        if self.current_index < 0:
            self.cmd_stop()
        else:
            self.cmd_play()
    
    def cmd_pause(self, state=None):
        """Set the pause state playback."""
        if state is None:
            self.paused = not self.paused # Toggle.
        else:
            self.paused = cast_arg('intbool', state)
    
    def cmd_play(self, index=-1):
        """Begin playback, possibly at a specified playlist index."""
        index = cast_arg(int, index)
        if index == -1: # No index specified: start where we are.
            if not self.playlist: # Empty playlist: stop immediately.
                self.cmd_stop()
            if self.current_index == -1: # No current song.
                self.current_index = 0 # Start at the beginning.
            # If we have a current song, just stay there.
        else: # Start with the specified index.
            self.current_index = index
        
        self.paused = False
        
    def cmd_playid(self, track_id=0):
        track_id = cast_arg(int, track_id)
        if track_id == -1:
            index = -1
        else:
            index = self._id_to_index(track_id)
        self.cmd_play(index)
    
    def cmd_stop(self):
        """Stop playback."""
        self.current_index = -1
        self.paused = False
    
    def cmd_seek(self, index, time):
        """Seek to a specified point in a specified song."""
        index = cast_arg(int, index)
        if index < 0 or index >= len(self.playlist):
            raise ArgumentIndexError()
        self.current_index = index
        self.cmd_play()
    def cmd_seekid(self, track_id, time):
        index = self._id_to_index(track_id)
        for l in self.cmd_seek(index, time): yield l

class Connection(object):
    """A connection between a client and the server. Handles input and
    output from and to the client.
    """
    
    def __init__(self, client, server):
        """Create a new connection for the accepted socket `client`.
        """
        self.client, self.server = client, server
    
    def send(self, data=None):
        """Send data, which is either a string or an iterable
        consisting of strings, to the client. A newline is added after
        every string. `data` may be None, in which case nothing is
        sent.
        """
        if data is None:
            return
        
        if isinstance(data, basestring): # Passed a single string.
            out = data + NEWLINE
        else: # Passed an iterable of strings (for instance, a Response).
            out = NEWLINE.join(data) + NEWLINE
        
        log.debug(out[:-1]) # Don't log trailing newline.
        self.client.sendall(out.encode('utf-8'))
    
    line_re = re.compile(r'([^\r\n]*)(?:\r\n|\n\r|\n|\r)')
    def lines(self):
        """A generator yielding lines (delimited by some usual newline
        code) as they arrive from the client.
        """
        buf = ''
        while True:
            # Dump new data on the buffer.
            chunk = self.client.recv(BUFSIZE)
            if not chunk: break # EOF.
            buf += chunk
            
            # Clear out and yield any lines in the buffer.
            while True:
                match = self.line_re.match(buf)
                if not match: break # No lines remain.
                yield match.group(1)
                buf = buf[match.end():] # Remove line from buffer.
    
    def do_command(self, command):
        """Run the given command and give an appropriate response."""
        try:
            command.run(self)
        except BPDError, e:
            # Send the error.
            self.send(e.response())
        else:
            # Send success code.
            self.send(RESP_OK)
    
    def run(self):
        """Send a greeting to the client and begin processing commands
        as they arrive. Blocks until the client disconnects.
        """
        self.send(HELLO)
        
        clist = None # Initially, no command list is being constructed.
        for line in self.lines():
            log.debug(line)
               
            if clist is not None:
                # Command list already opened.
                if line == CLIST_END:
                    self.do_command(clist)
                    clist = None # Clear the command list.
                else:
                    clist.append(Command(line))
            
            elif line == CLIST_BEGIN or line == CLIST_VERBOSE_BEGIN:
                # Begin a command list.
                clist = CommandList([], line == CLIST_VERBOSE_BEGIN)
                
            else:
                # Ordinary command.
                try:
                    self.do_command(Command(line))
                except BPDClose:
                    # Command indicates that the conn should close.
                    self.client.close()
                    return
    
    @classmethod
    def handle(cls, client, server):
        """Creates a new `Connection` for `client` and `server` and runs
        it.
        """
        cls(client, server).run()

class Command(object):
    """A command issued by the client for processing by the server.
    """
    
    command_re = re.compile(r'^([^ \t]+)[ \t]*')
    arg_re = re.compile(r'"((?:\\"|[^"])+)"|([^ \t"]+)')
    
    def __init__(self, s):
        """Creates a new `Command` from the given string, `s`, parsing
        the string for command name and arguments.
        """
        command_match = self.command_re.match(s)
        self.name = command_match.group(1)
        arg_matches = self.arg_re.findall(s[command_match.end():])
        self.args = [m[0] or m[1] for m in arg_matches]
        
    def run(self, conn):
        """Executes the command on the given connection.
        """
        func_name = 'cmd_' + self.name
        if hasattr(conn.server, func_name):
            try:
                responses = getattr(conn.server, func_name)(*self.args)
                if responses is not None:
                    # Yielding nothing is considered success.
                    for response in responses:
                        conn.send(response)
            
            except BPDError, e:
                # An exposed error. Set the command name and then let
                # the Connection handle it.
                e.cmd_name = self.name
                raise e
            
            except BPDClose:
                # An indication that the connection should close. Send
                # it on the Connection.
                raise
            
            except Exception, e:
                # An "unintentional" error. Hide it from the client.
                log.error(traceback.format_exc(e))
                raise BPDError(ERROR_SYSTEM, 'server error', self.name)
                
        else:
            raise BPDError(ERROR_UNKNOWN, 'unknown command', self.name)

class CommandList(list):
    """A list of commands issued by the client for processing by the
    server. May be verbose, in which case the response is delimited, or
    not. Should be a list of `Command` objects.
    """
    def __init__(self, sequence=None, verbose=False):
        """Create a new `CommandList` from the given sequence of
        `Command`s. If `verbose`, this is a verbose command list.
        """
        if sequence:
            for item in sequence:
                self.append(item)
        self.verbose = verbose

    def run(self, conn):
        """Execute all the commands in this list.
        """

        for i, command in enumerate(self):
            try:
                command.run(conn)
            except BPDError, e:
                # If the command failed, stop executing.
                e.index = i # Give the error the correct index.
                raise e

            # Otherwise, possibly send the output delimeter if we're in a
            # verbose ("OK") command list.
            if self.verbose:
                conn.send(RESP_CLIST_VERBOSE)



# A subclass of the basic, protocol-handling server that actually plays
# music.

class Server(BaseServer):
    """An MPD-compatible server using GStreamer to play audio and beets
    to store its library.
    """

    def __init__(self, library, host='', port=DEFAULT_PORT):
        from beets.player.gstplayer import GstPlayer
        super(Server, self).__init__(host, port)
        self.lib = library
        self.player = GstPlayer(self.play_finished)
    
    def run(self):
        self.player.run()
        super(Server, self).run()

    def play_finished(self):
        """A callback invoked every time our player finishes a
        track.
        """
        self.cmd_next()
    
    
    # Metadata helper functions.
    
    def _item_path(self, item):
        """Returns the item's "virtual path."""
        return seq_to_path((item.artist, item.album, item.title))

    def _item_info(self, item):
        info_lines = ['file: ' + self._item_path(item),
                      'Time: ' + str(int(item.length)),
                      'Title: ' + item.title,
                      'Artist: ' + item.artist,
                      'Album: ' + item.album,
                      'Genre: ' + item.genre,
                     ]
        
        track = str(item.track)
        if item.tracktotal:
            track += '/' + str(item.tracktotal)
        info_lines.append('Track: ' + track)
        
        info_lines.append('Date: ' + str(item.year))
        
        try:
            pos = self._id_to_index(item.id)
            info_lines.append('Pos: ' + str(pos))
        except ArgumentNotFoundError:
            # Don't include position if not in playlist.
            pass
        
        info_lines.append('Id: ' + str(item.id))
        
        return info_lines
        
    def _item_id(self, item):
        return item.id


    # Path (directory tree) browsing.
    
    def _parse_path(self, path="/"):
        """Take an artist/album/track path and return its components.
        """
        if len(path) >= 1 and path[0] == '/': # Remove leading slash.
            path = path[1:]
        items = path_to_list(path)

        artist, album, track = None, None, None
        if items: artist = items.pop(0)
        if items: album = items.pop(0)
        if items: track = items.pop(0)
        return artist, album, track
    
    def cmd_lsinfo(self, path="/"):
        """Yields info on all the items in the path."""
        artist, album, track = self._parse_path(path)
        
        if not artist: # List all artists.
            for artist in self.lib.artists():
                yield 'directory: ' + artist
        elif not album: # List all albums for an artist.
            for album in self.lib.albums(artist):
                yield 'directory: ' + seq_to_path(album)
        elif not track: # List all tracks on an album.
            for item in self.lib.items(artist, album):
                yield self._item_info(item)
        else: # List a track. This isn't a directory.
            raise BPDError(ERROR_ARG, 'this is not a directory')
        
    def _listall(self, path="/", info=False):
        """Helper function for recursive listing. If info, show
        tracks' complete info; otherwise, just show items' paths.
        """
        artist, album, track = self._parse_path(path)

        # artists
        if not artist:
            for a in self.lib.artists():
                yield 'directory: ' + a

        # albums
        if not album:
            for a in self.lib.albums(artist or None):
                yield 'directory: ' + seq_to_path(a)

        # tracks
        items = self.lib.items(artist or None, album or None)
        if info:
            for item in items:
                yield self._item_info(item)
        else:
            for item in items:
                yield 'file: ' + self._item_path(i)
    
    def cmd_listall(self, path="/"):
        """Return the paths all items in the directory, recursively."""
        for l in self._listall(path, False): yield l
    def cmd_listallinfo(self, path="/"):
        """Return info on all the items in the directory, recursively."""
        for l in self._listall(path, True): yield l
    
    
    # Playlist manipulation.
    
    def _get_by_path(self, path):
        """Helper function returning the item at a given path."""
        artist, album, track = path_to_list(path)
        it = self.lib.items(artist, album, track)
        try:
            return it.next()
        except StopIteration:
            raise ArgumentNotFoundError()
    def cmd_add(self, path):
        """Adds a track to the playlist, specified by its path."""
        self.playlist.append(self._get_by_path(path))
        self.playlist_version += 1
    def cmd_addid(self, path):
        """Same as cmd_add but yields an id."""
        track = self._get_by_path(path)
        self.playlist.append(track)
        self.playlist_version += 1
        yield 'Id: ' + str(track.id)


    # Server info.

    def cmd_status(self):
        for l in super(Server, self).cmd_status(): yield l
        if self.current_index > -1:
            item = self.playlist[self.current_index]
            yield 'bitrate: ' + str(item.bitrate/1000)
            yield 'time: 0:' + str(int(item.length)) #fixme

    def cmd_stats(self):
        # The first three items need to be done more efficiently. The
        # last three need to be implemented.
        yield ('artists: ' + str(len(self.lib.artists())),
               'albums: ' + str(len(self.lib.albums())),
               'songs: ' + str(len(list(self.lib.items()))),
               'uptime: ' + str(int(time.time() - self.startup_time)),
               'playtime: ' + '0',
               'db_playtime: ' + '0',
               'db_update: ' + str(int(self.startup_time)),
              )


    # Searching.

    tagtype_map = {
        'Artist':       'artist',
        'Album':        'album',
        'Title':        'title',
        'Track':        'track',
        # Name?
        'Genre':        'genre',
        'Date':         'year',
        'Composer':     'composer',
        # Performer?
        'Disc':         'disc',
    }

    def cmd_tagtypes(self):
        """Returns a list of the metadata (tag) fields available for
        searching.
        """
        for tag in self.tagtype_map:
            yield 'tagtype: ' + tag
    
    def cmd_search(self, key, value):
        """Perform a substring match in a specific column."""
        if key == 'filename':
            key = 'path'
        query = beets.library.SubstringQuery(key, value)
        for item in self.lib.get(query):
            yield self._item_info(item)
    
    def cmd_find(self, key, value):
        """Perform an exact match in a specific column."""
        if key == 'filename':
            key = 'path'
        query = beets.library.MatchQuery(key, value)
        for item in self.lib.get(query):
            yield self._item_info(item)
    
    
    # "Outputs." Just a dummy implementation because we don't control
    # any outputs.
    
    def cmd_outputs(self):
        """List the available outputs."""
        yield ('outputid: 0',
               'outputname: gstreamer',
               'outputenabled: 1',
              )
    
    def cmd_enableoutput(self, output_id):
        output_id = cast_arg(int, output_id)
        if output_id != 0:
            raise ArgumentIndexError()
    
    def cmd_disableoutput(self, output_id):
        output_id = cast_arg(int, output_id)
        if output_id == 0:
            raise BPDError(ERROR_ARG, 'cannot disable this output')
        else:
            raise ArgumentIndexError()
        

            
    # The functions below hook into the half-implementations provided
    # by the base class. Together, they're enough to implement all
    # normal playback functionality.

    def cmd_play(self, index=-1):
        super(Server, self).cmd_play(index)
        if self.current_index > -1: # Not stopped.
            self.player.play_file(self.playlist[self.current_index].path)

    def cmd_pause(self, state=None):
        super(Server, self).cmd_pause(state)
        if self.paused:
            self.player.pause()
        elif self.playing:
            self.player.play()

    def cmd_stop(self):
        super(Server, self).cmd_stop()
        self.player.stop()


# When run as a script, just start the server.

if __name__ == '__main__':
    Server(beets.Library('library.blb')).run()

