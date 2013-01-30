Smart Playlist Plugin
=====================

``smartplaylist`` is a plugin to generate smart playlists in m3u format based on
beets queries every time your library changes. This plugin is specifically
created to work well with `MPD`_'s playlist functionality.

.. _MPD: http://mpd.wikia.com/wiki/Music_Player_Daemon_Wiki

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
``playlists`` section, using the normal querying format (see
:doc:`/reference/query`) for ``query`` and the file name to be generated for
``name`` (*note*: if you have existing files with the same names, you should
back them up, as they will be overwritten when the plugin runs).

If you add a smart playlist to your ``config.yaml`` file and don't want to wait
until the next time your library changes for ``smartplugin`` to run, you can
invoke it manually from the command-line::

    $ beet splupdate

which will generate your new smart playlists.