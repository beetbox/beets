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

"""Tests for the command-line interface.
"""

import unittest
import sys
sys.path.append('..')
from beets import library
from beets import ui
from beets.ui import commands

# Dummy printing so we can get the commands' output.
outbuffer = []
def buffer_append(*txt):
    outbuffer.extend(txt)
ui.print_ = buffer_append
commands.print_ = buffer_append
def get_output():
    return u' '.join(outbuffer)
def clear_buffer():
    outbuffer[:]

class ListTest(unittest.TestCase):
    def setUp(self):
        clear_buffer()
        self.lib = library.Library(':memory:')
        i = library.Item({
            'title':      u'the title',
            'artist':     u'the artist',
            'album':      u'the album',
            'genre':      u'the genre',
            'composer':   u'the composer',
            'grouping':   u'the grouping',
            'year':       1,
            'month':      2,
            'day':        3,
            'track':      4,
            'tracktotal': 5,
            'disc':       6,
            'disctotal':  7,
            'lyrics':     u'the lyrics',
            'comments':   u'the comments',
            'bpm':        8,
            'comp':       True,
            'path':       'somepath',
            'length':     60.0,
            'bitrate':    128000,
        })
        self.lib.add(i)
        
    def test_list_outputs_item(self):
        commands.list_items(self.lib, '', False)
        out = get_output()
        self.assertTrue(u'the title' in out)
    
    def test_list_album_omits_title(self):
        commands.list_items(self.lib, '', True)
        out = get_output()
        self.assertTrue(u'the title' not in out)
    
def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
