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
attempts to contribute to files missing information, as well as specify extra
patterns to match.

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
          - year
        patterns:
          file: []
          folder: []

.. conf:: fields
    :default: [ artist, album, albumartist, catalognum, disc, media, title, track, year ]

    The fields the plugin will guess with its default pattern matching. If a field is specified in a user pattern,  that field does not need to be present on this list to be applied. If you only want the plugin contribute the track title and artist, you would put ``[title, artist]``.

.. conf:: patterns

    Extra regular expression patterns specified by the user. See the section on patterns for more information.

Patterns
--------

Examples of paths that the plugin can parse successfully, and the fields
retrieved.

.. code-block:: yaml

    "/Artist - Album (2025)/03.wav"
    album: Album
    albumartist: Artist
    title: "03"
    track: 3
    year: 2025

    "/[CAT123] Album - Various [WEB-FLAC]/2-10 - Artist - Song One.flac"
    artist: Artist
    album: Album
    albumartist: Various Artists
    catalognum: CAT123
    disc: 2
    media: Digital Media
    title: Song One
    track: 10

    "/Album Artist - Album Title (1997) {CATALOGNUM123}/1-23.flac"
    albumartist: Album Artist
    album: Album Title
    year: 1997
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

User Patterns
~~~~~~~~~~~~~

Users can specify patterns to improve the efficacy of the plugin. Patterns can
be specified as ``file`` or ``folder`` patterns. ``file`` patterns are checked
against the filename. ``folder`` patterns are checked against the parent folder
of the file.

To contribute information, the patterns must use named capture groups
``(?P<name>...)``. The name of the capture group represents the beets field the
captured text will be applied to. User patterns are compiled with the verbose
and ignore case flags. Spaces in a match should be noted with `\s`.

If ``fromfilename`` can't match the entire string to the given pattern, it will
fall back to the default pattern.

The following custom patterns will match this path and retrieve the specified
fields.

``/music/James Lawson - 841689/Coming Up - James Lawson & Andy Farley.mp3``

.. code-block:: yaml

    patterns:
       folder:
         # multiline blocks are allowed for readability
         - |
           (?P<albumartist>\w+)
           \s-\s
           (?P<discogs_albumid>\d+)'
       file:
         - '(?P<artist>\w+)\s-\s(?P<track>\d+)'

For more information on writing regular expressions, check out the `python
documentation`_.

.. _python documentation: https://docs.python.org/3/library/re.html
