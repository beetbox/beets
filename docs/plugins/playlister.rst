Playlister Plugin
=================

The ``playlister`` plugin automatically adds imported tracks to selected
playlists in the ``.m3u`` format.

The plugin currently only works if either the option ``move`` or the option
``copy`` is set to ``yes``.

Usage
-----

After each imported track all currently present playlists in the
``playlistfolder`` are displayed. A comma separated list of indices or name of
the present playlists as well as names of new playlists can be specified. 

Example::

    $ beet imp my_track.mp3
    Add track my_track to playlist(s)? [Y]es/No/no to All y
    [0] Playlist1
    [1] Playlist2
    Enter comma-separated list of indices of playlists and/or names of new
    playlists (empty cancels): 0, Playlist3
    Adding my_track.mp3 to playlist: Playlist1
    Adding my_track.mp3 to playlist: Playlist3

Configuration
-------------

To configure the plugin, make a ``playlister`` section in your configuration
file. The available options are:

- **playlistfolder**: The folder in which to store all playlists.
  Default: ``~/Playlists``.
- **mode**: (``absolute`` or ``relative``) Use absolute or relative paths in 
  the playlists.   
  Default: ``absolute``
