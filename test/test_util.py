# This file is part of beets.
# Copyright 2013, Adrian Sampson.
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

"""Tests for utils."""

import _common
from _common import unittest
from beets.util.enumeration import OrderedEnum, IndexableEnum

class EnumTest(_common.TestCase):
  """
  Test Enum Subclasses defined in beets.util.enumeration
  """
  def test_ordered_enum(self):
    OrderedEnumTest = OrderedEnum('OrderedEnumTest', ['a', 'b', 'c'])
    self.assertLess(OrderedEnumTest.a, OrderedEnumTest.b)
    self.assertLess(OrderedEnumTest.a, OrderedEnumTest.c)
    self.assertLess(OrderedEnumTest.b, OrderedEnumTest.c)
    
  def test_indexable_enum(self):
    values = ['a', 'b', 'c']
    IndexableEnumTest = IndexableEnum('IndexableEnumTest', values)
    for v in values:
      self.assertEqual(IndexableEnumTest[IndexableEnumTest[v].value],
                       IndexableEnumTest[v])
                                      

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')

