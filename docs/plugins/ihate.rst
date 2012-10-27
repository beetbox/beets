IHate Plugin
============

The ``ihate`` plugin allows you to automatically skip things you hate during
import or warn you about them. It supports album, artist and genre patterns.
Also there is whitelist to avoid skipping bands you still like. There are two
groups: warn and skip. Skip group is checked first. Whitelist overrides any
other patterns.

To use plugin, enable it by including ``ihate`` into ``plugins`` line of
your beets config::

    [beets]
    plugins = ihate

You need to configure plugin before use, so add following section into config
file and adjust it to your needs::

    [ihate]
    # you will be warned about these suspicious genres/artists (regexps):
    warn_genre=rnb soul power\smetal
    warn_artist=bad\band another\sbad\sband
    warn_album=tribute\sto
    # if you don't like genre in general, but accept some band playing it,
    # add exceptions here:
    warn_whitelist=hate\sexception
    # never import any of this:
    skip_genre=russian\srock polka
    skip_artist=manowar
    skip_album=christmas
    # but import this:
    skip_whitelist=

Note: plugin will trust you decision in 'as-is' mode.
  