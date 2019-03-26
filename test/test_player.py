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
        time.sleep(1)
        client = self.make_client(host, port)
        return server_proc, client

    def test_server_hello(self):
        alt_client = self.make_client(do_hello=False)
        self.assertEqual(alt_client.readline(), b'OK MPD 0.13.0\n')

    def test_cmd_ping(self):
        response = self.client.send_command(b'ping')
        self.assertTrue(response.ok)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
