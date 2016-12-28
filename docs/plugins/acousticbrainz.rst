AcousticBrainz Plugin
=====================

The ``acousticbrainz`` plugin gets acoustic-analysis information from the
`AcousticBrainz`_ project.

.. _AcousticBrainz: http://acousticbrainz.org/

Enable the ``acousticbrainz`` plugin in your configuration (see :ref:`using-plugins`) and run it by typing::

    $ beet acousticbrainz [-f] [QUERY]

By default, the command will only look for acousticbrainz data when the tracks doesn't
already have it; the ``-f`` or ``--force`` switch makes it fetch acousticbrainz 
for the item. If you specify a query, only matching tracks will be processed; 
otherwise, the command processes every track in your library.

For all tracks with a MusicBrainz recording ID, the plugin currently sets
these fields:

* ``average_loudness``
* ``bpm``
* ``chords_changes_rate``
* ``chords_key``
* ``chords_number_rate``
* ``chords_scale``
* ``danceable``
* ``gender``
* ``genre_rosamerica``
* ``initial_key`` (This is a built-in beets field, which can also be provided
  by :doc:`/plugins/keyfinder`.)
* ``key_strength``
* ``mood_acoustic``
* ``mood_aggressive``
* ``mood_electronic``
* ``mood_happy``
* ``mood_party``
* ``mood_relaxed``
* ``mood_sad``
* ``rhythm``
* ``tonal``
* ``voice_instrumental``

Automatic Tagging
-----------------

To automatically tag files using AcousticBrainz data during import, just
enable the ``acousticbrainz`` plugin (see :ref:`using-plugins`). When importing 
new files, beets will query the AcousticBrainz API using MBID and
set the appropriate metadata.

Configuration
-------------

To configure the plugin, make a ``acousticbrainz:`` section in your
configuration file. There is one option:

- **auto**: Enable AcousticBrainz during ``beet import``.
  Default: ``yes``.
- **force**: By default, beets will not override already fetched acousticbrainz data. To instead fetch acousticbrainz and override data, 
  set the ``force`` option to ``yes``.
  Default: ``no``.