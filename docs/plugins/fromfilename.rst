FromFilename Plugin
===================

The ``fromfilename`` plugin helps to tag albums that are missing tags altogether
but where the filenames contain useful information like the artist and title.

When you attempt to import a track that's missing a title, this plugin will look
at the track's filename and guess its disc, track number, title, and artist.
These will be used to search for metadata and match track ordering.

To use the ``fromfilename`` plugin, enable it in your configuration (see
:ref:`using-plugins`).

Configuration
-------------

Configuration for ``fromfilename`` allows you to choose what fields the plugin
attempts to contribute to files missing information.

Default
~~~~~~~

.. code-block:: yaml

    fromfilename:
        fields:
          - artist
          - album
          - albumartist
          - catalognum
          - disc
          - media
          - title
          - track

Recognized Patterns
-------------------

Examples of paths that the plugin can parse successfully, and the fields
retrieved.

.. code-block:: yaml

    "/Artist - Album (2025)/03.wav"
    album: Album
    albumartist: Artist
    title: "03"
    track: 3

    "/[CAT123] Album - Various [WEB-FLAC]/2-10 - Artist - Song One.flac"
    artist: Artist
    album: Album
    albumartist: Various Artists
    catalognum: CAT123
    disc: 2
    media: Digital Media
    title: Song One
    track: 10

    "/1-23.flac"
    disc: 1
    track: 23

    "/04. Song.mp3"
    title: Song
    track: 4

    "/5_-_My_Artist_-_My_Title.m4a"
    artist: My_Artist
    title: My_Title
    track: 5

    "/8 Song by Artist.wav"
    artist: Artist
    title: Song
    track: 8
