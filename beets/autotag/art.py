import urllib
import sys
import logging

from beets.autotag.mb import album_for_id

log = logging.getLogger('beets')

AMAZON_URL = 'http://images.amazon.com/images/P/%s.%02i.LZZZZZZZ.jpg'
AMAZON_INDICES = (1,2)
AMAZON_CONTENT_TYPE = 'image/jpeg'

def art_for_album(album):
    """Given an album info dictionary from MusicBrainz, returns a path
    to art for the album (or None if no art is found).
    """
    if album['asin']:
        for index in AMAZON_INDICES:
            # Fetch the image.
            url = AMAZON_URL % (album['asin'], index)
            try:
                fn, headers = urllib.urlretrieve(url)
            except IOError:
                log.debug('error fetching art at URL %s' % url)
                continue
                
            # Make sure it's actually an image.
            if headers['Content-Type'] == AMAZON_CONTENT_TYPE:
                return fn
    else:
        return None

# Smoke test.
if __name__ == '__main__':
    aid = sys.argv[1]
    fn = art_for_album(album_for_id(aid))
    if fn:
        print fn
        print len(open(fn).read())/1024
    else:
        print 'no art found'
