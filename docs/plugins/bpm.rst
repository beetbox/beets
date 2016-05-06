BPM Plugin
==========

This ``bpm`` plugin lets you to get the tempo (beats per minute) of a song by
tapping out the beat on your keyboard.

Usage
-----

To use the ``bpm`` plugin, first enable it in your configuration (see
:ref:`using-plugins`).

Then, play a song you want to measure in your favorite media player and type::

     beet bpm <song>

You'll be prompted to press Enter three times to the rhythm. This typically
allows to determine the BPM within 5% accuracy.

The plugin works best if you wrap it in a script that gets the playing song.
for instance, with ``mpc`` you can do something like::

     beet bpm $(mpc |head -1|tr -d "-")

If :ref:`import.write <config-import-write>` is ``yes``, the song's tags are
written to disk.

Configuration
-------------

To configure the plugin, make a ``bpm:`` section in your configuration file.
The available options are:

- **max_strokes**: The maximum number of strokes to accept when tapping out the
  BPM.
  Default: 3.
- **overwrite**: Overwrite the track's existing BPM.
  Default: ``yes``.

Credit
------

This plugin is inspired by a similar feature present in the Banshee media
player.
