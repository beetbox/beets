#!/usr/bin/env python
import unittest

test_modules = ['test_mediafile', 'test_library']

def suite():
    s = unittest.TestSuite()
    for mod in map(__import__, test_modules):
        s.addTest(mod.suite())
    return s

if __name__ == '__main__':
    unittest.main(defaultTest='suite')