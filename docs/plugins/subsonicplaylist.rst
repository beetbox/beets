Subsonic Playlist Plugin
========================

The ``subsonicplaylist`` plugin allows to import playlists from a subsonic server.
This is done by retrieving the track info from the subsonic server, searching
for them in the beets library, and adding the playlist names to the
`subsonic_playlist` tag of the found items. The content of the tag has the format:

    subsonic_playlist: ";first playlist;second playlist;"

To get all items in a playlist use the query `;playlist name;`.

Command Line Usage
------------------

To use the ``subsonicplaylist`` plugin, enable it in your configuration (see
:ref:`using-plugins`). Then use it by invoking the ``subsonicplaylist`` command.
Next, configure the plugin to connect to your Subsonic server, like this::

    subsonicplaylist:
        base_url: http://subsonic.example.com
        username: someUser
        password: somePassword

After this you can import your playlists by invoking the `subsonicplaylist` command.

By default only the tags of the items found for playlists will be updated.
This means that, if one imported a playlist, then delete one song from it and
imported the playlist again, the deleted song will still have the playlist set
in its `subsonic_playlist` tag. To solve this problem one can use the `-d/--delete`
flag. This resets all `subsonic_playlist` tag before importing playlists.

Here's an example configuration with all the available options and their default values::

    subsonicplaylist:
        base_url: "https://your.subsonic.server"
        delete: no
        playlist_ids: []
        playlist_names: []
        username: ''
        password: ''

The `base_url`, `username`, and `password` options are required.
