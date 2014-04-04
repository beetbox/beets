ReplayGain Plugin
=================

This plugin adds support for `ReplayGain`_, a technique for normalizing audio
playback levels.

.. _ReplayGain: http://wiki.hydrogenaudio.org/index.php?title=ReplayGain

Installation
------------

This plugin can use one of two backends to compute the ReplayGain values

GStreamer
`````````

This backend uses the popular `GStreamer`_ multimedia framework.
In order to use this backend, you will need to install the GStreamer library
as well as a set of plugins for handling your selection of audio files.
Some linux distributions don't package plugins for some popular formats in
their default repositories, and packages for those plugins need to be
downloaded from elsewhere or compiled from source.

The minimal version of the GStreamer library supported by this backend is 1.0
The 0.x branch (which is the default on some older distributions) is not
supported.

.. _GStreamer: http://gstreamer.freedesktop.org/

Then enable the GStreamer backend of the ``replaygain`` plugin
(see :doc:`/reference/config`) add the following to your config file::

    replaygain:
        backend: gstreamer


MP3Gain-based command-line tools
````````````````````````````````

In order to use this backend, you will need to install the `mp3gain`_
command-line tool or the `aacgain`_ fork thereof. To get started, install this
tool:

* On Mac OS X, you can use `Homebrew`_. Type ``brew install aacgain``.
* On Linux, `mp3gain`_ is probably in your repositories. On Debian or Ubuntu,
  for example, you can run ``apt-get install mp3gain``.
* On Windows, download and install the original `mp3gain`_.

.. _mp3gain: http://mp3gain.sourceforge.net/download.php
.. _aacgain: http://aacgain.altosdesign.com
.. _Homebrew: http://mxcl.github.com/homebrew/

Then enable the MP3gain backend of the ``replaygain`` plugin (see :doc:`/reference/config`). If beets
doesn't automatically find the ``mp3gain`` or ``aacgain`` executable, you can
configure the path explicitly like so::

    replaygain:
        backend: command
        command: /Applications/MacMP3Gain.app/Contents/Resources/aacgain

Usage & Configuration
---------------------

The plugin will automatically analyze albums and individual tracks as you import
them. It writes tags to each file according to the `ReplayGain`_ specification;
if your player supports these tags, it can use them to do level adjustment.

Note that some of these options are backend specific and are not currently
supported on all backends.

By default, files that already have ReplayGain tags will not be re-analyzed. If
you want to analyze *every* file on import, you can set the ``overwrite`` option
for the plugin in your :doc:`configuration file </reference/config>`, like so::

    replaygain:
        overwrite: yes

The target level can be modified to any target dB with the ``targetlevel``
option (default: 89 dB).

When analyzing albums, this plugin can calculates an "album gain" alongside
individual track gains. Album gain normalizes an entire album's loudness while
allowing the dynamics from song to song on the album to remain intact. This is
especially important for classical music albums with large loudness ranges.
Players can choose which gain (track or album) to honor. By default, only
per-track gains are used; to calculate album gain also, set the ``albumgain``
option to ``yes``.

If you use a player that does not support ReplayGain specifications, you can
force the volume normalization by applying the gain to the file via the
``apply`` option. This is a lossless and reversible operation with no
transcoding involved. The use of ReplayGain can cause clipping if the average
volume of a song is below the target level. By default, a "prevent clipping"
option named ``noclip`` is enabled to reduce the amount of ReplayGain adjustment
to whatever amount would keep clipping from occurring.

Manual Analysis
---------------

By default, the plugin will analyze all items an albums as they are implemented.
However, you can also manually analyze files that are already in your library.
Use the ``beet replaygain`` command::

    $ beet replaygain [-a] [QUERY]

The ``-a`` flag analyzes whole albums instead of individual tracks. Provide a
query (see :doc:`/reference/query`) to indicate which items or albums to
analyze.

ReplayGain analysis is not fast, so you may want to disable it during import.
Use the ``auto`` config option to control this::

    replaygain:
        auto: no
