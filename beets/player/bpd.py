#!/usr/bin/env python

"""A clone of the Music Player Daemon (MPD) that plays music from a
Beets library. Attempts to implement a compatible protocol to allow
use of the wide range of MPD clients.
"""

import eventlet.api
import re
from string import Template
from beets import Library
import sys


DEFAULT_PORT = 6600
PROTOCOL_VERSION = '0.12.2'
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


def debug(msg):
    print >>sys.stderr, msg

class BPDError(Exception):
    """An error that should be exposed to the client to the BPD
    server.
    """
    def __init__(self, code, message):
        self.code = code
        self.message = message
        
    def response(self, cmd):
        """Returns an ErrorResponse for the exception as a response
        to the given command.
        """
        return ErrorResponse(self.code, cmd.name, self.message)

def make_bpd_error(self, s_code, s_message):
    """Create a BPDError subclass for a static code and message.
    """
    class NewBPDError(BPDError):
        code = s_code
        message = s_message
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


class Server(object):
    """A MPD-compatible music player server.
    
    The functions with the `cmd_` prefix are invoked in response to
    client commands. For instance, if the client says `status`,
    `cmd_status` will be invoked. The arguments to the client's commands
    are used as function arguments (*args). The functions should return
    a `Response` object (or None to indicate an empty but successful
    response). They may also raise BPDError exceptions to report errors.
    
    This is a generic superclass and doesn't support many commands.
    """
    
    def __init__(self, host, port=DEFAULT_PORT):
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
    
    def run(self):
        """Block and start listening for connections from clients. An
        interrupt (^C) closes the server.
        """
        try:
            self.listener = eventlet.api.tcp_listener((self.host, self.port))
            while True:
                sock, address = self.listener.accept()
                eventlet.api.spawn(Connection.handle, sock, self)
        except KeyboardInterrupt:
            pass # ^C ends the server.

    def _generic_status(self):
        """Returns some status information for use with an
        implementation of cmd_status.
        
        Gives a list of response-lines for: volume, repeat, random,
        playlist, playlistlength, and xfade.
        """
        return ['volume: ' + str(self.volume),
                'repeat: ' + str(int(self.repeat)),
                'random: ' + str(int(self.random)),
                'playlist: ' + str(self.playlist_version),
                'playlistlength: ' + str(len(self.playlist)),
                'xfade: ' + str(self.crossfade),
               ]

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
        for index, track in self.playlist:
            if _item_id(track) == track_id:
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
                out.append('command: ' + key[4:])
        return SuccessResponse(out)
    
    def cmd_notcommands(self):
        """Lists all unavailable commands. Because there's currently no
        authentication, returns no commands.
        """
        pass
    
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
        return self.cmd_move(idx_from, idx_to)
    
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
        return self.cmd_swap(i, j)
    
    def cmd_urlhandlers(self):
        """Indicates supported URL schemes. None by default."""
        pass
    
    def _items_info(self, l):
        """Gets info (using _item_info) for an entire list (e.g.,
        the playlist).
        """
        info = []
        for track in l:
            info += self._item_info(track)
        return SuccessReponse(info)
    
    def cmd_playlistinfo(self, index=-1):
        """Gives metadata information about the entire playlist or a
        single track, given by its index.
        """
        index = cast_arg(int, index)
        if index == -1:
            return self._items_info(self.playlist)
        else:
            try:
                track = self.playlist[index]
            except IndexError:
                raise ArgumentIndexError()
            return SuccessReponse(self._item_info(track))
    def cmd_playlistid(self, track_id=-1):
        return self.cmd_playlistinfo(self._id_to_index(track_id))
        
    

class Connection(object):
    """A connection between a client and the server. Handles input and
    output from and to the client.
    """
    
    def __init__(self, client, server):
        """Create a new connection for the accepted socket `client`.
        """
        self.client, self.server = client, server
    
    def send(self, data):
        """Send data, which is either a string or an iterable
        consisting of strings, to the client. A newline is added after
        every string.
        """
        if isinstance(data, basestring): # Passed a single string.
            lines = (data,)
        else: # Passed an iterable of strings (for instance, a Response).
            lines = data
        
        for line in lines:
            debug(line)
            self.client.sendall(line + NEWLINE)
    
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
    
    def run(self):
        """Send a greeting to the client and begin processing commands
        as they arrive. Blocks until the client disconnects.
        """
        self.send(HELLO)
        
        clist = None # Initially, no command list is being constructed.
        for line in self.lines():
            debug(line)
               
            if clist is not None:
                # Command list already opened.
                if line == CLIST_END:
                    self.send(clist.run(self.server))
                    clist = None
                else:
                    clist.append(Command(line))
            
            elif line == CLIST_BEGIN or line == CLIST_VERBOSE_BEGIN:
                # Begin a command list.
                clist = CommandList([], line == CLIST_VERBOSE_BEGIN)
                
            else:
                # Ordinary command.
                try:
                    self.send(Command(line).run(self.server))
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
        
    def run(self, server):
        """Executes the command on the given `Sever`, returning a
        `Response` object.
        """
        func_name = 'cmd_' + self.name
        if hasattr(server, func_name):
            try:
                response = getattr(server, func_name)(*self.args)
            
            except BPDError as e:
                # An exposed error. Send it to the client.
                return e.response(self)
            
            except BPDClose:
                # An indication that the connection should close. Send
                # it on the Connection.
                raise
            
            except Exception as e:
                # An "unintentional" error. Hide it from the client.
                debug(e)
                return ErrorResponse(ERROR_SYSTEM, self.name, 'server error')
            
            if response is None:
                # Assume success if nothing is returned.
                return SuccessResponse()
            else:
                return response
                
        else:
            return ErrorResponse(ERROR_UNKNOWN, self.name, 'unknown command')

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

    def run(self, server):
        """Execute all the commands in this list, returning a list of
        strings to be sent as a response.
        """
        out = []

        for i, command in enumerate(self):
            resp = command.run(server)
            out.extend(resp.items)

            # If the command failed, stop executing and send the completion
            # code for this command.
            if isinstance(resp, ErrorResponse):
                resp.index = i # Give the error the correct index.
                break

            # Otherwise, possibly send the output delimeter if we're in a
            # verbose ("OK") command list.
            if self.verbose:
                out.append(RESP_CLIST_VERBOSE)

        # Give a completion code matching that of the last command (correct
        # for both success and failure).
        out.append(resp.completion())

        return out

class Response(object):
    """A result of executing a single `Command`. A `Response` is
    iterable and consists of zero or more lines of response data
    (`items`) and a completion code. It is an abstract class.
    """
    def __init__(self, items=None):
        """Create a response consisting of the given lines of
        response messages.
        """
        self.items = (items if items else [])
    def __iter__(self):
        """Iterate through the `Response`'s items and then its
        completion code."""
        return iter(self.items + [self.completion()])
    def completion(self):
        """Returns the completion code of the response."""
        raise NotImplementedError

class ErrorResponse(Response):
    """A result of a command that fails.
    """
    template = Template('$resp [$code@$index] {$cmd_name} $message')
    
    def __init__(self, code, cmd_name, message, index=0, items=None):
        """Create a new `ErrorResponse` for error code `code`
        resulting from command with name `cmd_name`. `message` is an
        explanatory error message, `index` is the index of a command
        in a command list, and `items` is the additional data to be
        send to the client.
        """
        super(ErrorResponse, self).__init__(items)
        self.code, self.index, self.cmd_name, self.message = \
             code,      index,      cmd_name,      message
    
    def completion(self):
        return self.template.substitute({'resp':     RESP_ERR,
                                         'code':     self.code,
                                         'index':    self.index,
                                         'cmd_name': self.cmd_name,
                                         'message':  self.message
                                       })

class SuccessResponse(Response):
    """A result of a command that succeeds.
    """
    def completion(self):
        return RESP_OK


class BGServer(Server):
    """A `Server` using GStreamer to play audio and beets to store its
    library.
    """

    def __init__(self, library, host='127.0.0.1', port=DEFAULT_PORT):
        import gstplayer
        super(BGServer, self).__init__(host, port)
        self.library = library
        self.player = gstplayer.GstPlayer()
    
    def run(self):
        super(BGServer, self).run()
        self.player.run()
    
    def _item_info(self, item):
        info_lines = ['file: ' + item.path,
                      'Time: ' + '100', #fixme
                      'Artist: ' + item.artist,
                      'Title: ' + item.title,
                      'Album: ' + item.album]
        
        track = str(item.track)
        if item.tracktotal:
            track += '/' + str(item.tracktotal)
        info_lines.append('Track: ' + track)
        
        info_lines += ['Date: ' + str(item.year),
                       'Genre: ' + item.genre]
        
        try:
            pos = self._id_to_index(self.item.id)
            info_lines.append('Pos: ' + str(pos))
        except ArgumentNotFoundError:
            # Don't include position if not in playlist.
            pass
        
        info_lines.append('Id: ' + str(item.id))
        
        return info_lines
        
    def _item_id(self, item):
        return item.id
    
    def cmd_status(self):
        statuses = self._generic_status()
        if self.player.playing:
            statuses += ['state: play']
        else:
            statuses += ['state: pause']
        return SuccessResponse(statuses)
    
    def cmd_lsinfo(self, path="/"):
        if path != "/":
            raise BPDError(ERROR_NO_EXIST, 'cannot list paths other than /')
        return _items_info(self.lib.get())
    
    def cmd_search(self, key, value):
        if key == 'filename':
            key = 'path'
        query = key + ':' + value + ''
        return _items_info(self.lib.get(query))


if __name__ == '__main__':
    BGServer(Library('library.blb')).run()
