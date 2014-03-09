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
            - name: all.m3u
              query: ''

            - name: beatles.m3u
              query: 'artist:Beatles'

If you intend to use this plugin to generate playlists for MPD, you should set
``relative_to`` to your MPD music directory (by default, ``relative_to`` is
``None``, and the absolute paths to your music files will be generated).

``playlist_dir`` is where the generated playlist files will be put.

You can generate as many playlists as you want by adding them to the
``playlists`` section, using beets query syntax (see
:doc:`/reference/query`) for ``query`` and the file name to be generated for
``name``. The query will be split using shell-like syntax, so if you need to
use spaces in the query, be sure to quote them (e.g., ``artist:"The Beatles"``).
If you have existing files with the same names, you should back them up---they
will be overwritten when the plugin runs.

For more advanced usage, you can use template syntax (see
:doc:`/reference/pathformat/`) in the ``name`` field. For example::

    - name: 'ReleasedIn$year.m3u'
      query: 'year::201(0|1)'

This will query all the songs in 2010 and 2011 and generate the two playlist
files `ReleasedIn2010.m3u` and `ReleasedIn2011.m3u` using those songs.

You can also gather the results of several queries by putting them in a list.
(Items that match both queries are not included twice.) For example::

    - name: 'BeatlesUniverse.m3u'
      query: ['artist:beatles', 'genre:"beatles cover"']

For querying albums instead of items (mainly useful with extensible fields),
use the ``album_query`` field. ``query`` and ``album_query`` can be used at the
same time. The following example gathers single items but also items belonging
to albums that have a ``for_travel`` extensible field set to 1::

    - name: 'MyTravelPlaylist.m3u'
      album_query: 'for_travel:1'
      query: 'for_travel:1'

By default, all playlists are automatically regenerated after every beets
command that changes the library database. This can be disabled by specifying
``auto: no``. To force regeneration, you can invoke it manually from the
command line::

    $ beet splupdate

which will generate your new smart playlists.

You can also use this plugin together with the :doc:`mpdupdate`, in order to
automatically notify MPD of the playlist change, by adding ``mpdupdate`` to
the ``plugins`` line in your config file *after* the ``smartplaylist``
plugin.
