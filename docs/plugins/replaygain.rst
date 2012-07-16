ReplayGain Plugin
=================

This plugin adds support for `ReplayGain`_, a technique for normalizing audio
playback levels.

.. _ReplayGain: http://wiki.hydrogenaudio.org/index.php?title=ReplayGain

Installation
------------

This plugin use a command line tool to compute the ReplayGain information:

* On Mac OS X, you can use `Homebrew`_. Type ``brew install aacgain``.
* On Windows, install the original `mp3gain`_.

.. _mp3gain: http://mp3gain.sourceforge.net/download.php
.. _Homebrew: http://mxcl.github.com/homebrew/

To enable the plugin, you’ll need to edit your .beetsconfig file and add the 
line ``plugins: replaygain``.

    [beets]
    plugins = replaygain

In case beets doesn't find the path to the ReplayGain binary, you can write it
explicitely in the plugin options like so :

    [replaygain]
    command: /Applications/MacMP3Gain.app/Contents/Resources/aacgain

Usage & Configuration
---------------------

The plugin will automatically analyze albums and individual tracks as you import
them. It writes tags to each file according to the `ReplayGain`_ specification;
if your player supports these tags, it can use them to do level adjustment.

By default, files that already have ReplayGain tags will not be re-analyzed. If
you want to analyze *every* file on import, you can set the ``overwrite`` option
for the plugin in your :doc:`/reference/config`, like so::

    [replaygain]
    overwrite: yes

The target level can be modified to any target dB with the ``targetlevel``option
(default: 89 dB).

ReplayGain allows to make consistent the loudness of a whole album while allowing
 the dynamics from song to song on the album to remain intact. This is called
 'Album Gain' (especially important for classical music albums with large loudness
 range). 
'Track Gain' (each song considered independently) mode is used by default but can 
be changed with ``albumgain`` switch::

    [replaygain]
    albumgain: yes

If you use a player that does not support ReplayGain specifications, you may want
to force the volume normalization by applying the gain to the file via the ``apply`` 
option. This is a lossless and revertable operation with no decoding/re-encoding involved.
The use of ReplayGain can cause clipping if the average volume of a song is below
the target level. By default a "prevent clipping" feature named ``noclip`` is
enabled to reduce the amount of ReplayGain adjustment to whatever amount would
keep clipping from occurring.