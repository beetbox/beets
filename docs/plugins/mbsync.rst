MBSync Plugin
=============

The ``mbsync`` lets you fetch metadata from MusicBrainz for albums and
singletons that already have MusicBrainz IDs. This is useful for updating tags
as they are fixed in the MusicBrainz database, or when you change your mind
about some config options that change how tags are written to files. If you have
a music library that is already nicely tagged by a program that also uses
MusicBrainz like Picard, this can speed up the initial import if you just import
“as-is” and then use ``mbsync`` to get up-to-date tags that are written to the
files according to your beets configuration.


Usage
-----

Enable the plugin and then run ``beet mbsync QUERY`` to fetch updated metadata
for a part of your collection. By default this will use the given query to
search for albums and singletons. You can use the  ``-a`` (``--album``) and
``-s`` (``--singleton``) command line flags to only search for albums or
singletons respectively.

To only preview the changes that would be made, use the ``-p`` (``--pretend``)
flag. By default all the new metadata will be written to the files and the files
will be moved according to their new metadata. This behaviour can be changed
with the ``-W`` (``--nowrite``) and ``-M`` (``--nomove``) command line options.
