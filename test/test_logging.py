"""Stupid tests that ensure logging works as expected"""
import logging as log
from StringIO import StringIO

import beets.logging as blog
from _common import unittest, TestCase


class LoggingTest(TestCase):
    def test_logging_management(self):
        l1 = log.getLogger("foo123")
        l2 = blog.getLogger("foo123")
        self.assertEqual(l1, l2)
        self.assertEqual(type(l1), log.Logger)

        l3 = blog.getLogger("bar123")
        l4 = log.getLogger("bar123")
        self.assertEqual(l3, l4)
        self.assertEqual(type(l3), blog.StrFormatLogger)

        l5 = l3.getChild("shalala")
        self.assertEqual(type(l5), blog.StrFormatLogger)

    def test_str_format_logging(self):
        l = blog.getLogger("baz123")
        stream = StringIO()
        handler = log.StreamHandler(stream)

        l.addHandler(handler)
        l.propagate = False

        l.warning("foo {} {bar}", "oof", bar="baz")
        handler.flush()
        self.assertTrue(stream.getvalue(), "foo oof baz")


if __name__ == '__main__':
    unittest.main()
