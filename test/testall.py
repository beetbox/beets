#!/usr/bin/env python
import unittest
import os
import re

def suite():
    s = unittest.TestSuite()
    # get the suite() of every module in this directory begining with test_
    for fname in os.listdir('.'):
        match = re.match(r'(test_\S+)\.py$', fname)
        if match:
            s.addTest(__import__(match.group(1)).suite())
    return s

if __name__ == '__main__':
    unittest.main(defaultTest='suite')