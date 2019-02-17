Smart Playlist Plugin
=====================

``playlist`` is a plugin to use playlists in m3u format.

To use it, enable the ``playlist`` plugin in your configuration
(see :ref:`using-plugins`).
Then configure your playlists like this::

    playlist:
        relative_to: ~/Music
        playlist_dir: ~/.mpd/playlists

It is possible to query the library based on a playlist by speicifying its
absolute path::

    $ beet ls playlist:/path/to/someplaylist.m3u

The plugin also supports referencing playlists by name. The playlist is then
seached in the playlist_dir and the ".m3u" extension is appended to the
name::

    $ beet ls playlist:anotherplaylist

Configuration
-------------

To configure the plugin, make a ``smartplaylist:`` section in your
configuration file. In addition to the ``playlists`` described above, the
other configuration options are:

- **playlist_dir**: Where to read playlist files from.
  Default: The current working directory (i.e., ``'.'``).
- **relative_to**: Interpret paths in the playlist files relative to a base
  directory. Instead of setting it to a fixed path, it is also possible to
  set it to ``playlist`` to use the playlist's parent directory or to
  ``library`` to use the library directory.
  Default: ``library``
