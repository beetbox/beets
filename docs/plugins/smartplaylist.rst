Smart Playlist Plugin
=====================

``smartplaylist`` is a plugin to generate smart playlists in m3u format based on
beets queries every time your library changes. This plugin is specifically
created to work well with `MPD's`_ playlist functionality.

.. _MPD's: http://mpd.wikia.com/wiki/Music_Player_Daemon_Wiki

To use it, enable the plugin by putting ``smartplaylist`` in the ``plugins``
section in your ``config.yaml``. Then configure your smart playlists like the
following example::

    smartplaylist:
        relative_to: ~/Music
        playlist_dir: ~/.mpd/playlists
        playlists:
            - query: ''
              name: all.m3u

            - query: 'artist:Beatles'
              name: beatles.m3u

If you intend to use this plugin to generate playlists for MPD, you should set
``relative_to`` to your MPD music directory (by default, ``relative_to`` is
``None``, and the absolute paths to your music files will be generated).

``playlist_dir`` is where the generated playlist files will be put.

You can generate as many playlists as you want by adding them to the
``playlists`` section, using beets query syntax (see
:doc:`/reference/query`) for ``query`` and the file name to be generated for
``name``. If you have existing files with the same names, you should
back them up---they will be overwritten when the plugin runs.

For more advanced usage, you can use template syntax (see
:doc:`/reference/pathformat/`) in the ``name`` field. For example::

    - query: 'year::201(0|1)'
      name: 'ReleasedIn$year.m3u'

This will query all the songs in 2010 and 2011 and generate the two playlist
files `ReleasedIn2010.m3u` and `ReleasedIn2011.m3u` using those songs.

By default, all playlists are regenerated after every beets command that
changes the library database. To force regeneration, you can invoke it manually
from the command line::

    $ beet splupdate

which will generate your new smart playlists.
