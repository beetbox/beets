IHate Plugin
============

The ``ihate`` plugin allows you to automatically skip things you hate during
import or warn you about them. It supports album, artist and genre patterns.
There also is a whitelist to avoid skipping bands you still like. There are two
groups: warn and skip. The skip group is checked first. Whitelist overrides any
other patterns.

To use the plugin, enable it by including ``ihate`` in the ``plugins`` line of
your beets config. Then, add an ``ihate:`` section to your configuration file::

    ihate:
        # you will be warned about these suspicious genres/artists (regexps):
        warn_genre: rnb soul power\smetal
        warn_artist: bad\band another\sbad\sband
        warn_album: tribute\sto
        # if you don't like a genre in general, but accept some band playing it,
        # add exceptions here:
        warn_whitelist: hate\sexception
        # never import any of this:
        skip_genre: russian\srock polka
        skip_artist: manowar
        skip_album: christmas
        # but import this:
        skip_whitelist: ''

Note: The plugin will trust your decision in 'as-is' mode.
