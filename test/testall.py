#!/usr/bin/env python

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

