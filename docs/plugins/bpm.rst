BPM Plugin
==========

This ``bpm`` plugin allows to determine the bpm (beats per minute) of a song by recording the user's keystrokes. The rationale is that sometimes the bpm of a song cannot be obtained from the echonest database (via the ``echonest`` plugin) or it is simply plain wrong. Whenever you need to fix the bpm of a song manually, the ``bpm`` plugin comes to the rescue.

Usage
------

First, enable the plugin ``bpm`` as described in :doc:`/plugins/index`. Then, suppose you want to set or modify the bpm of ``<song>``, where ``<song>`` is any valid query that matches the song of interest. Start playing it with your favorite media player, fire up a terminal and type::

     beet bpm <song> 

You'll be prompted to press Enter three times to the rhythm. This typically allows to determine the bpm within 5% accuracy. 

The plugin works best if you wrap it in a script that gets the playing song, for instance with ``mpc`` you can do something like::

     beet bpm $(mpc |head -1|tr -d "-")

Credit
------

This plugin is inspired by a similar feature present in the Banshee media player.
