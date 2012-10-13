ReplayGain Plugin
=================

This plugin adds support for `ReplayGain`_, a technique for normalizing audio
playback levels.

.. _ReplayGain: http://wiki.hydrogenaudio.org/index.php?title=ReplayGain

Installation
------------

This plugin uses the `mp3gain`_ command-line tool or the `aacgain`_ fork
thereof. To get started, install this tool:

* On Mac OS X, you can use `Homebrew`_. Type ``brew install aacgain``.
* On Linux, `mp3gain`_ is probably in your repositories. On Debian or Ubuntu,
  for example, you can run ``apt-get install mp3gain``.
* On Windows, download and install the original `mp3gain`_.

.. _mp3gain: http://mp3gain.sourceforge.net/download.php
.. _aacgain: http://aacgain.altosdesign.com
.. _Homebrew: http://mxcl.github.com/homebrew/

Then enable the ``replaygain`` plugin (see :doc:`/reference/config`). If beets
doesn't automatically find the ``mp3gain`` or ``aacgain`` executable, you can
configure the path explicitly like so::

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

The target level can be modified to any target dB with the ``targetlevel``
option (default: 89 dB).

ReplayGain can normalize an entire album's loudness while allowing the dynamics
from song to song on the album to remain intact. This is called "album gain" and
is especially important for classical music albums with large loudness ranges.
"Track gain," in which each song is considered independently, is used by
default. To override this, use the ``albumgain`` option::

    [replaygain]
    albumgain: yes

If you use a player that does not support ReplayGain specifications, you can
force the volume normalization by applying the gain to the file via the
``apply`` option. This is a lossless and reversible operation with no
transcoding involved. The use of ReplayGain can cause clipping if the average
volume of a song is below the target level. By default, a "prevent clipping"
option named ``noclip`` is enabled to reduce the amount of ReplayGain adjustment
to whatever amount would keep clipping from occurring.
