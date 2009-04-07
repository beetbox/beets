from collections import defaultdict
from beets.autotag.mb import match_album

def likely_metadata(items):
    """Returns the most likely artist and album for a set of Items.
    Each is determined by tag reflected by the plurality of the Items.
    """

    # The tags we'll try to determine.
    keys = 'artist', 'album'

    # Make dictionaries in which to count the freqencies of different
    # artist and album tags. We'll use this to find the most likely
    # artist and album. Defaultdicts let the frequency default to zero.
    freqs = {}
    for key in keys:
        freqs[key] = defaultdict(int)

    # Count the frequencies.
    for item in items:
        for key in keys:
            value = getattr(item, key)
            if value: # Don't count empty tags.
                freqs[key][value] += 1

    # Find max-frequency tags.
    likelies = {}
    for key in keys:
        max_freq = 0
        likelies[key] = None
        for tag, freq in freqs[key].items():
            if freq > max_freq:
                max_freq = freq
                likelies[key] = tag
    
    return (likelies['artist'], likelies['album'])

if __name__ == '__main__': # Smoke test.
    from beets.library import Item
    items = [Item({'artist': 'The Beatles', 'album': 'The White Album'}),
             Item({'artist': 'The Beetles', 'album': 'The White Album'}),
             Item({'artist': 'The Beatles', 'album': 'Teh White Album'})]
    print likely_metadata(items)


