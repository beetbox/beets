FromFilename Plugin
===================

The ``fromfilename`` plugin helps to tag albums that are missing tags altogether
but where the filenames contain useful information like the artist and title.

When you attempt to import a track that's missing a title, this plugin will look
at the track's filename and parent folder, and guess a number of fields.

The extracted information will be used to search for metadata and match track
ordering.

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
        ignore_dirs:

.. conf:: fields
    :default: [ artist, album, albumartist, catalognum, disc, media, title, track, year ]

    The fields the plugin will guess with its default pattern matching.

    By default, the plugin is configured to match all fields its default
    patterns are capable of matching.

    If a field is specified in a user pattern, that field does not need
    to be present on this list to be applied.

    If you only want the plugin to contribute the track title and artist,
    you would put ``[title, artist]``.

.. conf:: patterns

    Users can specify patterns to expand the set of filenames that can
    be recognized by the plugin. Patterns can be specified as ``file``
    or ``folder`` patterns. ``file`` patterns are checked against the filename.
    ``folder`` patterns are checked against the parent folder of the file.

    If ``fromfilename`` can't match the entire string to one of the given pattern, it will
    fall back to the default pattern.

    For example, the following custom patterns will match this path and folder,
    and retrieve the specified fields.

    ``/music/James Lawson - 841689 (2004)/Coming Up - James Lawson & Andy Farley.mp3``

    .. code-block:: yaml

        patterns:
           folder:
             - "$albumartist - $discogs_albumid ($year)"
           file:
             - "$title - $artist"

.. conf:: ignore_dirs
    :default: []

    Specify parent directory names that will not be searched for album
    information. Useful if you use a regular directory for importing
    single files.
