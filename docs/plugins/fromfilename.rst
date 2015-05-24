FromFilename Plugin
===================

The ``fromfilename`` plugin helps to tag albums that are missing tags
altogether but where the filenames contain useful information like the artist
and title.

When you attempt to import a track that's missing a title, this plugin will
look at the track's filename and guess its track number, title, and artist.
These will be used to search in MusicBrainz and match track ordering.

To use the ``fromfilename`` plugin, enable it in your configuration
(see :ref:`using-plugins`).
