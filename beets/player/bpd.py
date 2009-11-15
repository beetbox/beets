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

SAFE_COMMANDS = (
    # Commands that are available when unauthenticated.
    'close', 'commands', 'notcommands', 'password', 'ping',
)


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

def seq_to_path(seq, placeholder=''):
    """Encodes a sequence of strings as a path-like string. The
    sequence can be recovered exactly using path_to_list. If
    `placeholder` is provided, it is used in place of empty path
    components.
    """
    out = []
    for s in seq:
        if placeholder and s == '':
            out.append(placeholder)
        else:
            out.append(s.replace('\\', '\\\\') # preserve backslashes
                        .replace('_', '\\_')   # preserve _s
                        .replace('/', '_')     # hide /s as _s
                      )
    return '/'.join(out)


def path_to_list(path, placeholder=''):
    """Takes a path-like string (probably encoded by seq_to_path) and
    returns the list of strings it represents. If `placeholder` is
    provided, it is interpreted to represent an empty path component.
    Also, when given a `placeholder`, this function ignores empty
    path components.
    """
    def repl(m):
        # This function maps "escaped" characters to original
        # characters. Because the regex is in the right order, the
        # sequences are replaced top-to-bottom.
        return {'\\\\': '\\',
                '\\_':  '_',
                '_':    '/',
               }[m.group(0)]
    components = [re.sub(r'\\\\|\\_|_', repl, component)
                  for component in path.split('/')]
    
    if placeholder:
        new_components = []
        for c in components:
            if c == '':
                # Drop empty path components.
                continue
            if c == placeholder:
                new_components.append('')
            else:
                new_components.append(c)
        components = new_components
    
    return components

PATH_PH = '(unknown)'


# Generic server infrastructure, implementing the basic protocol.

class BaseServer(object):
    """A MPD-compatible music player server.
    
    The functions with the `cmd_` prefix are invoked in response to
    client commands. For instance, if the client says `status`,
    `cmd_status` will be invoked. The arguments to the client's commands
    are used as function arguments following the connection issuing the
    command. The functions may send data on the connection. They may
    also raise BPDError exceptions to report errors.
    
    This is a generic superclass and doesn't support many commands.
    """
    
    def __init__(self, host='', port=DEFAULT_PORT, password=''):
        """Create a new server bound to address `host` and listening
        on port `port`. If `password` is given, it is required to do
        anything significant on the server.
        """
        self.host, self.port, self.password = host, port, password
        
        # Default server values.
        self.random = False
        self.repeat = False
        self.volume = VOLUME_MAX
        self.crossfade = 0
        self.playlist = []
        self.playlist_version = 0
        self.current_index = -1
        self.paused = False
        self.error = None
    
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

    def cmd_ping(self, conn):
        """Succeeds."""
        pass
    
    def cmd_kill(self, conn):
        """Exits the server process."""
        self.listener.close()
        exit(0)
    
    def cmd_close(self, conn):
        """Closes the connection."""
        raise BPDClose()
    
    def cmd_password(self, conn, password):
        """Attempts password authentication."""
        if password == self.password:
            conn.authenticated = True
        else:
            conn.authenticated = False
            raise BPDError(ERROR_PASSWORD, 'incorrect password')
    
    def cmd_commands(self, conn):
        """Lists the commands available to the user."""
        if self.password and not conn.authenticated:
            # Not authenticated. Show limited list of commands.
            for cmd in SAFE_COMMANDS:
                conn.send('command: ' + cmd)
        
        else:
            # Authenticated. Show all commands.
            for func in dir(self):
                if func.startswith('cmd_'):
                    conn.send('command: ' + func[4:])
    
    def cmd_notcommands(self, conn):
        """Lists all unavailable commands."""
        if self.password and not conn.authenticated:
            # Not authenticated. Show privileged commands.
            for func in dir(self):
                if func.startswith('cmd_'):
                    cmd = func[4:]
                    if cmd not in SAFE_COMMANDS:
                        conn.send('command: ' + cmd)
        
        else:
            # Authenticated. No commands are unavailable.
            pass
    
    def cmd_status(self, conn):
        """Returns some status information for use with an
        implementation of cmd_status.
        
        Gives a list of response-lines for: volume, repeat, random,
        playlist, playlistlength, and xfade.
        """
        conn.send('volume: ' + str(self.volume),
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
        conn.send('state: ' + state)
        
        if self.current_index != -1: # i.e., paused or playing
            current_id = self._item_id(self.playlist[self.current_index])
            conn.send('song: ' + str(self.current_index))
            conn.send('songid: ' + str(current_id))

        if self.error:
            conn.send('error: ' + self.error)

    def cmd_clearerror(self, conn):
        """Removes the persistent error state of the server. This
        error is set when a problem arises not in response to a
        command (for instance, when playing a file).
        """
        self.error = None
    
    def cmd_random(self, conn, state):
        """Set or unset random (shuffle) mode."""
        self.random = cast_arg('intbool', state)
    
    def cmd_repeat(self, conn, state):
        """Set or unset repeat mode."""
        self.repeat = cast_arg('intbool', state)
    
    def cmd_setvol(self, conn, vol):
        """Set the player's volume level (0-100)."""
        vol = cast_arg(int, vol)
        if vol < VOLUME_MIN or vol > VOLUME_MAX:
            raise BPDError(ERROR_ARG, 'volume out of range')
        self.volume = vol
    
    def cmd_crossfade(self, conn, crossfade):
        """Set the number of seconds of crossfading."""
        crossfade = cast_arg(int, crossfade)
        if crossfade < 0:            
            raise BPDError(ERROR_ARG, 'crossfade time must be nonnegative')
    
    def cmd_clear(self, conn):
        """Clear the playlist."""
        self.playlist = []
        self.playlist_version += 1
        self.cmd_stop(conn)
    
    def cmd_delete(self, conn, index):
        """Remove the song at index from the playlist."""
        index = cast_arg(int, index)
        try:
            del(self.playlist[index])
        except IndexError:
            raise ArgumentIndexError()
        self.playlist_version += 1

        if self.current_index == index: # Deleted playing song.
            self.cmd_stop(conn)
        elif index < self.current_index: # Deleted before playing.
            # Shift playing index down.
            self.current_index -= 1

    def cmd_deleteid(self, conn, track_id):
        self.cmd_delete(conn, self._id_to_index(track_id))
    
    def cmd_move(self, conn, idx_from, idx_to):
        """Move a track in the playlist."""
        print idx_from, idx_to
        print self.current_index, [i.title for i in self.playlist]
        idx_from = cast_arg(int, idx_from)
        idx_to = cast_arg(int, idx_to)
        try:
            track = self.playlist.pop(idx_from)
            self.playlist.insert(idx_to, track)
        except IndexError:
            raise ArgumentIndexError()
        
        # Update currently-playing song.
        if idx_from == self.current_index:
            self.current_index = idx_to
        elif idx_from < self.current_index <= idx_to:
            self.current_index -= 1
        elif idx_from > self.current_index >= idx_to:
            self.current_index += 1
        
        self.playlist_version += 1
    
    def cmd_moveid(self, conn, id_from, idx_to):
        idx_from = self._id_to_index(idx_from)
        self.cmd_move(conn, idx_from, idx_to)
    
    def cmd_swap(self, conn, i, j):
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
        
        # Update currently-playing song.
        if self.current_index == i:
            self.current_index = j
        elif self.current_index == j:
            self.current_index = i
    
        self.playlist_version += 1
        
    def cmd_swapid(self, conn, i_id, j_id):
        i = self._id_to_index(i_id)
        j = self._id_to_index(j_id)
        self.cmd_swap(conn, i, j)
    
    def cmd_urlhandlers(self, conn):
        """Indicates supported URL schemes. None by default."""
        pass
    
    def cmd_playlistinfo(self, conn, index=-1):
        """Gives metadata information about the entire playlist or a
        single track, given by its index.
        """
        index = cast_arg(int, index)
        if index == -1:
            for track in self.playlist:
                conn.send(*self._item_info(track))
        else:
            try:
                track = self.playlist[index]
            except IndexError:
                raise ArgumentIndexError()
            conn.send(*self._item_info(track))
    def cmd_playlistid(self, conn, track_id=-1):
        self.cmd_playlistinfo(conn, self._id_to_index(track_id))
    
    def cmd_plchanges(self, conn, version):
        """Sends playlist changes since the given version.
        
        This is a "fake" implementation that ignores the version and
        just returns the entire playlist (rather like version=0). This
        seems to satisfy many clients.
        """
        self.cmd_playlistinfo(conn)
    
    def cmd_plchangesposid(self, conn, version):
        """Like plchanges, but only sends position and id.
        
        Also a dummy implementation.
        """
        for idx, track in enumerate(self.playlist):
            conn.send('cpos: ' + str(idx), 
                      'Id: ' + str(track.id),
                      )
    
    def cmd_currentsong(self, conn):
        """Sends information about the currently-playing song.
        """
        if self.current_index != -1: # -1 means stopped.
            track = self.playlist[self.current_index]
            conn.send(*self._item_info(track))
    
    def cmd_next(self, conn):
        """Advance to the next song in the playlist."""
        self.current_index += 1
        if self.current_index >= len(self.playlist):
            # Fallen off the end. Just move to stopped state.
            self.cmd_stop(conn)
        else:
            self.cmd_play(conn)
    
    def cmd_previous(self, conn):
        """Step back to the last song."""
        self.current_index -= 1
        if self.current_index < 0:
            self.cmd_stop(conn)
        else:
            self.cmd_play(conn)
    
    def cmd_pause(self, conn, state=None):
        """Set the pause state playback."""
        if state is None:
            self.paused = not self.paused # Toggle.
        else:
            self.paused = cast_arg('intbool', state)
    
    def cmd_play(self, conn, index=-1):
        """Begin playback, possibly at a specified playlist index."""
        index = cast_arg(int, index)
        
        if index < -1 or index > len(self.playlist):
            raise ArgumentIndexError()
        
        if index == -1: # No index specified: start where we are.
            if not self.playlist: # Empty playlist: stop immediately.
                self.cmd_stop(conn)
            if self.current_index == -1: # No current song.
                self.current_index = 0 # Start at the beginning.
            # If we have a current song, just stay there.
        
        else: # Start with the specified index.
            self.current_index = index
        
        self.paused = False
        
    def cmd_playid(self, conn, track_id=0):
        track_id = cast_arg(int, track_id)
        if track_id == -1:
            index = -1
        else:
            index = self._id_to_index(track_id)
        self.cmd_play(conn, index)
    
    def cmd_stop(self, conn):
        """Stop playback."""
        self.current_index = -1
        self.paused = False
    
    def cmd_seek(self, conn, index, pos):
        """Seek to a specified point in a specified song."""
        index = cast_arg(int, index)
        if index < 0 or index >= len(self.playlist):
            raise ArgumentIndexError()
        self.current_index = index
    def cmd_seekid(self, track_id, pos):
        index = self._id_to_index(track_id)
        self.cmd_seek(conn, index, pos)

class Connection(object):
    """A connection between a client and the server. Handles input and
    output from and to the client.
    """
    
    def __init__(self, client, server):
        """Create a new connection for the accepted socket `client`.
        """
        self.client, self.server = client, server
        self.authenticated = False
    
    def send(self, *lines):
        """Send lines, which are strings, to the client. A newline is
        added after every string. `data` may be None, in which case
        nothing is sent.
        """
        out = NEWLINE.join(lines) + NEWLINE
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
        
        # Attempt to get correct command function.
        func_name = 'cmd_' + self.name
        if not hasattr(conn.server, func_name):
            raise BPDError(ERROR_UNKNOWN, 'unknown command', self.name)
        func = getattr(conn.server, func_name)
        
        # Ensure we have permission for this command.
        if conn.server.password and \
                not conn.authenticated and \
                self.name not in SAFE_COMMANDS:
            raise BPDError(ERROR_PERMISSION, 'insufficient privileges')
        
        try:
            args = [conn] + self.args
            func(*args)
        
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

    def __init__(self, library, host='', port=DEFAULT_PORT, password=''):
        from beets.player.gstplayer import GstPlayer
        super(Server, self).__init__(host, port, password)
        self.lib = library
        self.player = GstPlayer(self.play_finished)
    
    def run(self):
        self.player.run()
        super(Server, self).run()

    def play_finished(self):
        """A callback invoked every time our player finishes a
        track.
        """
        self.cmd_next(None)
    
    
    # Metadata helper functions.
    
    def _item_path(self, item):
        """Returns the item's "virtual path."""
        return seq_to_path((item.artist, item.album, item.title), PATH_PH)

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
        items = path_to_list(path, PATH_PH)

        dirs = [None, None, None]
        for i in range(len(dirs)):
            if items:
                # Take a directory if it exists. Otherwise, leave as "none".
                # This way, we ensure that we always return 3 elements.
                dirs[i] = items.pop(0)
        return dirs
    
    def cmd_lsinfo(self, conn, path="/"):
        """Sends info on all the items in the path."""
        artist, album, track = self._parse_path(path)
        
        if artist is None: # List all artists.
            for artist in self.lib.artists():
                conn.send('directory: ' + seq_to_path((artist,), PATH_PH))
        elif album is None: # List all albums for an artist.
            for album in self.lib.albums(artist):
                conn.send('directory: ' + seq_to_path(album, PATH_PH))
        elif track is None: # List all tracks on an album.
            for item in self.lib.items(artist, album):
                conn.send(*self._item_info(item))
        else: # List a track. This isn't a directory.
            raise BPDError(ERROR_ARG, 'this is not a directory')
        
    def _listall(self, conn, path="/", info=False):
        """Helper function for recursive listing. If info, show
        tracks' complete info; otherwise, just show items' paths.
        """
        artist, album, track = self._parse_path(path)

        # artists
        if not artist:
            for a in self.lib.artists():
                conn.send('directory: ' + a)

        # albums
        if not album:
            for a in self.lib.albums(artist or None):
                conn.send('directory: ' + seq_to_path(a, PATH_PH))

        # tracks
        items = self.lib.items(artist or None, album or None)
        if info:
            for item in items:
                conn.send(*self._item_info(item))
        else:
            for item in items:
                conn.send('file: ' + self._item_path(i))
    
    def cmd_listall(self, conn, path="/"):
        """Send the paths all items in the directory, recursively."""
        self._listall(conn, path, False)
    def cmd_listallinfo(self, conn, path="/"):
        """Send info on all the items in the directory, recursively."""
        self._listall(conn, path, True)
    
    
    # Playlist manipulation.
    
    def _add(self, conn, path, send_id=False):
        """Adds a track or directory to the playlist, specified by a
        path. If `send_id`, write each item's id to the client.
        """
        components = path_to_list(path, PATH_PH)
        
        if len(components) <= 3:
            # Add a single track.
            found_an_item = None
            for item in self.lib.items(*components):
                found_an_item = True
                self.playlist.append(item)
                if send_id:
                    conn.send('Id: ' + str(item.id))
                
            if not found_an_item:
                # No items matched.
                raise ArgumentNotFoundError()
            
            self.playlist_version += 1
        
        else:
            # More than three path components: invalid pathname.
            raise ArgumentNotFoundError()
        
    def cmd_add(self, conn, path):
        """Adds a track or directory to the playlist, specified by a
        path.
        """
        self._add(conn, path, False)
    
    def cmd_addid(self, conn, path):
        """Same as `cmd_add` but sends an id back to the client."""
        self._add(conn, path, True)


    # Server info.

    def cmd_status(self, conn):
        super(Server, self).cmd_status(conn)
        if self.current_index > -1:
            item = self.playlist[self.current_index]
            
            conn.send('bitrate: ' + str(item.bitrate/1000))
            #fixme: missing 'audio'
            
            (pos, total) = self.player.time()
            conn.send('time: ' + str(pos) + ':' + str(total))
            
        #fixme: also missing 'updating_db'


    def cmd_stats(self, conn):
        """Sends some statistics about the library."""
        songs, totaltime = beets.library.TrueQuery().count(self.lib)

        statement = 'SELECT COUNT(DISTINCT artist), ' \
                           'COUNT(DISTINCT album) FROM items'
        c = self.lib.conn.cursor()
        result = c.execute(statement).fetchone()
        artists, albums = result[0], result[1]

        conn.send('artists: ' + str(artists),
                  'albums: ' + str(albums),
                  'songs: ' + str(songs),
                  'uptime: ' + str(int(time.time() - self.startup_time)),
                  'playtime: ' + '0', #fixme
                  'db_playtime: ' + str(int(totaltime)),
                  'db_update: ' + str(int(self.startup_time)), #fixme
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
        'filename':     'path', # Suspect.
    }

    def cmd_tagtypes(self, conn):
        """Returns a list of the metadata (tag) fields available for
        searching.
        """
        for tag in self.tagtype_map:
            conn.send('tagtype: ' + tag)
    
    def _tagtype_lookup(self, tag):
        """Uses `tagtype_map` to look up the beets column name for an
        MPD tagtype (or throw an appropriate exception). Returns both
        the canonical name of the MPD tagtype and the beets column
        name.
        """
        for test_tag, key in self.tagtype_map.items():
            # Match case-insensitively.
            if test_tag.lower() == tag.lower():
                return test_tag, key
        raise BPDError(ERROR_UNKNOWN, 'no such tagtype')

    def _metadata_query(self, query_type, any_query_type, kv):
        """Helper function returns a query object that will find items
        according to the library query type provided and the key-value
        pairs specified. The any_query_type is used for queries of
        type "any"; if None, then an error is thrown.
        """
        if kv: # At least one key-value pair.
            queries = []
            # Iterate pairwise over the arguments.
            it = iter(kv)
            for tag, value in zip(it, it):
                if tag.lower() == 'any':
                    if any_query_type:
                        queries.append(any_query_type(value))
                    else:
                        raise BPDError(ERROR_UNKNOWN, 'no such tagtype')
                else:
                    _, key = self._tagtype_lookup(tag)
                    queries.append(query_type(key, value))
            return beets.library.AndQuery(queries)
        else: # No key-value pairs.
            return beets.library.TrueQuery()
    
    def cmd_search(self, conn, *kv):
        """Perform a substring match for items."""
        query = self._metadata_query(beets.library.SubstringQuery,
                                     beets.library.AnySubstringQuery,
                                     kv)
        for item in self.lib.items(query=query):
            conn.send(*self._item_info(item))
    
    def cmd_find(self, conn, *kv):
        """Perform an exact match for items."""
        query = self._metadata_query(beets.library.MatchQuery,
                                     None,
                                     kv)
        for item in self.lib.items(query=query):
            conn.send(*self._item_info(item))
    
    def cmd_list(self, conn, show_tag, *kv):
        """List distinct metadata values for show_tag, possibly
        filtered by matching match_tag to match_term.
        """
        show_tag_canon, show_key = self._tagtype_lookup(show_tag)
        query = self._metadata_query(beets.library.MatchQuery, None, kv)
        
        clause, subvals = query.clause()
        statement = 'SELECT DISTINCT ' + show_key + \
                    ' FROM items WHERE ' + clause + \
                    ' ORDER BY ' + show_key
        c = self.lib.conn.cursor()
        c.execute(statement, subvals)
        
        for row in c:
            conn.send(show_tag_canon + ': ' + unicode(row[0]))
    
    def cmd_count(self, conn, tag, value):
        """Returns the number and total time of songs matching the
        tag/value query.
        """
        _, key = self._tagtype_lookup(tag)
        query = beets.library.MatchQuery(key, value)
        songs, playtime = query.count(self.lib)
        conn.send('songs: ' + str(songs),
                  'playtime: ' + str(int(playtime)))
        
    
    # "Outputs." Just a dummy implementation because we don't control
    # any outputs.
    
    def cmd_outputs(self, conn):
        """List the available outputs."""
        conn.send('outputid: 0',
                  'outputname: gstreamer',
                  'outputenabled: 1',
                  )
    
    def cmd_enableoutput(self, conn, output_id):
        output_id = cast_arg(int, output_id)
        if output_id != 0:
            raise ArgumentIndexError()
    
    def cmd_disableoutput(self, conn, output_id):
        output_id = cast_arg(int, output_id)
        if output_id == 0:
            raise BPDError(ERROR_ARG, 'cannot disable this output')
        else:
            raise ArgumentIndexError()
        
   
    # Playback control. The functions below hook into the
    # half-implementations provided by the base class. Together, they're
    # enough to implement all normal playback functionality.

    def cmd_play(self, conn, index=-1):
        new_index = index != -1 and index != self.current_index
        was_paused = self.paused
        super(Server, self).cmd_play(conn, index)
        
        if self.current_index > -1: # Not stopped.
            if was_paused and not new_index:
                # Just unpause.
                self.player.play()
            else:
                self.player.play_file(self.playlist[self.current_index].path)

    def cmd_pause(self, conn, state=None):
        super(Server, self).cmd_pause(conn, state)
        if self.paused:
            self.player.pause()
        elif self.player.playing:
            self.player.play()

    def cmd_stop(self, conn):
        super(Server, self).cmd_stop(conn)
        self.player.stop()
    
    def cmd_seek(self, conn, index, pos):
        """Seeks to the specified position in the specified song."""
        index = cast_arg(int, index)
        pos = cast_arg(int, pos)
        super(Server, self).cmd_seek(conn, index, pos)
        self.player.seek(pos)


# When run as a script, just start the server.

if __name__ == '__main__':
    Server(beets.Library('library.blb')).run()
