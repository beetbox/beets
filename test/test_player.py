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

"""Tests for BPD and music playing.
"""
from __future__ import division, absolute_import, print_function

import unittest
from beetsplug import bpd

import multiprocessing as mp
import socket
import time

from test import _common
from test.helper import TestHelper


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
        self.body = b'\n'.join(raw_response.split(b'\n')[:-2])
        self.status = raw_response.split(b'\n')[-2]
        self.ok = self.status.startswith(b'OK')
        self.err = self.status.startswith(b'ACK')
        if self.err:
            print(self.status)


class MPCClient(object):
    def __init__(self, host, port, do_hello=True):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.buf = b''
        if do_hello:
            hello = self.get_response()
            if not hello.ok:
                raise RuntimeError('Bad hello: {}'.format(hello.status))

    def __del__(self):
        self.sock.close()

    def get_response(self):
        response = b''
        while True:
            line = self.readline()
            response += line
            if line.startswith(b'OK') or line.startswith(b'ACK'):
                return MPCResponse(response)

    def send_command(self, command, *args):
        cmd = [command]
        for arg in args:
            if b' ' in arg:
                cmd.append(b'"{}"'.format(arg))
            else:
                cmd.append(arg)
        self.sock.sendall(b' '.join(cmd) + b'\n')
        return self.get_response()

    def readline(self, terminator=b'\n', bufsize=1024):
        ''' Reads a line of data from the socket. '''

        while True:
            if terminator in self.buf:
                line, self.buf = self.buf.split(terminator, 1)
                line += terminator
                return line
            data = self.sock.recv(bufsize)
            if data:
                self.buf += data
            else:
                line = self.buf
                self.buf = b''
                return line


def implements(commands, expectedFailure=False):
    def _test(self):
        response = self.client.send_command(b'commands')
        implemented = {line[9:] for line in response.body.split(b'\n')}
        self.assertEqual(commands.intersection(implemented), commands)
    return unittest.expectedFailure(_test) if expectedFailure else _test


@_common.slow_test()
class BPDTest(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_beets()
        self.load_plugins('bpd')
        self.item = self.add_item()
        self.lib.add_album([self.item])

        self.server_proc, self.client = self.make_server_client()

    def tearDown(self):
        self.server_proc.terminate()
        self.teardown_beets()
        self.unload_plugins()

    def make_server(self, host, port, password=None):
        bpd_server = bpd.BaseServer(host, port, password)
        server_proc = mp.Process(target=bpd_server.run)
        server_proc.start()
        return server_proc

    def make_client(self, host='localhost', port=9876, do_hello=True):
        return MPCClient(host, port, do_hello)

    def make_server_client(self, host='localhost', port=9876, password=None):
        server_proc = self.make_server(host, port, password)
        time.sleep(0.1)  # wait for the server to start
        client = self.make_client(host, port)
        return server_proc, client

    def test_server_hello(self):
        alt_client = self.make_client(do_hello=False)
        self.assertEqual(alt_client.readline(), b'OK MPD 0.13.0\n')

    def test_cmd_ping(self):
        response = self.client.send_command(b'ping')
        self.assertTrue(response.ok)

    def test_cmd_password(self):
        self.server_proc.terminate()
        self.server_proc, self.client = self.make_server_client(
                password='abc123')

        response = self.client.send_command(b'status')
        self.assertTrue(response.err)
        self.assertEqual(response.status,
                         b'ACK [4@0] {} insufficient privileges')

        response = self.client.send_command(b'password', b'wrong')
        self.assertTrue(response.err)
        self.assertEqual(response.status,
                         b'ACK [3@0] {password} incorrect password')

        response = self.client.send_command(b'password', b'abc123')
        self.assertTrue(response.ok)
        response = self.client.send_command(b'status')
        self.assertTrue(response.ok)

    test_implements_query = implements({
            b'clearerror', b'currentsong', b'idle', b'status', b'stats',
            }, expectedFailure=True)

    test_implements_playback = implements({
            b'consume', b'crossfade', b'mixrampdb', b'mixrampdelay', b'random',
            b'repeat', b'setvol', b'single', b'replay_gain_mode',
            b'replay_gain_status', b'volume',
            }, expectedFailure=True)

    test_implements_control = implements({
            b'next', b'pause', b'play', b'playid', b'previous', b'seek',
            b'seekid', b'seekcur', b'stop',
            }, expectedFailure=True)

    test_implements_queue = implements({
            b'add', b'addid', b'clear', b'delete', b'deleteid', b'move',
            b'moveid', b'playlist', b'playlistfind', b'playlistid',
            b'playlistinfo', b'playlistsearch', b'plchanges',
            b'plchangesposid', b'prio', b'prioid', b'rangeid', b'shuffle',
            b'swap', b'swapid', b'addtagid', b'cleartagid',
            }, expectedFailure=True)

    test_implements_playlists = implements({
            b'listplaylist', b'listplaylistinfo', b'listplaylists', b'load',
            b'playlistadd', b'playlistclear', b'playlistdelete',
            b'playlistmove', b'rename', b'rm', b'save',
            }, expectedFailure=True)

    test_implements_database = implements({
            b'albumart', b'count', b'find', b'findadd', b'list', b'listall',
            b'listallinfo', b'listfiles', b'lsinfo', b'readcomments',
            b'search', b'searchadd', b'searchaddpl', b'update', b'rescan',
            }, expectedFailure=True)

    test_implements_mounts = implements({
            b'mount', b'unmount', b'listmounts', b'listneighbors',
            }, expectedFailure=True)

    test_implements_stickers = implements({
            b'sticker',
            }, expectedFailure=True)

    test_implements_connection = implements({
            b'close', b'kill', b'password', b'ping', b'tagtypes',
            }, expectedFailure=True)

    test_implements_partitions = implements({
            b'partition', b'listpartitions', b'newpartition',
            }, expectedFailure=True)

    test_implements_devices = implements({
            b'disableoutput', b'enableoutput', b'toggleoutput', b'outputs',
            }, expectedFailure=True)

    test_implements_reflection = implements({
            b'config', b'commands', b'notcommands', b'urlhandlers',
            b'decoders',
            }, expectedFailure=True)

    test_implements_peers = implements({
            b'subscribe', b'unsubscribe', b'channels', b'readmessages',
            b'sendmessage',
            }, expectedFailure=True)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
