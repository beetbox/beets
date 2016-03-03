# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

"""DBCore is an abstract database package that forms the basis for beets'
Library.
"""
from __future__ import division, absolute_import, print_function

from .db import Model, Database
from .query import Query, FieldQuery, MatchQuery, AndQuery, OrQuery
from .types import Type
from .queryparse import query_from_strings
from .queryparse import sort_from_strings
from .queryparse import parse_sorted_query
from .query import InvalidQueryError

# flake8: noqa
