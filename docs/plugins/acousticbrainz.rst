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

Here's an example of how the metadata will look like when written to mp3 files:

   Essentia_ab Average Loudness=0.523903489113
   Essentia_ab Chords Changes Rate=0.040707375854
   Essentia_ab Chords Key=C
   Essentia_ab Chords Number Rate=0.001668335055
   Essentia_ab Chords Scale=minor
   Essentia_ab Danceable=0.500000000000
   Essentia_ab Gender=male
   Essentia_ab Genre Rosamerica=rhy
   Essentia_ab Ismir04 Rhythm=0.00
   Essentia_ab Key Strength=0.677906572819
   Essentia_ab Mood Acoustic=0.227068513632
   Essentia_ab Mood Aggressive=0.074388481677
   Essentia_ab Mood Electronic=0.938988804817
   Essentia_ab Mood Happy=0.070650450885
   Essentia_ab Mood Party=0.265368700027
   Essentia_ab Mood Relaxed=0.943796038628
   Essentia_ab Mood Sad=0.398043692112
   Essentia_ab Moods Mirex=Cluster5
   Essentia_ab Timbre=dark
   Essentia_ab Tonal=0.506820321083
   Essentia_ab Voice Instrumental=instrumental

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
