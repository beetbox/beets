AcousticBrainz Plugin
=====================

The ``acousticbrainz`` plugin gets acoustic-analysis information from the
`AcousticBrainz`_ project. The spirit is similar to the
:doc:`/plugins/echonest`.

.. _AcousticBrainz: http://acousticbrainz.org/

Enable the ``acousticbrainz`` plugin in your configuration (see :ref:`using-plugins`) and run it by typing::

    $ beet acousticbrainz [QUERY]

For all tracks with a MusicBrainz recording ID, the plugin currently sets
these fields:

* ``average_loudness``
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
