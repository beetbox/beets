#!/usr/bin/env python

"""
Test file manipulation functionality of Item.
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
        self.i.add(self.lib)
        
        # set up the destination
        self.libdir = join('rsrc', 'testlibdir')
        self.lib.options['directory'] = self.libdir
        self.lib.options['path_format'] = join('$artist',
                                                '$album', '$title')
        self.i.artist = 'one'
        self.i.album = 'two'
        self.i.title = 'three'
        self.dest = join(self.libdir, 'one', 'two', 'three')
        
    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)
        if os.path.exists(self.libdir):
            shutil.rmtree(self.libdir)
    
    def test_move_arrives(self):
        self.i.move()
        self.assertTrue(os.path.exists(self.dest))
    
    def test_move_departs(self):
        self.i.move()
        self.assertTrue(not os.path.exists(self.path))
    
    def test_copy_arrives(self):
        self.i.move(copy=True)
        self.assertTrue(os.path.exists(self.dest))
    
    def test_copy_does_not_depart(self):
        self.i.move(copy=True)
        self.assertTrue(os.path.exists(self.path))
    
    def test_move_changes_path(self):
        self.i.move()
        self.assertEqual(self.i.path, beets.library._normpath(self.dest))

class DeleteTest(unittest.TestCase):
    def setUp(self):
        # make a temporary file
        self.path = join('rsrc', 'temp.mp3')
        shutil.copy(join('rsrc', 'full.mp3'), self.path)
        
        # add it to a temporary library
        self.lib = beets.library.Library(':memory:')
        self.i = beets.library.Item.from_path(self.path)
        self.i.add(self.lib)
    def tearDown(self):
        # make sure the temp file is gone
        if os.path.exists(self.path):
            os.remove(self.path)
    
    def test_delete_deletes_file(self):
        self.i.delete()
        self.assertTrue(not os.path.exists(self.path))
    
    def test_delete_removes_from_db(self):
        self.i.delete()
        c = self.lib.conn.execute('select * from items where 1')
        self.assertEqual(c.fetchone(), None)

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
        
def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')