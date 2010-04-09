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

class WalkTest(unittest.TestCase):
    def setUp(self):
        # create a directory structure for testing
        self.base = join('rsrc', 'temp_walk')
        os.mkdir(self.base)
        mkfile(join(self.base, 'file'))
        os.mkdir(join(self.base, 'dir1'))
        mkfile(join(self.base, 'dir1', 'dir1f1'))
        mkfile(join(self.base, 'dir1', 'dir1f2'))
        os.mkdir(join(self.base, 'dir2'))
        mkfile(join(self.base, 'dir2', 'dir2f'))
        os.mkdir(join(self.base, 'dir2', 'dir2dir'))
        mkfile(join(self.base, 'dir2', 'dir2dir', 'dir2dirf'))
    def tearDown(self):
        shutil.rmtree(self.base)
    
    def test_walk_single_file(self):
        path = join(self.base, 'file')
        s = set(beets.library._walk_files(path))
        self.assertTrue(path in s)
        s.remove(path)
        self.assertTrue(not s) # s is empty (i.e., contains nothing else)
    
    def test_walk_flat_directory(self):
        path = join(self.base, 'dir1')
        s = set(beets.library._walk_files(path))
        for f in (join(path, 'dir1f1'),
                  join(path, 'dir1f2')):
            self.assertTrue(f in s)
            s.remove(f)
        self.assertTrue(not s)
    
    def test_walk_hierarchy(self):
        path = join(self.base, 'dir2')
        s = set(beets.library._walk_files(path))
        for f in (join(path, 'dir2f'),
                  join(path, 'dir2dir', 'dir2dirf')):
            self.assertTrue(f in s)
            s.remove(f)
        self.assertTrue(not s)

class AddTest(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.join('rsrc', 'test_lib')
        self.lib = beets.library.Library(':memory:')
        self.lib.directory = self.dir
        self.lib.path_format = 'item'
    def tearDown(self):
        if os.path.exists(self.dir):
            shutil.rmtree(self.dir)

    def test_library_add_path_copies(self):
        self.lib.add_path(os.path.join('rsrc', 'full.mp3'), copy=True)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, 'item.mp3')))

    def test_add_path_enforces_unicode_pathnames(self):
        self.lib.add_path(os.path.join('rsrc', 'full.mp3'))
        item = self.lib.get().next()
        self.assertTrue(isinstance(item.path, unicode))
    
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
