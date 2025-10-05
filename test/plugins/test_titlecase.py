# This file is part of beets.
# Copyright 2025, Henry Oberholtzer
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

""" Tests for the 'titlecase' plugin"""

import pytest

from beets import config
from beets.test.helper import BeetsTestCase
from beetsplug.titlecase import TitlecasePlugin

@pytest.mark.parametrize("given, expected",
    [("PENDULUM", "Pendulum"),
     ("Aaron-carl", "Aaron-Carl"),
     ("LTJ bukem", "LTJ Bukem"),
     ("Freaky chakra Vs. Single Cell Orchestra",
     "Freaky Chakra vs. Single Cell Orchestra")
     ])
def test_basic_titlecase(given, expected):
    """ Assert that general behavior is as expected. """
    assert TitlecasePlugin().titlecase(given) == expected


class TitlecasePluginTest(BeetsTestCase):
    
    def test_preserved_case(self):
        """ Test using given strings to preserve case """
        names_to_preserve = ["easyFun", "A.D.O.R.", 
            "D.R.", "ABBA", "LaTeX"]
        config["titlecase"]["preserve"] = names_to_preserve
        for name in names_to_preserve:
            assert TitlecasePlugin().titlecase(
                    name.lower()) == name

    def test_small_first_last(self):
        config["titlecase"]["small_first_last"] = False
        assert TitlecasePlugin().titlecase(
                "A Simple Trial") == "a Simple Trial"
        config["titlecase"]["small_first_last"] = True
        assert TitlecasePlugin().titlecase(
                "A simple Trial") == "A Simple Trial"

    

