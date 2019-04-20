# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

"""Tests for BPD's implementation of the MPD protocol.
"""
from __future__ import division, absolute_import, print_function

import unittest
from test.helper import TestHelper

import os
import sys
import multiprocessing as mp
import threading
import socket
import time
import yaml
import tempfile
from contextlib import contextmanager

from beets.util import confit, py3_path
from beetsplug import bpd


# Mock GstPlayer so that the forked process doesn't attempt to import gi:
import mock
import imp
gstplayer = imp.new_module("beetsplug.bpd.gstplayer")
def _gstplayer_play(*_):  # noqa: 42
    bpd.gstplayer._GstPlayer.playing = True
    return mock.DEFAULT
gstplayer._GstPlayer = mock.MagicMock(
    spec_set=[
        "time", "volume", "playing", "run", "play_file", "pause", "stop",
        "seek", "play", "get_decoders",
    ], **{
        'playing': False,
        'volume': 0,
        'time.return_value': (0, 0),
        'play_file.side_effect': _gstplayer_play,
        'play.side_effect': _gstplayer_play,
        'get_decoders.return_value': {'default': ({'audio/mpeg'}, {'mp3'})},
    })
gstplayer.GstPlayer = lambda _: gstplayer._GstPlayer
sys.modules["beetsplug.bpd.gstplayer"] = gstplayer
bpd.gstplayer = gstplayer


class CommandParseTest(unittest.TestCase):
    def test_no_args(self):
        s = r'command'
        c = bpd.Command(s)
        self.assertEqual(c.name, u'command')
        self.assertEqual(c.args, [])

    def test_one_unquoted_arg(self):
        s = r'command hello'
        c = bpd.Command(s)
        self.assertEqual(c.name, u'command')
        self.assertEqual(c.args, [u'hello'])

    def test_two_unquoted_args(self):
        s = r'command hello there'
        c = bpd.Command(s)
        self.assertEqual(c.name, u'command')
        self.assertEqual(c.args, [u'hello', u'there'])

    def test_one_quoted_arg(self):
        s = r'command "hello there"'
        c = bpd.Command(s)
        self.assertEqual(c.name, u'command')
        self.assertEqual(c.args, [u'hello there'])

    def test_heterogenous_args(self):
        s = r'command "hello there" sir'
        c = bpd.Command(s)
        self.assertEqual(c.name, u'command')
        self.assertEqual(c.args, [u'hello there', u'sir'])

    def test_quote_in_arg(self):
        s = r'command "hello \" there"'
        c = bpd.Command(s)
        self.assertEqual(c.args, [u'hello " there'])

    def test_backslash_in_arg(self):
        s = r'command "hello \\ there"'
        c = bpd.Command(s)
        self.assertEqual(c.args, [u'hello \\ there'])


class MPCResponse(object):
    def __init__(self, raw_response):
        body = b'\n'.join(raw_response.split(b'\n')[:-2]).decode('utf-8')
        self.data = self._parse_body(body)
        status = raw_response.split(b'\n')[-2].decode('utf-8')
        self.ok, self.err_data = self._parse_status(status)

    def _parse_status(self, status):
        """ Parses the first response line, which contains the status.
        """
        if status.startswith('OK') or status.startswith('list_OK'):
            return True, None
        elif status.startswith('ACK'):
            code, rest = status[5:].split('@', 1)
            pos, rest = rest.split(']', 1)
            cmd, rest = rest[2:].split('}')
            return False, (int(code), int(pos), cmd, rest[1:])
        else:
            raise RuntimeError('Unexpected status: {!r}'.format(status))

    def _parse_body(self, body):
        """ Messages are generally in the format "header: content".
        Convert them into a dict, storing the values for repeated headers as
        lists of strings, and non-repeated ones as string.
        """
        data = {}
        repeated_headers = set()
        for line in body.split('\n'):
            if not line:
                continue
            if ':' not in line:
                raise RuntimeError('Unexpected line: {!r}'.format(line))
            header, content = line.split(':', 1)
            content = content.lstrip()
            if header in repeated_headers:
                data[header].append(content)
            elif header in data:
                data[header] = [data[header], content]
                repeated_headers.add(header)
            else:
                data[header] = content
        return data


class MPCClient(object):
    def __init__(self, sock, do_hello=True):
        self.sock = sock
        self.buf = b''
        if do_hello:
            hello = self.get_response()
            if not hello.ok:
                raise RuntimeError('Bad hello')

    def get_response(self, force_multi=None):
        """ Wait for a full server response and wrap it in a helper class.
        If the request was a batch request then this will return a list of
        `MPCResponse`s, one for each processed subcommand.
        """

        response = b''
        responses = []
        while True:
            line = self.readline()
            response += line
            if line.startswith(b'OK') or line.startswith(b'ACK'):
                if force_multi or any(responses):
                    if line.startswith(b'ACK'):
                        responses.append(MPCResponse(response))
                        n_remaining = force_multi - len(responses)
                        responses.extend([None] * n_remaining)
                    return responses
                else:
                    return MPCResponse(response)
            if line.startswith(b'list_OK'):
                responses.append(MPCResponse(response))
                response = b''
            elif not line:
                raise RuntimeError('Unexpected response: {!r}'.format(line))

    def serialise_command(self, command, *args):
        cmd = [command.encode('utf-8')]
        for arg in [a.encode('utf-8') for a in args]:
            if b' ' in arg:
                cmd.append(b'"' + arg + b'"')
            else:
                cmd.append(arg)
        return b' '.join(cmd) + b'\n'

    def send_command(self, command, *args):
        request = self.serialise_command(command, *args)
        self.sock.sendall(request)
        return self.get_response()

    def send_commands(self, *commands):
        """ Use MPD command batching to send multiple commands at once.
        Each item of commands is a tuple containing a command followed by
        any arguments.
        """

        requests = []
        for command_and_args in commands:
            command = command_and_args[0]
            args = command_and_args[1:]
            requests.append(self.serialise_command(command, *args))
        requests.insert(0, b'command_list_ok_begin\n')
        requests.append(b'command_list_end\n')
        request = b''.join(requests)
        self.sock.sendall(request)
        return self.get_response(force_multi=len(commands))

    def readline(self, terminator=b'\n', bufsize=1024):
        """ Reads a line of data from the socket.
        """

        while True:
            if terminator in self.buf:
                line, self.buf = self.buf.split(terminator, 1)
                line += terminator
                return line
            self.sock.settimeout(1)
            data = self.sock.recv(bufsize)
            if data:
                self.buf += data
            else:
                line = self.buf
                self.buf = b''
                return line


def start_beets(*args):
    import beets.ui
    beets.ui.main(list(args))


def implements(commands, expectedFailure=False):  # noqa: N803
    def _test(self):
        with self.run_bpd() as client:
            response = client.send_command('commands')
        self._assert_ok(response)
        implemented = response.data['command']
        self.assertEqual(commands.intersection(implemented), commands)
    return unittest.expectedFailure(_test) if expectedFailure else _test


class BPDTestHelper(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_beets(disk=True)
        self.load_plugins('bpd')
        self.item1 = self.add_item(
                title='Track One Title', track=1,
                album='Album Title', artist='Artist Name')
        self.item2 = self.add_item(
                title='Track Two Title', track=2,
                album='Album Title', artist='Artist Name')
        self.lib.add_album([self.item1, self.item2])

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()

    @contextmanager
    def run_bpd(self, host='localhost', port=9876, password=None,
                do_hello=True, second_client=False):
        """ Runs BPD in another process, configured with the same library
        database as we created in the setUp method. Exposes a client that is
        connected to the server, and kills the server at the end.
        """
        # Create a config file:
        config = {
                'pluginpath': [py3_path(self.temp_dir)],
                'plugins': 'bpd',
                'bpd': {'host': host, 'port': port, 'control_port': port + 1},
        }
        if password:
            config['bpd']['password'] = password
        config_file = tempfile.NamedTemporaryFile(
                mode='wb', dir=py3_path(self.temp_dir), suffix='.yaml',
                delete=False)
        config_file.write(
                yaml.dump(config, Dumper=confit.Dumper, encoding='utf-8'))
        config_file.close()

        # Fork and launch BPD in the new process:
        args = (
            '--library', self.config['library'].as_filename(),
            '--directory', py3_path(self.libdir),
            '--config', py3_path(config_file.name),
            'bpd'
        )
        server = mp.Process(target=start_beets, args=args)
        server.start()

        # Wait until the socket is connected:
        sock, sock2 = None, None
        for _ in range(20):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if sock.connect_ex((host, port)) == 0:
                break
            else:
                sock.close()
                time.sleep(0.01)
        else:
            raise RuntimeError('Timed out waiting for the BPD server')

        try:
            if second_client:
                sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock2.connect((host, port))
                yield MPCClient(sock, do_hello), MPCClient(sock2, do_hello)
            else:
                yield MPCClient(sock, do_hello)
        finally:
            sock.close()
            if sock2:
                sock2.close()
            server.terminate()
            server.join(timeout=0.2)

    def _assert_ok(self, *responses):
        for response in responses:
            self.assertTrue(response is not None)
            self.assertTrue(response.ok, 'Response failed: {}'.format(
                response.err_data))

    def _assert_failed(self, response, code, pos=None):
        """ Check that a command failed with a specific error code. If this
        is a list of responses, first check all preceding commands were OK.
        """
        if pos is not None:
            previous_commands = response[0:pos]
            self._assert_ok(*previous_commands)
            response = response[pos]
            self.assertEqual(pos, response.err_data[1])
        self.assertFalse(response.ok)
        if code is not None:
            self.assertEqual(code, response.err_data[0])

    def _bpd_add(self, client, *items, **kwargs):
        """ Add the given item to the BPD playlist or queue.
        """
        paths = ['/'.join([
            item.artist, item.album,
            py3_path(os.path.basename(item.path))]) for item in items]
        playlist = kwargs.get('playlist')
        if playlist:
            commands = [('playlistadd', playlist, path) for path in paths]
        else:
            commands = [('add', path) for path in paths]
        responses = client.send_commands(*commands)
        self._assert_ok(*responses)


class BPDTest(BPDTestHelper):
    def test_server_hello(self):
        with self.run_bpd(do_hello=False) as client:
            self.assertEqual(client.readline(), b'OK MPD 0.14.0\n')

    def test_unknown_cmd(self):
        with self.run_bpd() as client:
            response = client.send_command('notacommand')
        self._assert_failed(response, bpd.ERROR_UNKNOWN)

    def test_unexpected_argument(self):
        with self.run_bpd() as client:
            response = client.send_command('ping', 'extra argument')
        self._assert_failed(response, bpd.ERROR_ARG)

    def test_missing_argument(self):
        with self.run_bpd() as client:
            response = client.send_command('add')
        self._assert_failed(response, bpd.ERROR_ARG)

    def test_system_error(self):
        with self.run_bpd() as client:
            response = client.send_command('crash_TypeError')
        self._assert_failed(response, bpd.ERROR_SYSTEM)

    def test_empty_request(self):
        with self.run_bpd() as client:
            response = client.send_command('')
        self._assert_failed(response, bpd.ERROR_UNKNOWN)


class BPDQueryTest(BPDTestHelper):
    test_implements_query = implements({
            'clearerror', 'currentsong', 'stats',
            })

    def test_cmd_status(self):
        with self.run_bpd() as client:
            self._bpd_add(client, self.item1, self.item2)
            responses = client.send_commands(
                    ('status',),
                    ('play',),
                    ('status',))
        self._assert_ok(*responses)
        fields_not_playing = {
            'repeat', 'random', 'single', 'consume', 'playlist',
            'playlistlength', 'mixrampdb', 'state',
            'volume'
        }
        self.assertEqual(fields_not_playing, set(responses[0].data.keys()))
        fields_playing = fields_not_playing | {
            'song', 'songid', 'time', 'elapsed', 'bitrate', 'duration', 'audio'
        }
        self.assertEqual(fields_playing, set(responses[2].data.keys()))

    def test_cmd_idle(self):
        def _toggle(c):
            for _ in range(3):
                rs = c.send_commands(('play',), ('pause',))
                # time.sleep(0.05)  # uncomment if test is flaky
                if any(not r.ok for r in rs):
                    raise RuntimeError('Toggler failed')
        with self.run_bpd(second_client=True) as (client, client2):
            self._bpd_add(client, self.item1, self.item2)
            toggler = threading.Thread(target=_toggle, args=(client2,))
            toggler.start()
            # Idling will hang until the toggler thread changes the play state.
            # Since the client sockets have a 1s timeout set at worst this will
            # raise a socket.timeout and fail the test if the toggler thread
            # manages to finish before the idle command is sent here.
            response = client.send_command('idle', 'player')
            toggler.join()
        self._assert_ok(response)

    def test_cmd_idle_with_pending(self):
        with self.run_bpd(second_client=True) as (client, client2):
            response1 = client.send_command('random', '1')
            response2 = client2.send_command('idle')
        self._assert_ok(response1, response2)
        self.assertEqual('options', response2.data['changed'])

    def test_cmd_noidle(self):
        with self.run_bpd() as client:
            # Manually send a command without reading a response.
            request = client.serialise_command('idle')
            client.sock.sendall(request)
            time.sleep(0.01)
            response = client.send_command('noidle')
        self._assert_ok(response)


class BPDPlaybackTest(BPDTestHelper):
    test_implements_playback = implements({
            'random',
            })

    def test_cmd_consume(self):
        with self.run_bpd() as client:
            self._bpd_add(client, self.item1, self.item2)
            responses = client.send_commands(
                    ('consume', '0'),
                    ('playlistinfo',),
                    ('next',),
                    ('playlistinfo',),
                    ('consume', '1'),
                    ('playlistinfo',),
                    ('play', '0'),
                    ('next',),
                    ('playlistinfo',),
                    ('status',))
        self._assert_ok(*responses)
        self.assertEqual(responses[1].data['Id'], responses[3].data['Id'])
        self.assertEqual(['1', '2'], responses[5].data['Id'])
        self.assertEqual('2', responses[8].data['Id'])
        self.assertEqual('1', responses[9].data['consume'])
        self.assertEqual('play', responses[9].data['state'])

    def test_cmd_consume_in_reverse(self):
        with self.run_bpd() as client:
            self._bpd_add(client, self.item1, self.item2)
            responses = client.send_commands(
                    ('consume', '1'),
                    ('play', '1'),
                    ('playlistinfo',),
                    ('previous',),
                    ('playlistinfo',),
                    ('status',))
        self._assert_ok(*responses)
        self.assertEqual(['1', '2'], responses[2].data['Id'])
        self.assertEqual('1', responses[4].data['Id'])
        self.assertEqual('play', responses[5].data['state'])

    def test_cmd_single(self):
        with self.run_bpd() as client:
            self._bpd_add(client, self.item1, self.item2)
            responses = client.send_commands(
                    ('status',),
                    ('single', '1'),
                    ('play',),
                    ('status',),
                    ('next',),
                    ('status',))
        self._assert_ok(*responses)
        self.assertEqual('0', responses[0].data['single'])
        self.assertEqual('1', responses[3].data['single'])
        self.assertEqual('play', responses[3].data['state'])
        self.assertEqual('stop', responses[5].data['state'])

    def test_cmd_repeat(self):
        with self.run_bpd() as client:
            self._bpd_add(client, self.item1, self.item2)
            responses = client.send_commands(
                    ('repeat', '1'),
                    ('play',),
                    ('currentsong',),
                    ('next',),
                    ('currentsong',),
                    ('next',),
                    ('currentsong',))
        self._assert_ok(*responses)
        self.assertEqual('1', responses[2].data['Id'])
        self.assertEqual('2', responses[4].data['Id'])
        self.assertEqual('1', responses[6].data['Id'])

    def test_cmd_repeat_with_single(self):
        with self.run_bpd() as client:
            self._bpd_add(client, self.item1, self.item2)
            responses = client.send_commands(
                    ('repeat', '1'),
                    ('single', '1'),
                    ('play',),
                    ('currentsong',),
                    ('next',),
                    ('status',),
                    ('currentsong',))
        self._assert_ok(*responses)
        self.assertEqual('1', responses[3].data['Id'])
        self.assertEqual('play', responses[5].data['state'])
        self.assertEqual('1', responses[6].data['Id'])

    def test_cmd_repeat_in_reverse(self):
        with self.run_bpd() as client:
            self._bpd_add(client, self.item1, self.item2)
            responses = client.send_commands(
                    ('repeat', '1'),
                    ('play',),
                    ('currentsong',),
                    ('previous',),
                    ('currentsong',))
        self._assert_ok(*responses)
        self.assertEqual('1', responses[2].data['Id'])
        self.assertEqual('2', responses[4].data['Id'])

    def test_cmd_repeat_with_single_in_reverse(self):
        with self.run_bpd() as client:
            self._bpd_add(client, self.item1, self.item2)
            responses = client.send_commands(
                    ('repeat', '1'),
                    ('single', '1'),
                    ('play',),
                    ('currentsong',),
                    ('previous',),
                    ('status',),
                    ('currentsong',))
        self._assert_ok(*responses)
        self.assertEqual('1', responses[3].data['Id'])
        self.assertEqual('play', responses[5].data['state'])
        self.assertEqual('1', responses[6].data['Id'])

    def test_cmd_crossfade(self):
        with self.run_bpd() as client:
            responses = client.send_commands(
                    ('status',),
                    ('crossfade', '123'),
                    ('status',),
                    ('crossfade', '-2'))
            response = client.send_command('crossfade', '0.5')
        self._assert_failed(responses, bpd.ERROR_ARG, pos=3)
        self._assert_failed(response, bpd.ERROR_ARG)
        self.assertNotIn('xfade', responses[0].data)
        self.assertAlmostEqual(123, int(responses[2].data['xfade']))

    def test_cmd_mixrampdb(self):
        with self.run_bpd() as client:
            responses = client.send_commands(
                    ('mixrampdb', '-17'),
                    ('status',))
        self._assert_ok(*responses)
        self.assertAlmostEqual(-17, float(responses[1].data['mixrampdb']))

    def test_cmd_mixrampdelay(self):
        with self.run_bpd() as client:
            responses = client.send_commands(
                    ('mixrampdelay', '2'),
                    ('status',),
                    ('mixrampdelay', 'nan'),
                    ('status',),
                    ('mixrampdelay', '-2'))
        self._assert_failed(responses, bpd.ERROR_ARG, pos=4)
        self.assertAlmostEqual(2, float(responses[1].data['mixrampdelay']))
        self.assertNotIn('mixrampdelay', responses[3].data)

    def test_cmd_setvol(self):
        with self.run_bpd() as client:
            responses = client.send_commands(
                    ('setvol', '67'),
                    ('status',),
                    ('setvol', '32'),
                    ('status',),
                    ('setvol', '101'))
        self._assert_failed(responses, bpd.ERROR_ARG, pos=4)
        self.assertEqual('67', responses[1].data['volume'])
        self.assertEqual('32', responses[3].data['volume'])

    def test_cmd_volume(self):
        with self.run_bpd() as client:
            response = client.send_command('volume', '10')
        self._assert_failed(response, bpd.ERROR_SYSTEM)

    def test_cmd_replay_gain(self):
        with self.run_bpd() as client:
            responses = client.send_commands(
                    ('replay_gain_mode', 'track'),
                    ('replay_gain_status',),
                    ('replay_gain_mode', 'notanoption'))
        self._assert_failed(responses, bpd.ERROR_ARG, pos=2)
        self.assertAlmostEqual('track', responses[1].data['replay_gain_mode'])


class BPDControlTest(BPDTestHelper):
    test_implements_control = implements({
            'pause', 'playid', 'seek',
            'seekid', 'seekcur', 'stop',
            }, expectedFailure=True)

    def test_cmd_play(self):
        with self.run_bpd() as client:
            self._bpd_add(client, self.item1, self.item2)
            responses = client.send_commands(
                    ('status',),
                    ('play',),
                    ('status',),
                    ('play', '1'),
                    ('currentsong',))
        self._assert_ok(*responses)
        self.assertEqual('stop', responses[0].data['state'])
        self.assertEqual('play', responses[2].data['state'])
        self.assertEqual('2', responses[4].data['Id'])

    def test_cmd_next(self):
        with self.run_bpd() as client:
            self._bpd_add(client, self.item1, self.item2)
            responses = client.send_commands(
                    ('play',),
                    ('currentsong',),
                    ('next',),
                    ('currentsong',),
                    ('next',),
                    ('status',))
        self._assert_ok(*responses)
        self.assertEqual('1', responses[1].data['Id'])
        self.assertEqual('2', responses[3].data['Id'])
        self.assertEqual('stop', responses[5].data['state'])

    def test_cmd_previous(self):
        with self.run_bpd() as client:
            self._bpd_add(client, self.item1, self.item2)
            responses = client.send_commands(
                    ('play', '1'),
                    ('currentsong',),
                    ('previous',),
                    ('currentsong',),
                    ('previous',),
                    ('status',),
                    ('currentsong',))
        self._assert_ok(*responses)
        self.assertEqual('2', responses[1].data['Id'])
        self.assertEqual('1', responses[3].data['Id'])
        self.assertEqual('play', responses[5].data['state'])
        self.assertEqual('1', responses[6].data['Id'])


class BPDQueueTest(BPDTestHelper):
    test_implements_queue = implements({
            'addid', 'clear', 'delete', 'deleteid', 'move',
            'moveid', 'playlist', 'playlistfind', 'playlistid',
            'playlistsearch', 'plchanges',
            'plchangesposid', 'prio', 'prioid', 'rangeid', 'shuffle',
            'swap', 'swapid', 'addtagid', 'cleartagid',
            }, expectedFailure=True)

    def test_cmd_add(self):
        with self.run_bpd() as client:
            self._bpd_add(client, self.item1)

    def test_cmd_playlistinfo(self):
        with self.run_bpd() as client:
            self._bpd_add(client, self.item1)
            responses = client.send_commands(
                    ('playlistinfo',),
                    ('playlistinfo', '0'),
                    ('playlistinfo', '200'))
        self._assert_failed(responses, bpd.ERROR_ARG, pos=2)


class BPDPlaylistsTest(BPDTestHelper):
    test_implements_playlists = implements({'playlistadd'})

    def test_cmd_listplaylist(self):
        with self.run_bpd() as client:
            response = client.send_command('listplaylist', 'anything')
        self._assert_failed(response, bpd.ERROR_NO_EXIST)

    def test_cmd_listplaylistinfo(self):
        with self.run_bpd() as client:
            response = client.send_command('listplaylistinfo', 'anything')
        self._assert_failed(response, bpd.ERROR_NO_EXIST)

    def test_cmd_listplaylists(self):
        with self.run_bpd() as client:
            response = client.send_command('listplaylists')
        self._assert_failed(response, bpd.ERROR_UNKNOWN)

    def test_cmd_load(self):
        with self.run_bpd() as client:
            response = client.send_command('load', 'anything')
        self._assert_failed(response, bpd.ERROR_NO_EXIST)

    @unittest.skip
    def test_cmd_playlistadd(self):
        with self.run_bpd() as client:
            self._bpd_add(client, self.item1, playlist='anything')

    def test_cmd_playlistclear(self):
        with self.run_bpd() as client:
            response = client.send_command('playlistclear', 'anything')
        self._assert_failed(response, bpd.ERROR_UNKNOWN)

    def test_cmd_playlistdelete(self):
        with self.run_bpd() as client:
            response = client.send_command('playlistdelete', 'anything', '0')
        self._assert_failed(response, bpd.ERROR_UNKNOWN)

    def test_cmd_playlistmove(self):
        with self.run_bpd() as client:
            response = client.send_command(
                    'playlistmove', 'anything', '0', '1')
        self._assert_failed(response, bpd.ERROR_UNKNOWN)

    def test_cmd_rename(self):
        with self.run_bpd() as client:
            response = client.send_command('rename', 'anything', 'newname')
        self._assert_failed(response, bpd.ERROR_UNKNOWN)

    def test_cmd_rm(self):
        with self.run_bpd() as client:
            response = client.send_command('rm', 'anything')
        self._assert_failed(response, bpd.ERROR_UNKNOWN)

    def test_cmd_save(self):
        with self.run_bpd() as client:
            self._bpd_add(client, self.item1)
            response = client.send_command('save', 'newplaylist')
        self._assert_failed(response, bpd.ERROR_UNKNOWN)


class BPDDatabaseTest(BPDTestHelper):
    test_implements_database = implements({
            'albumart', 'find', 'findadd', 'listall',
            'listallinfo', 'listfiles', 'readcomments',
            'searchadd', 'searchaddpl', 'update', 'rescan',
            }, expectedFailure=True)

    def test_cmd_search(self):
        with self.run_bpd() as client:
            response = client.send_command('search', 'track', '1')
        self._assert_ok(response)
        self.assertEqual(self.item1.title, response.data['Title'])

    def test_cmd_list(self):
        with self.run_bpd() as client:
            responses = client.send_commands(
                    ('list', 'album'),
                    ('list', 'track'),
                    ('list', 'album', 'artist', 'Artist Name', 'track'))
        self._assert_failed(responses, bpd.ERROR_ARG, pos=2)
        self.assertEqual('Album Title', responses[0].data['Album'])
        self.assertEqual(['1', '2'], responses[1].data['Track'])

    def test_cmd_list_three_arg_form(self):
        with self.run_bpd() as client:
            responses = client.send_commands(
                    ('list', 'album', 'artist', 'Artist Name'),
                    ('list', 'album', 'Artist Name'),
                    ('list', 'track', 'Artist Name'))
        self._assert_failed(responses, bpd.ERROR_ARG, pos=2)
        self.assertEqual(responses[0].data, responses[1].data)

    def test_cmd_lsinfo(self):
        with self.run_bpd() as client:
            response1 = client.send_command('lsinfo')
            self._assert_ok(response1)
            response2 = client.send_command(
                    'lsinfo', response1.data['directory'])
            self._assert_ok(response2)
            response3 = client.send_command(
                    'lsinfo', response2.data['directory'])
            self._assert_ok(response3)
        self.assertIn(self.item1.title, response3.data['Title'])

    def test_cmd_count(self):
        with self.run_bpd() as client:
            response = client.send_command('count', 'track', '1')
        self._assert_ok(response)
        self.assertEqual('1', response.data['songs'])
        self.assertEqual('0', response.data['playtime'])


class BPDMountsTest(BPDTestHelper):
    test_implements_mounts = implements({
            'mount', 'unmount', 'listmounts', 'listneighbors',
            }, expectedFailure=True)


class BPDStickerTest(BPDTestHelper):
    test_implements_stickers = implements({
            'sticker',
            }, expectedFailure=True)


class BPDConnectionTest(BPDTestHelper):
    test_implements_connection = implements({
            'close', 'kill', 'tagtypes',
            })

    def test_cmd_password(self):
        with self.run_bpd(password='abc123') as client:
            response = client.send_command('status')
            self._assert_failed(response, bpd.ERROR_PERMISSION)

            response = client.send_command('password', 'wrong')
            self._assert_failed(response, bpd.ERROR_PASSWORD)

            responses = client.send_commands(
                    ('password', 'abc123'),
                    ('status',))
        self._assert_ok(*responses)

    def test_cmd_ping(self):
        with self.run_bpd() as client:
            response = client.send_command('ping')
        self._assert_ok(response)

    @unittest.skip
    def test_cmd_tagtypes(self):
        with self.run_bpd() as client:
            response = client.send_command('tagtypes')
        self._assert_ok(response)
        self.assertEqual({
            'Artist', 'ArtistSort', 'Album', 'AlbumSort', 'AlbumArtist',
            'AlbumArtistSort', 'Title', 'Track', 'Name', 'Genre', 'Date',
            'Composer', 'Performer', 'Comment', 'Disc', 'Label',
            'OriginalDate', 'MUSICBRAINZ_ARTISTID', 'MUSICBRAINZ_ALBUMID',
            'MUSICBRAINZ_ALBUMARTISTID', 'MUSICBRAINZ_TRACKID',
            'MUSICBRAINZ_RELEASETRACKID', 'MUSICBRAINZ_WORKID',
            }, set(response.data['tag']))

    @unittest.skip
    def test_tagtypes_mask(self):
        with self.run_bpd() as client:
            response = client.send_command('tagtypes', 'clear')
        self._assert_ok(response)


class BPDPartitionTest(BPDTestHelper):
    test_implements_partitions = implements({
            'partition', 'listpartitions', 'newpartition',
            }, expectedFailure=True)


class BPDDeviceTest(BPDTestHelper):
    test_implements_devices = implements({
            'disableoutput', 'enableoutput', 'toggleoutput', 'outputs',
            }, expectedFailure=True)


class BPDReflectionTest(BPDTestHelper):
    test_implements_reflection = implements({
        'config', 'commands', 'notcommands', 'urlhandlers',
    }, expectedFailure=True)

    def test_cmd_decoders(self):
        with self.run_bpd() as client:
            response = client.send_command('decoders')
        self._assert_ok(response)
        self.assertEqual('default', response.data['plugin'])
        self.assertEqual('mp3', response.data['suffix'])
        self.assertEqual('audio/mpeg', response.data['mime_type'])


class BPDPeersTest(BPDTestHelper):
    test_implements_peers = implements({
            'subscribe', 'unsubscribe', 'channels', 'readmessages',
            'sendmessage',
            }, expectedFailure=True)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
