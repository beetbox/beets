Subsonic Playlist Plugin
========================

The ``subsonicplaylist`` plugin allows to import playlist from a subsonic server

Command Line Usage
------------------

To use the ``subsonicplaylist`` plugin, enable it in your configuration (see
:ref:`using-plugins`). Then use it by invoking the ``subsonicplaylist`` command.
The command will search the playlist on the subsonic server and create a playlist
using the beets library. Options to be defined in your config with their default value::

    subsonicplaylist:
        base_url: "https://your.subsonic.server"
        'relative_to': None,
        'playlist_dir': '.',
        'forward_slash': False,
        'playlist_ids': [],
        'playlist_names': [],
        'username': '',
        'password': ''

Parameters `base_url`, `username` and `password` must be defined!