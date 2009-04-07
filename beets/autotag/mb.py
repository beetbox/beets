import re
import time
import datetime
import musicbrainz2.webservice as mbws

QUERY_WAIT_TIME = 1.0
last_query_time = 0.0
def query_wait():
    global last_query_time

    now = time.time()
    while now - last_query_time < QUERY_WAIT_TIME:
        time.sleep(QUERY_WAIT_TIME - (now - last_query_time))
        now = time.time()

    last_query_time = now

# Regex stolen from MusicBrainz Picard.
def lucene_escape(text):
    return re.sub(r'([+\-&|!(){}\[\]\^"~*?:\\])', r'\\\1', text)

# Workings more or less stolen from Picard.
def find_releases(criteria, limit=25):
    # Build Lucene query (the MusicBrainz 'query' filter).
    query_parts = []
    for name, value in criteria.items():
        value = lucene_escape(value).strip().lower()
        if value:
            query_parts.append('%s:(%s)' % (name, value.encode('utf-8')))
    query = ' '.join(query_parts)
    
    # Build the filter and send the query.
    filter = mbws.ReleaseFilter(limit=limit, query=query)
    query_wait()
    query = mbws.Query()
    return query.getReleases(filter=filter)

def release_dict(release):
    out = {'album':     release.title,
           'album_id':  release.id,
           'artist':    release.artist.name,
           'artist_id': release.artist.id,
          }

    date_str = release.getEarliestReleaseDate()
    try:
        # If the date-string is just an integer, then it's the release
        # year.
        out['year'] = int(date_str)
    except ValueError:
        # Otherwise, it is a full date in the format YYYY-MM-DD.
        timestamp = time.mktime(time.strptime(date_str, '%Y-%m-%d'))
        date = datetime.date.fromtimestamp(timestamp)
        out.update({'year':  date.year,
                    'month': date.month,
                    'day':   date.day,
                   })

    return out

def match_album(artist, album, tracks=None):
    criteria = {'artist':  artist, 'release': album}
    if tracks is not None:
        criteria['tracks'] = str(tracks)

    results = find_releases(criteria, 1)
    if not results:
        return None
    return release_dict(results[0].release)


if __name__ == '__main__':
    print match_album('the little ones', 'morning tide')
    print match_album('the 6ths', 'hyacinths and thistles')

