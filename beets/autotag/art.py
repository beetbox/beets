# This file is part of beets.
# Copyright 2011, Adrian Sampson.
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
import os

from beets.autotag.mb import album_for_id

IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg']
COVER_NAMES = ['cover', 'front', 'art', 'album', 'folder']

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
            log.debug('Downloading art: %s' % url)
            fn, headers = urllib.urlretrieve(url)
        except IOError:
            log.debug('error fetching art at URL %s' % url)
            continue
            
        # Make sure it's actually an image.
        if headers.gettype() == AMAZON_CONTENT_TYPE:
            log.debug('Downloaded art to: %s' % fn)
            return fn


# Art from the filesystem.

def art_in_path(path):
    """Look for album art files in a specified directory."""
    if not os.path.isdir(path):
        return

    # Find all files that look like images in the directory.
    images = []
    for fn in os.listdir(path):
        for ext in IMAGE_EXTENSIONS:
            if fn.lower().endswith('.' + ext):
                images.append(fn)

    # Look for "preferred" filenames.
    for fn in images:
        for name in COVER_NAMES:
            if fn.lower().startswith(name):
                log.debug('Using well-named art file %s' % fn)
                return os.path.join(path, fn)

    # Fall back to any image in the folder.
    if images:
        log.debug('Using fallback art file %s' % images[0])
        return os.path.join(path, images[0])


# Main interface.

def art_for_album(album, path):
    """Given an album info dictionary from MusicBrainz, returns a path
    to downloaded art for the album (or None if no art is found).
    """
    if isinstance(path, basestring):
        out = art_in_path(path)
        if out:
            return out

    if album.asin:
        log.debug('Fetching album art for ASIN %s.' % album.asin)
        return art_for_asin(album.asin)
    else:
        log.debug('No ASIN available: no art found.')
        return None


# Smoke test.

if __name__ == '__main__':
    aid = sys.argv[1]
    album = album_for_id(aid)
    if not album:
        print 'album not found'
    else:
        fn = art_for_album(album, None)
        if fn:
            print fn
            print len(open(fn).read())/1024
        else:
            print 'no art found'
