FromFilename Plugin
===================

The ``fromfilename`` plugin helps to expand the tags on files where filenames
contain useful information that may be missing on the file metadata.

If importing an album, the plugin will look at the parent folder and use it to
find album specific information.

The extracted information will be used to search for metadata and better match
track order.

A prompt is added to the UI by the plugin, ``toggle FromFilename`` that allows
you to toggle searching with the additional found tags by the plugin. This can
be helpful when the plugin gets a guess completely wrong!

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
          - disc
          - title
          - track
        patterns: []
        sanity_check: yes
        autouse: yes
        fromfolder:
            fields:
              - album
              - albumartist
              - catalognum
              - media
              - year
            patterns: []
            ignore: []

.. conf:: fields
    :default: [ artist, disc, title, track ]

    Fields are the tags a filename with its default pattern matching.

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

.. conf:: sanity_check
    :default: yes

    This double checks the track title and artist fields have been guessed correctly.
    Essentially, if all the title guesses are the same, that is more likely to be
    the album artist than the track title.

.. conf:: autouse
    :default: yes

    Whether or not the plugin should be enabled automatically when starting an import session.
    Set to ``no`` to require turning it on with the UI by selecting ``toggle FromFilename``.

.. conf:: fromfolder.fields
    :default: [ album, albumartist, catalognum, media, year ]

    The fields are what the plugin will search a folder name
    for. This is not used when choosing to group by album or
    group by tracks.

.. conf:: fromfolder.patterns
    :default: []

    See the above ``patterns`` configuration documentation.

.. conf:: fromfolder.ignore
    :default: []

    Specify parent directory names that will not be searched for album
    information. Useful if you use a regular directory for importing
    single files.
