# This file is part of beets.
# Copyright 2010, Adrian Sampson.
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

"""A clone of the Music Player Daemon (MPD) that plays music from a
Beets library. Attempts to implement a compatible protocol to allow
use of the wide range of MPD clients.
"""

import bluelet
import re
from string import Template
import traceback
import logging
import time

import beets
from beets.plugins import BeetsPlugin
import beets.ui
from beets import vfs


DEFAULT_PORT = 6600
DEFAULT_HOST = ''
DEFAULT_PASSWORD = ''
PROTOCOL_VERSION = '0.13.0'
BUFSIZE = 1024

HELLO = 'OK MPD %s' % PROTOCOL_VERSION
CLIST_BEGIN = 'command_list_begin'
CLIST_VERBOSE_BEGIN = 'command_list_ok_begin'
CLIST_END = 'command_list_end'
RESP_OK = 'OK'
RESP_CLIST_VERBOSE = 'list_OK'
RESP_ERR = 'ACK'

NEWLINE = u"\n"

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
    u'close', u'commands', u'notcommands', u'password', u'ping',
)


# Loggers.
log = logging.getLogger('beets.bpd')
global_log = logging.getLogger('beets')


# Gstreamer import error.
class NoGstreamerError(Exception): pass


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
        
    template = Template(u'$resp [$code@$index] {$cmd_name} $message')
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
    
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT,
                 password=DEFAULT_PASSWORD):
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
        bluelet.run(bluelet.server(self.host, self.port,
                                   Connection.handler(self)))

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
                yield u'command: ' + cmd
        
        else:
            # Authenticated. Show all commands.
            for func in dir(self):
                if func.startswith('cmd_'):
                    yield u'command: ' + func[4:]
    
    def cmd_notcommands(self, conn):
        """Lists all unavailable commands."""
        if self.password and not conn.authenticated:
            # Not authenticated. Show privileged commands.
            for func in dir(self):
                if func.startswith('cmd_'):
                    cmd = func[4:]
                    if cmd not in SAFE_COMMANDS:
                        yield u'command: ' + cmd
        
        else:
            # Authenticated. No commands are unavailable.
            pass
    
    def cmd_status(self, conn):
        """Returns some status information for use with an
        implementation of cmd_status.
        
        Gives a list of response-lines for: volume, repeat, random,
        playlist, playlistlength, and xfade.
        """
        yield (u'volume: ' + unicode(self.volume),
               u'repeat: ' + unicode(int(self.repeat)),
               u'random: ' + unicode(int(self.random)),
               u'playlist: ' + unicode(self.playlist_version),
               u'playlistlength: ' + unicode(len(self.playlist)),
               u'xfade: ' + unicode(self.crossfade),
              )
        
        if self.current_index == -1:
            state = u'stop'
        elif self.paused:
            state = u'pause'
        else:
            state = u'play'
        yield u'state: ' + state
        
        if self.current_index != -1: # i.e., paused or playing
            current_id = self._item_id(self.playlist[self.current_index])
            yield u'song: ' + unicode(self.current_index)
            yield u'songid: ' + unicode(current_id)

        if self.error:
            yield u'error: ' + self.error

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
            raise BPDError(ERROR_ARG, u'volume out of range')
        self.volume = vol
    
    def cmd_crossfade(self, conn, crossfade):
        """Set the number of seconds of crossfading."""
        crossfade = cast_arg(int, crossfade)
        if crossfade < 0:            
            raise BPDError(ERROR_ARG, u'crossfade time must be nonnegative')
    
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
        return self.cmd_move(conn, idx_from, idx_to)
    
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
        return self.cmd_swap(conn, i, j)
    
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
                yield self._item_info(track)
        else:
            try:
                track = self.playlist[index]
            except IndexError:
                raise ArgumentIndexError()
            yield self._item_info(track)
    def cmd_playlistid(self, conn, track_id=-1):
        return self.cmd_playlistinfo(conn, self._id_to_index(track_id))
    
    def cmd_plchanges(self, conn, version):
        """Sends playlist changes since the given version.
        
        This is a "fake" implementation that ignores the version and
        just returns the entire playlist (rather like version=0). This
        seems to satisfy many clients.
        """
        return self.cmd_playlistinfo(conn)
    
    def cmd_plchangesposid(self, conn, version):
        """Like plchanges, but only sends position and id.
        
        Also a dummy implementation.
        """
        for idx, track in enumerate(self.playlist):
            yield u'cpos: ' + unicode(idx)
            yield u'Id: ' + unicode(track.id)
    
    def cmd_currentsong(self, conn):
        """Sends information about the currently-playing song.
        """
        if self.current_index != -1: # -1 means stopped.
            track = self.playlist[self.current_index]
            yield self._item_info(track)
    
    def cmd_next(self, conn):
        """Advance to the next song in the playlist."""
        self.current_index += 1
        if self.current_index >= len(self.playlist):
            # Fallen off the end. Just move to stopped state.
            return self.cmd_stop(conn)
        else:
            return self.cmd_play(conn)
    
    def cmd_previous(self, conn):
        """Step back to the last song."""
        self.current_index -= 1
        if self.current_index < 0:
            return self.cmd_stop(conn)
        else:
            return self.cmd_play(conn)
    
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
                return self.cmd_stop(conn)
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
        return self.cmd_play(conn, index)
    
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
    def cmd_seekid(self, conn, track_id, pos):
        index = self._id_to_index(track_id)
        return self.cmd_seek(conn, index, pos)

    def cmd_profile(self, conn):
        """Memory profiling for debugging."""
        from guppy import hpy
        heap = hpy().heap()
        print heap

class Connection(object):
    """A connection between a client and the server. Handles input and
    output from and to the client.
    """
    def __init__(self, server, sock):
        """Create a new connection for the accepted socket `client`.
        """
        self.server = server
        self.sock = sock
        self.authenticated = False
    
    def send(self, lines):
        """Send lines, which which is either a single string or an
        iterable consisting of strings, to the client. A newline is
        added after every string. Returns a Bluelet event that sends
        the data.
        """
        if isinstance(lines, basestring):
            lines = [lines]
        out = NEWLINE.join(lines) + NEWLINE
        log.debug(out[:-1]) # Don't log trailing newline.
        if isinstance(out, unicode):
            out = out.encode('utf8')
        return self.sock.sendall(out)
    
    def do_command(self, command):
        """A coroutine that runs the given command and sends an
        appropriate response."""
        try:
            yield bluelet.call(command.run(self))
        except BPDError, e:
            # Send the error.
            yield self.send(e.response())
        else:
            # Send success code.
            yield self.send(RESP_OK)
    
    def run(self):
        """Send a greeting to the client and begin processing commands
        as they arrive.
        """
        yield self.send(HELLO)
        
        clist = None # Initially, no command list is being constructed.
        while True:
            line = (yield self.sock.readline()).strip()
            if not line:
                break
            log.debug(line)
               
            if clist is not None:
                # Command list already opened.
                if line == CLIST_END:
                    yield bluelet.call(self.do_command(clist))
                    clist = None # Clear the command list.
                else:
                    clist.append(Command(line))
            
            elif line == CLIST_BEGIN or line == CLIST_VERBOSE_BEGIN:
                # Begin a command list.
                clist = CommandList([], line == CLIST_VERBOSE_BEGIN)
                
            else:
                # Ordinary command.
                try:
                    yield bluelet.call(self.do_command(Command(line)))
                except BPDClose:
                    # Command indicates that the conn should close.
                    self.sock.close()
                    return
    
    @classmethod
    def handler(cls, server):
        def _handle(sock):
            """Creates a new `Connection` and runs it.
            """
            return cls(server, sock).run()
        return _handle

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

        self.args = []
        arg_matches = self.arg_re.findall(s[command_match.end():])
        for match in arg_matches:
            if match[0]:
                # Quoted argument.
                arg = match[0]
                arg = arg.replace('\\"', '"').replace('\\\\', '\\')
            else:
                # Unquoted argument.
                arg = match[1]
            arg = arg.decode('utf8')
            self.args.append(arg)
        
    def run(self, conn):
        """A coroutine that executes the command on the given
        connection.
        """
        # Attempt to get correct command function.
        func_name = 'cmd_' + self.name
        if not hasattr(conn.server, func_name):
            raise BPDError(ERROR_UNKNOWN, u'unknown command', self.name)
        func = getattr(conn.server, func_name)
        
        # Ensure we have permission for this command.
        if conn.server.password and \
                not conn.authenticated and \
                self.name not in SAFE_COMMANDS:
            raise BPDError(ERROR_PERMISSION, u'insufficient privileges')
        
        try:
            args = [conn] + self.args
            results = func(*args)
            if results:
                for data in results:
                    yield conn.send(data)
        
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
            raise BPDError(ERROR_SYSTEM, u'server error', self.name)
            

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
        """Coroutine executing all the commands in this list.
        """
        for i, command in enumerate(self):
            try:
                yield bluelet.call(command.run(conn))
            except BPDError, e:
                # If the command failed, stop executing.
                e.index = i # Give the error the correct index.
                raise e

            # Otherwise, possibly send the output delimeter if we're in a
            # verbose ("OK") command list.
            if self.verbose:
                yield conn.send(RESP_CLIST_VERBOSE)



# A subclass of the basic, protocol-handling server that actually plays
# music.

class Server(BaseServer):
    """An MPD-compatible server using GStreamer to play audio and beets
    to store its library.
    """

    def __init__(self, library, host='', port=DEFAULT_PORT, password=''):
        try:
            from beetsplug.bpd import gstplayer
        except ImportError, e:
            # This is a little hacky, but it's the best I know for now.
            if e.args[0].endswith(' gst'):
                raise NoGstreamerError()
            else:
                raise
        super(Server, self).__init__(host, port, password)
        self.lib = library
        self.player = gstplayer.GstPlayer(self.play_finished)
        self.cmd_update(None)
    
    def run(self):
        self.player.run()
        super(Server, self).run()

    def play_finished(self):
        """A callback invoked every time our player finishes a
        track.
        """
        self.cmd_next(None)
    
    
    # Metadata helper functions.
    
    def _item_info(self, item):
        info_lines = [u'file: ' + self.lib.destination(item, fragment=True),
                      u'Time: ' + unicode(int(item.length)),
                      u'Title: ' + item.title,
                      u'Artist: ' + item.artist,
                      u'Album: ' + item.album,
                      u'Genre: ' + item.genre,
                     ]
        
        track = unicode(item.track)
        if item.tracktotal:
            track += u'/' + unicode(item.tracktotal)
        info_lines.append(u'Track: ' + track)
        
        info_lines.append(u'Date: ' + unicode(item.year))
        
        try:
            pos = self._id_to_index(item.id)
            info_lines.append(u'Pos: ' + unicode(pos))
        except ArgumentNotFoundError:
            # Don't include position if not in playlist.
            pass
        
        info_lines.append(u'Id: ' + unicode(item.id))
        
        return info_lines
        
    def _item_id(self, item):
        return item.id


    # Database updating.

    def cmd_update(self, conn, path=u'/'):
        """Updates the catalog to reflect the current database state.
        """
        # Path is ignored. Also, the real MPD does this asynchronously;
        # this is done inline.
        self.tree = vfs.libtree(self.lib)
        self.updated_time = time.time()


    # Path (directory tree) browsing.

    def _resolve_path(self, path):
        """Returns a VFS node or an item ID located at the path given.
        If the path does not exist, raises a 
        """
        components = path.split(u'/')
        node = self.tree

        for component in components:
            if not component:
                continue

            if isinstance(node, int):
                # We're trying to descend into a file node.
                raise ArgumentNotFoundError()

            if component in node.files:
                node = node.files[component]
            elif component in node.dirs:
                node = node.dirs[component]
            else:
                raise ArgumentNotFoundError()

        return node
    
    def _path_join(self, p1, p2):
        """Smashes together two BPD paths."""
        out = p1 + u'/' + p2
        return out.replace(u'//', u'/').replace(u'//', u'/')
    
    def cmd_lsinfo(self, conn, path=u"/"):
        """Sends info on all the items in the path."""
        node = self._resolve_path(path)
        if isinstance(node, int):
            # Trying to list a track.
            raise BPDError(ERROR_ARG, 'this is not a directory')
        else:
            for name, itemid in node.files.iteritems():
                item = self.lib.get_item(itemid)
                yield self._item_info(item)
            for name, _ in node.dirs.iteritems():
                dirpath = self._path_join(path, name)
                if dirpath.startswith(u"/"):
                    # Strip leading slash (libmpc rejects this).
                    dirpath = dirpath[1:]
                yield u'directory: %s' % dirpath
        
    def _listall(self, basepath, node, info=False):
        """Helper function for recursive listing. If info, show
        tracks' complete info; otherwise, just show items' paths.
        """
        if isinstance(node, int):
            # List a single file.
            if info:
                item = self.lib.get_item(node)
                yield self._item_info(item)
            else:
                yield u'file: ' + basepath
        else:
            # List a directory. Recurse into both directories and files.
            for name, itemid in sorted(node.files.iteritems()):
                newpath = self._path_join(basepath, name)
                # "yield from"
                for v in self._listall(newpath, itemid, info): yield v
            for name, subdir in sorted(node.dirs.iteritems()):
                newpath = self._path_join(basepath, name)
                yield u'directory: ' + newpath
                for v in self._listall(newpath, subdir, info): yield v
    
    def cmd_listall(self, conn, path=u"/"):
        """Send the paths all items in the directory, recursively."""
        return self._listall(path, self._resolve_path(path), False)
    def cmd_listallinfo(self, conn, path=u"/"):
        """Send info on all the items in the directory, recursively."""
        return self._listall(path, self._resolve_path(path), True)
    
    
    # Playlist manipulation.

    def _all_items(self, node):
        """Generator yielding all items under a VFS node.
        """
        if isinstance(node, int):
            # Could be more efficient if we built up all the IDs and
            # then issued a single SELECT.
            yield self.lib.get_item(node)
        else:
            # Recurse into a directory.
            for name, itemid in sorted(node.files.iteritems()):
                # "yield from"
                for v in self._all_items(itemid): yield v
            for name, subdir in sorted(node.dirs.iteritems()):
                for v in self._all_items(subdir): yield v
    
    def _add(self, path, send_id=False):
        """Adds a track or directory to the playlist, specified by the
        path. If `send_id`, write each item's id to the client.
        """
        for item in self._all_items(self._resolve_path(path)):
            self.playlist.append(item)
            if send_id:
                yield u'Id: ' + unicode(item.id)
        self.playlist_version += 1
        
    def cmd_add(self, conn, path):
        """Adds a track or directory to the playlist, specified by a
        path.
        """
        return self._add(path, False)
    
    def cmd_addid(self, conn, path):
        """Same as `cmd_add` but sends an id back to the client."""
        return self._add(path, True)


    # Server info.

    def cmd_status(self, conn):
        for line in super(Server, self).cmd_status(conn):
            yield line
        if self.current_index > -1:
            item = self.playlist[self.current_index]
            
            yield u'bitrate: ' + unicode(item.bitrate/1000)
            #fixme: missing 'audio'
            
            (pos, total) = self.player.time()
            yield u'time: ' + unicode(pos) + u':' + unicode(total)
            
        #fixme: also missing 'updating_db'


    def cmd_stats(self, conn):
        """Sends some statistics about the library."""
        songs, totaltime = beets.library.TrueQuery().count(self.lib)

        statement = 'SELECT COUNT(DISTINCT artist), ' \
                           'COUNT(DISTINCT album) FROM items'
        c = self.lib.conn.execute(statement)
        result = c.fetchone()
        c.close()
        artists, albums = result[0], result[1]

        yield (u'artists: ' + unicode(artists),
               u'albums: ' + unicode(albums),
               u'songs: ' + unicode(songs),
               u'uptime: ' + unicode(int(time.time() - self.startup_time)),
               u'playtime: ' + u'0', #fixme
               u'db_playtime: ' + unicode(int(totaltime)),
               u'db_update: ' + unicode(int(self.updated_time)),
              )


    # Searching.

    tagtype_map = {
        u'Artist':       u'artist',
        u'Album':        u'album',
        u'Title':        u'title',
        u'Track':        u'track',
        # Name?
        u'Genre':        u'genre',
        u'Date':         u'year',
        u'Composer':     u'composer',
        # Performer?
        u'Disc':         u'disc',
        u'filename':     u'path', # Suspect.
    }

    def cmd_tagtypes(self, conn):
        """Returns a list of the metadata (tag) fields available for
        searching.
        """
        for tag in self.tagtype_map:
            yield u'tagtype: ' + tag
    
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
        raise BPDError(ERROR_UNKNOWN, u'no such tagtype')

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
                if tag.lower() == u'any':
                    if any_query_type:
                        queries.append(any_query_type(value))
                    else:
                        raise BPDError(ERROR_UNKNOWN, u'no such tagtype')
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
        for item in self.lib.items(query):
            yield self._item_info(item)
    
    def cmd_find(self, conn, *kv):
        """Perform an exact match for items."""
        query = self._metadata_query(beets.library.MatchQuery,
                                     None,
                                     kv)
        for item in self.lib.items(query):
            yield self._item_info(item)
    
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
            conn.send(show_tag_canon + u': ' + unicode(row[0]))
    
    def cmd_count(self, conn, tag, value):
        """Returns the number and total time of songs matching the
        tag/value query.
        """
        _, key = self._tagtype_lookup(tag)
        query = beets.library.MatchQuery(key, value)
        songs, playtime = query.count(self.lib)
        yield u'songs: ' + unicode(songs)
        yield u'playtime: ' + unicode(int(playtime))
        
    
    # "Outputs." Just a dummy implementation because we don't control
    # any outputs.
    
    def cmd_outputs(self, conn):
        """List the available outputs."""
        yield (u'outputid: 0',
               u'outputname: gstreamer',
               u'outputenabled: 1',
              )
    
    def cmd_enableoutput(self, conn, output_id):
        output_id = cast_arg(int, output_id)
        if output_id != 0:
            raise ArgumentIndexError()
    
    def cmd_disableoutput(self, conn, output_id):
        output_id = cast_arg(int, output_id)
        if output_id == 0:
            raise BPDError(ERROR_ARG, u'cannot disable this output')
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


    # Volume control.

    def cmd_setvol(self, conn, vol):
        vol = cast_arg(int, vol)
        super(Server, self).cmd_setvol(conn, vol)
        self.player.volume = float(vol)/100


# Beets plugin hooks.

class BPDPlugin(BeetsPlugin):
    """Provides the "beet bpd" command for running a music player
    server.
    """
    def start_bpd(self, lib, host, port, password, debug):
        """Starts a BPD server."""
        if debug:
            log.setLevel(logging.DEBUG)
        else:
            log.setLevel(logging.WARNING)
        try:
            Server(lib, host, port, password).run()
        except NoGstreamerError:
            global_log.error('Gstreamer Python bindings not found.')
            global_log.error('Install "python-gst0.10", "py26-gst-python",'
                             'or similar package to use BPD.')

    def commands(self):
        cmd = beets.ui.Subcommand('bpd',
            help='run an MPD-compatible music player server')
        cmd.parser.add_option('-d', '--debug', action='store_true',
            help='dump all MPD traffic to stdout')

        def func(lib, config, opts, args):
            host = args.pop(0) if args else \
                beets.ui.config_val(config, 'bpd', 'host', DEFAULT_HOST)
            port = args.pop(0) if args else \
                beets.ui.config_val(config, 'bpd', 'port', str(DEFAULT_PORT))
            if args:
                raise beets.ui.UserError('too many arguments')
            password = beets.ui.config_val(config, 'bpd', 'password',
                                           DEFAULT_PASSWORD)
            debug = opts.debug or False
            self.start_bpd(lib, host, int(port), password, debug)
        
        cmd.func = func
        return [cmd]
