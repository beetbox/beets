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

"""Test file manipulation functionality of Item.
"""

import unittest, shutil, sys, os
sys.path.append('..')
import beets.library
from os.path import join

def mkfile(path):
    open(path, 'w').close()

class MoveTest(unittest.TestCase):
    def setUp(self):
        # make a temporary file
        self.path = join('rsrc', 'temp.mp3')
        shutil.copy(join('rsrc', 'full.mp3'), self.path)
        
        # add it to a temporary library
        self.lib = beets.library.Library(':memory:')
        self.i = beets.library.Item.from_path(self.path)
        self.lib.add(self.i)
        
        # set up the destination
        self.libdir = join('rsrc', 'testlibdir')
        self.lib.directory = self.libdir
        self.lib.path_format = join('$artist', '$album', '$title')
        self.i.artist = 'one'
        self.i.album = 'two'
        self.i.title = 'three'
        self.dest = join(self.libdir, 'one', 'two', 'three.mp3')
        
    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)
        if os.path.exists(self.libdir):
            shutil.rmtree(self.libdir)
    
    def test_move_arrives(self):
        self.i.move(self.lib)
        self.assertTrue(os.path.exists(self.dest))
    
    def test_move_departs(self):
        self.i.move(self.lib)
        self.assertTrue(not os.path.exists(self.path))
    
    def test_copy_arrives(self):
        self.i.move(self.lib, copy=True)
        self.assertTrue(os.path.exists(self.dest))
    
    def test_copy_does_not_depart(self):
        self.i.move(self.lib, copy=True)
        self.assertTrue(os.path.exists(self.path))
    
    def test_move_changes_path(self):
        self.i.move(self.lib)
        self.assertEqual(self.i.path, beets.library._normpath(self.dest))
    
class HelperTest(unittest.TestCase):
    def test_ancestry_works_on_file(self):
        p = '/a/b/c'
        a =  ['/','/a','/a/b']
        self.assertEqual(beets.library._ancestry(p), a)
    def test_ancestry_works_on_dir(self):
        p = '/a/b/c/'
        a = ['/', '/a', '/a/b', '/a/b/c']
        self.assertEqual(beets.library._ancestry(p), a)
    def test_ancestry_works_on_relative(self):
        p = 'a/b/c'
        a = ['a', 'a/b']
        self.assertEqual(beets.library._ancestry(p), a)
    
    def test_components_works_on_file(self):
        p = '/a/b/c'
        a =  ['/', 'a', 'b', 'c']
        self.assertEqual(beets.library._components(p), a)
    def test_components_works_on_dir(self):
        p = '/a/b/c/'
        a =  ['/', 'a', 'b', 'c']
        self.assertEqual(beets.library._components(p), a)
    def test_components_works_on_relative(self):
        p = 'a/b/c'
        a =  ['a', 'b', 'c']
        self.assertEqual(beets.library._components(p), a)

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
