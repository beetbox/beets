AcousticBrainz Plugin
=====================

The ``acousticbrainz`` plugin gets acoustic-analysis information from the
`AcousticBrainz`_ project.

.. _AcousticBrainz: https://acousticbrainz.org/

Enable the ``acousticbrainz`` plugin in your configuration (see :ref:`using-plugins`) and run it by typing::

    $ beet acousticbrainz [-f] [QUERY]

By default, the command will only look for AcousticBrainz data when the tracks
don't already have it; the ``-f`` or ``--force`` switch makes it re-download
data even when it already exists. If you specify a query, only matching tracks
will be processed; otherwise, the command processes every track in your
library.

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
* ``moods_mirex``
* ``rhythm``
* ``timbre``
* ``tonal``
* ``voice_instrumental``

The metadata written to files follows the tag naming scheme of MusicBrainz
Picard's AcousticBrainz plugin. Here's an example:

    ab:lo:average_loudness=0.887623310089
    ab:lo:tonal:chords_changes_rate=0.082755811512
    ab:lo:tonal:chords_key=A#
    ab:lo:tonal:chords_number_rate=0.002038320526
    ab:lo:tonal:chords_scale=minor
    ab:hi:danceability:danceable=0.000000000000
    ab:hi:gender=female
    ab:hi:genre_rosamerica=rhy
    ab:lo:tonal:key_strength=0.654201686382
    ab:hi:mood_acoustic:acoustic=0.081802986562
    ab:hi:mood_aggressive:aggressive=0.000000000000
    ab:hi:mood_electronic:electronic=0.979390621185
    ab:hi:mood_happy:happy=0.085078120232
    ab:hi:mood_party:party=0.000015778420
    ab:hi:mood_relaxed:relaxed=0.808817088604
    ab:hi:mood_sad:sad=0.109234951437
    ab:hi:moods_mirex=Cluster5
    ab:hi:ismir04_rhythm=ChaChaCha
    ab:hi:timbre=dark
    ab:hi:tonal_atonal:tonal=0.002889123978
    ab:hi:voice_instrumental=instrumental

For musical key and BPM information the default metadata fields ``initial_key``
and ``bpm`` are used.

Automatic Tagging
-----------------

To automatically tag files using AcousticBrainz data during import, just
enable the ``acousticbrainz`` plugin (see :ref:`using-plugins`). When importing
new files, beets will query the AcousticBrainz API using MBID and
set the appropriate metadata.

Configuration
-------------

To configure the plugin, make a ``acousticbrainz:`` section in your
configuration file. There are three options:

- **auto**: Enable AcousticBrainz during ``beet import``.
  Default: ``yes``.
- **force**: Download AcousticBrainz data even for tracks that already have
  it.
  Default: ``no``.
- **tags**: Which tags from the list above to set on your files.
  Default: [] (all)
