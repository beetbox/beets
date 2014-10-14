BPM Plugin
==========

This ``bpm`` plugin lets you to get the tempo (beats per minute) of a song by tapping out the beat on your keyboard.

Usage
-----

To enable the plugin, you'll need to edit your :doc:`configuration file
</reference/config>` and add ``bpm`` to your ``plugins:`` line.

Then, play a song you want to measure in your favorite media player and type::

     beet bpm <song>

You'll be prompted to press Enter three times to the rhythm. This typically allows to determine the BPM within 5% accuracy.

The plugin works best if you wrap it in a script that gets the playing song. for instance, with ``mpc`` you can do something like::

     beet bpm $(mpc |head -1|tr -d "-")

Credit
------

This plugin is inspired by a similar feature present in the Banshee media player.
