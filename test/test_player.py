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
def _gstplayer_play(_):  # noqa: 42
    bpd.gstplayer._GstPlayer.playing = True
    return mock.DEFAULT
gstplayer._GstPlayer = mock.MagicMock(
    spec_set=[
        "time", "volume", "playing", "run", "play_file", "pause", "stop",
        "seek"
    ], **{
        'playing': False,
        'volume': 0.0,
        'time.return_value': (0, 0),
        'play_file.side_effect': _gstplayer_play,
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
        self.status = raw_response.split(b'\n')[-2].decode('utf-8')
        self.ok = (self.status.startswith('OK') or
                   self.status.startswith('list_OK'))
        self.err = self.status.startswith('ACK')

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
                raise RuntimeError('Bad hello: {}'.format(hello.status))

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
        return self.get_response(force_multi=True)

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
        implemented = response.data['command']
        self.assertEqual(commands.intersection(implemented), commands)
    return unittest.expectedFailure(_test) if expectedFailure else _test


class BPDTest(unittest.TestCase, TestHelper):
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
                do_hello=True):
        """ Runs BPD in another process, configured with the same library
        database as we created in the setUp method. Exposes a client that is
        connected to the server, and kills the server at the end.
        """
        # Create a config file:
        config = {
                'pluginpath': [py3_path(self.temp_dir)],
                'plugins': 'bpd',
                'bpd': {'host': host, 'port': port},
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
        sock = None
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
            yield MPCClient(sock, do_hello)
        finally:
            sock.close()
            server.terminate()
            server.join(timeout=0.2)

    def test_server_hello(self):
        with self.run_bpd(do_hello=False) as client:
            self.assertEqual(client.readline(), b'OK MPD 0.13.0\n')

    test_implements_query = implements({
            'clearerror', 'currentsong', 'idle', 'status', 'stats',
            }, expectedFailure=True)

    test_implements_playback = implements({
            'consume', 'crossfade', 'mixrampd', 'mixrampdelay', 'random',
            'repeat', 'setvol', 'single', 'replay_gain_mode',
            'replay_gain_status', 'volume',
            }, expectedFailure=True)

    test_implements_control = implements({
            'next', 'pause', 'play', 'playid', 'previous', 'seek',
            'seekid', 'seekcur', 'stop',
            }, expectedFailure=True)

    def bpd_add_item(self, client, item):
        """ Add the given item to the BPD playlist
        """
        name = py3_path(os.path.basename(item.path))
        path = '/'.join([item.artist, item.album, name])
        response = client.send_command('add', path)
        self.assertTrue(response.ok)

    def test_cmd_play(self):
        with self.run_bpd() as client:
            self.bpd_add_item(client, self.item1)
            responses = client.send_commands(
                    ('status',),
                    ('play',),
                    ('status',))
        self.assertEqual('stop', responses[0].data['state'])
        self.assertTrue(responses[1].ok)
        self.assertEqual('play', responses[2].data['state'])

    test_implements_queue = implements({
            'add', 'addid', 'clear', 'delete', 'deleteid', 'move',
            'moveid', 'playlist', 'playlistfind', 'playlistid',
            'playlistinfo', 'playlistsearch', 'plchanges',
            'plchangesposid', 'prio', 'prioid', 'rangeid', 'shuffle',
            'swap', 'swapid', 'addtagid', 'cleartagid',
            }, expectedFailure=True)

    def test_cmd_add(self):
        with self.run_bpd() as client:
            self.bpd_add_item(client, self.item1)

    def test_cmd_playlistinfo(self):
        with self.run_bpd() as client:
            self.bpd_add_item(client, self.item1)
            responses = client.send_commands(
                    ('playlistinfo',),
                    ('playlistinfo', '0'))
            response = client.send_command('playlistinfo', '200')

        self.assertTrue(responses[0].ok)
        self.assertTrue(responses[1].ok)

        self.assertTrue(response.err)
        self.assertEqual(
                'ACK [2@0] {playlistinfo} argument out of range',
                response.status)

    test_implements_playlists = implements({
            'listplaylist', 'listplaylistinfo', 'listplaylists', 'load',
            'playlistadd', 'playlistclear', 'playlistdelete',
            'playlistmove', 'rename', 'rm', 'save',
            }, expectedFailure=True)

    test_implements_database = implements({
            'albumart', 'count', 'find', 'findadd', 'list', 'listall',
            'listallinfo', 'listfiles', 'lsinfo', 'readcomments',
            'search', 'searchadd', 'searchaddpl', 'update', 'rescan',
            }, expectedFailure=True)

    def test_cmd_search(self):
        with self.run_bpd() as client:
            response = client.send_command('search', 'track', '1')
        self.assertEqual(self.item1.title, response.data['Title'])

    def test_cmd_list_simple(self):
        with self.run_bpd() as client:
            response1 = client.send_command('list', 'album')
            response2 = client.send_command('list', 'track')
        self.assertEqual('Album Title', response1.data['Album'])
        self.assertEqual(['1', '2'], response2.data['Track'])

    def test_cmd_lsinfo(self):
        with self.run_bpd() as client:
            response1 = client.send_command('lsinfo')
            response2 = client.send_command(
                    'lsinfo', response1.data['directory'])
            response3 = client.send_command(
                    'lsinfo', response2.data['directory'])
        self.assertIn(self.item1.title, response3.data['Title'])

    def test_cmd_count(self):
        with self.run_bpd() as client:
            response = client.send_command('count', 'track', '1')
        self.assertEqual('1', response.data['songs'])
        self.assertEqual('0', response.data['playtime'])

    test_implements_mounts = implements({
            'mount', 'unmount', 'listmounts', 'listneighbors',
            }, expectedFailure=True)

    test_implements_stickers = implements({
            'sticker',
            }, expectedFailure=True)

    test_implements_connection = implements({
            'close', 'kill', 'password', 'ping', 'tagtypes',
            })

    def test_cmd_password(self):
        with self.run_bpd(password='abc123') as client:
            response = client.send_command('status')
            self.assertTrue(response.err)
            self.assertEqual(response.status,
                             'ACK [4@0] {} insufficient privileges')

            response = client.send_command('password', 'wrong')
            self.assertTrue(response.err)
            self.assertEqual(response.status,
                             'ACK [3@0] {password} incorrect password')

            response = client.send_command('password', 'abc123')
            self.assertTrue(response.ok)
            response = client.send_command('status')
            self.assertTrue(response.ok)

    def test_cmd_ping(self):
        with self.run_bpd() as client:
            response = client.send_command('ping')
        self.assertTrue(response.ok)

    @unittest.expectedFailure
    def test_cmd_tagtypes(self):
        with self.run_bpd() as client:
            response = client.send_command('tagtypes')
        self.assertEqual({
            'Artist', 'ArtistSort', 'Album', 'AlbumSort', 'AlbumArtist',
            'AlbumArtistSort', 'Title', 'Track', 'Name', 'Genre', 'Date',
            'Composer', 'Performer', 'Comment', 'Disc', 'Label',
            'OriginalDate', 'MUSICBRAINZ_ARTISTID', 'MUSICBRAINZ_ALBUMID',
            'MUSICBRAINZ_ALBUMARTISTID', 'MUSICBRAINZ_TRACKID',
            'MUSICBRAINZ_RELEASETRACKID', 'MUSICBRAINZ_WORKID',
            }, set(response.data['tag']))

    @unittest.expectedFailure
    def test_tagtypes_mask(self):
        with self.run_bpd() as client:
            response = client.send_command('tagtypes', 'clear')
        self.assertTrue(response.ok)

    test_implements_partitions = implements({
            'partition', 'listpartitions', 'newpartition',
            }, expectedFailure=True)

    test_implements_devices = implements({
            'disableoutput', 'enableoutput', 'toggleoutput', 'outputs',
            }, expectedFailure=True)

    test_implements_reflection = implements({
            'config', 'commands', 'notcommands', 'urlhandlers',
            'decoders',
            }, expectedFailure=True)

    test_implements_peers = implements({
            'subscribe', 'unsubscribe', 'channels', 'readmessages',
            'sendmessage',
            }, expectedFailure=True)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
