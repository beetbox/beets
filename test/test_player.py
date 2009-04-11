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

"""Tests for BPD and music playing.
"""

import unittest
import sys
sys.path.append('..')
from beets.player import bpd

class FauxPathTest(unittest.TestCase):
    
    # The current encoding actually cannot distinguish between ['']
    # and []. This doesn't cause a bug because we never use empty
    # sequences, but it might be nice to fix someday.
    #def test_empty_seq_preserved(self):
    #    seq = []
    #    self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq)), seq)
        
    def test_single_element_preserved(self):
        seq = ['hello']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq)), seq)
    
    def test_multiple_elements_preserved(self):
        seq = ['hello', 'there', 'how', 'are', 'you']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq)), seq)
    
    def test_spaces_preserved(self):
        seq = ['hel lo', 'what', 'is up']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq)), seq)
    
    def test_empty_string_preserved_in_middle(self):
        seq = ['hello', '', 'sup']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq)), seq)
    
    def test_empty_strings_preserved_on_ends(self):
        seq = ['', 'whatever', '']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq)), seq)
    
    def test_empty_strings_only(self):
        seq = ['', '', '']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq)), seq)
    
    def test_slashes_preserved(self):
        seq = ['hel/lo', 'what', 'is', 'up']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq)), seq)
    
    def test_backslashes_preserved(self):
        seq = ['hel\\lo', 'what', 'is', 'up']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq)), seq)
    
    def test_unicode_preserved(self):
        seq = [u'hello', u'what \x99 is', u'up']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq)), seq)
    
    def test_slashes_not_encoded_as_slashes(self):
        no_slashes = bpd.seq_to_path(['goodday', 'sir'])
        with_slashes = bpd.seq_to_path(['good/day', 'sir'])
        self.assertEqual(no_slashes.count('/'), with_slashes.count('/'))
    

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')

