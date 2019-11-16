Subsonic Playlist Plugin
========================

The ``subsonicplaylist`` plugin allows to import playlists from a subsonic server.
This is done by retrieving the track infos from the subsonic server, searching
them in the beets library and adding the playlist names to the
`subsonic_playlist` tag of the found items. The content of the tag has the format:

    subsonic_playlist: ";first playlist;second playlist"

To get all items in a playlist use the query `;playlist name;`.

Command Line Usage
------------------

To use the ``subsonicplaylist`` plugin, enable it in your configuration (see
:ref:`using-plugins`). Then use it by invoking the ``subsonicplaylist`` command.
By default only the tags of the items found for playlists will be updated.
This means that, if one imported a playlist, then delete one song from it and
imported the playlist again, the deleted song will still have the playlist set
in its `subsonic_playlist` tag. To solve this problem one can use the `-d/--delete`
flag. This resets all `subsonic_playlist` tag before importing playlists.
Options to be defined in your config with their default value::

    subsonicplaylist:
        'base_url': "https://your.subsonic.server"
        'delete': False,
        'playlist_ids': [],
        'playlist_names': [],
        'username': '',
        'password': ''

Parameters `base_url`, `username` and `password` must be defined!