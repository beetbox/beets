# This file is part of beets.
# Copyright 2026, J0J0 Todos.
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


"""Type aliases for the lastgenre plugin."""

from __future__ import annotations

Whitelist = set[str]
"""Set of valid genre names (lowercase). Empty set means all genres allowed."""

CanonTree = list[list[str]]
"""Genre hierarchy as list of paths from general to specific.
Example: [['electronic', 'house'], ['electronic', 'techno']]"""
