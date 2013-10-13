FtInTitle Plugin
================

The ``ftintitle`` plugin automatically moved "featured" artists from the
``artist`` field to the ``title`` field.

According to `MusicBrainz style`_, featured artists are part of the artist
field. That means that, if you tag your music using MusicBrainz, you'll have
tracks in your library like "Tellin' Me Things" by the artist "Blakroc feat.
RZA". If you prefer to tag this as "Tellin' Me Things feat. RZA" by "Blakroc",
then this plugin is for you.

To use the plugin, just enable it and run the command::

    $ beet ftintitle [QUERY]

The query is optional; if it's left off, the transformation will be applied to
your entire collection.

.. _MusicBrainz style: http://musicbrainz.org/doc/Style
