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

"""Helpers around the extraction of album/track ID's from metadata sources."""

# Spotify IDs consist of 22 alphanumeric characters
# (zero-left-padded base62 representation of randomly generated UUID4)
spotify_id_regex = {
    'pattern': r'(^|open\.spotify\.com/{}/)([0-9A-Za-z]{{22}})',
    'match_group': 2,
}
