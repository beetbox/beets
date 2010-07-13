# This file is part of beets.
# Copyright 2010, Adrian Sampson.
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

"""Finding album art for tagged albums."""

import urllib
import sys
import logging

from beets.autotag.mb import album_for_id

# The common logger.
log = logging.getLogger('beets')


# Art from Amazon.

AMAZON_URL = 'http://images.amazon.com/images/P/%s.%02i.LZZZZZZZ.jpg'
AMAZON_INDICES = (1,2)
AMAZON_CONTENT_TYPE = 'image/jpeg'
def art_for_asin(asin):
    """Fetches art for an Amazon ID (ASIN) string."""
    for index in AMAZON_INDICES:
        # Fetch the image.
        url = AMAZON_URL % (asin, index)
        try:
            fn, headers = urllib.urlretrieve(url)
        except IOError:
            log.debug('error fetching art at URL %s' % url)
            continue
            
        # Make sure it's actually an image.
        if headers.gettype() == AMAZON_CONTENT_TYPE:
            return fn


# Main interface.

def art_for_album(album):
    """Given an album info dictionary from MusicBrainz, returns a path
    to downloaded art for the album (or None if no art is found).
    """
    if album['asin']:
        return art_for_asin(album['asin'])
    else:
        return None


# Smoke test.

if __name__ == '__main__':
    aid = sys.argv[1]
    album = album_for_id(aid)
    if not album:
        print 'album not found'
    else:
        fn = art_for_album(album)
        if fn:
            print fn
            print len(open(fn).read())/1024
        else:
            print 'no art found'

