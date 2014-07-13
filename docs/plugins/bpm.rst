BPM Plugin
==========

This ``bpm`` plugin allows to determine the bpm (beats per minute) of a song by recording the user's keystrokes. The rationale is that sometimes the bpm of a song cannot be obtained from the echonest database (via the ``echonest`` plugin) or it is simply plain wrong. In all cases when you need to fix the bpm manually, the ``bpm`` plugin comes to the rescue.

Usage
------

Enable the plugin ``bpm`` as described in :doc:`/plugins/index`. To set or modify the bpm of ``<song>``, start playing it, fire up a terminal and type::

     beet bpm <song> 

You'll be prompted to press Enter three times to the rhythm. This typically allows to determine the bpm within 5% accuracy. 

The plugin works best if you wrap it in a script that gets the playing song, for instance with ``mpc`` you can do something like::

     beet bpm $(mpc |head -1|tr -d "-")

Credit
------

This plugin is inspired by a similar feature present in Banshee media player.
