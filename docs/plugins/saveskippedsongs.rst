Save Skipped Songs Plugin
================

The ``saveskippedsongs`` plugin will save the name of the skipped song/album 
to a text file during import for later review.

It will also allow you to try to find the Spotify link for the skipped songs if
the Spotify plugin is installed and configured.
This information can later be used together with other MB importers like Harmony.

If any song has already been written to the file, it will not be written again.

To use the ``saveskippedsongs`` plugin, enable it in your configuration (see
:ref:`using-plugins`).

Configuration
-------------

To configure the plugin, make a ``saveskippedsongs:`` section in your configuration
file. The available options are:

- **spotify**: Search Spotify for the song/album and return the link. Default: ``yes``.
- **path**: Path to the file to write the skipped songs to. Default: ``skipped_songs.txt``.
