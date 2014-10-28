ReplayGain Plugin
=================

This plugin adds support for `ReplayGain`_, a technique for normalizing audio
playback levels.

.. _ReplayGain: http://wiki.hydrogenaudio.org/index.php?title=ReplayGain


Installation
------------

This plugin can use one of two backends to compute the ReplayGain values:
GStreamer and mp3gain (and its cousin, aacgain). mp3gain can be easier to
install but GStreamer support more audio formats.

Once installed, this plugin analyzes all files during the import process. This
can be a slow process; to instead analyze after the fact, disable automatic
analysis and use the ``beet replaygain`` command (see below).

GStreamer
`````````

To use `GStreamer`_ for ReplayGain analysis, you will of course need to
install GStreamer and plugins for compatibility with your audio files.
You will need at least GStreamer 1.0 and `PyGObject 3.x`_ (a.k.a. python-gi).

.. _PyGObject 3.x: https://wiki.gnome.org/action/show/Projects/PyGObject
.. _GStreamer: http://gstreamer.freedesktop.org/

Then, enable the ``replaygain`` plugin (see :ref:`using-plugins`) and specify
the GStreamer backend by adding this to your configuration file::

    replaygain:
        backend: gstreamer

mp3gain and aacgain
```````````````````

In order to use this backend, you will need to install the `mp3gain`_
command-line tool or the `aacgain`_ fork thereof. Here are some hints:

* On Mac OS X, you can use `Homebrew`_. Type ``brew install aacgain``.
* On Linux, `mp3gain`_ is probably in your repositories. On Debian or Ubuntu,
  for example, you can run ``apt-get install mp3gain``.
* On Windows, download and install the original `mp3gain`_.

.. _mp3gain: http://mp3gain.sourceforge.net/download.php
.. _aacgain: http://aacgain.altosdesign.com
.. _Homebrew: http://mxcl.github.com/homebrew/

Then, enable the plugin (see :ref:`using-plugins`) and specify the "command"
backend in your configuration file::

    replaygain:
        backend: command

If beets doesn't automatically find the ``mp3gain`` or ``aacgain`` executable,
you can configure the path explicitly like so::

    replaygain:
        command: /Applications/MacMP3Gain.app/Contents/Resources/aacgain


Configuration
-------------

Available options :


- ``auto``: set it to ``no`` to disable replaygain analysis during import.
  Default: ``yes``.
- ``backend``: which backend to use for ReplayGain analysis.
  Must be one of ``gstreamer`` or ``command``.
  Default: ``command``
- ``overwrite``: by default, files that already have ReplayGain tags will not
  be re-analyzed. Set to ``yes`` if you want to analyze *every* file on import.
  Default: ``no``.
- ``targetlevel``: specify a number of decibels for the target loudness level
  Default: ``89``

  These options only work with the "command" backend:

- ``apply``: if you use a player that does not support ReplayGain
  specifications, you can force the volume normalization by applying the gain
  to the file via the ``apply`` option. This is a lossless and reversible
  operation with no transcoding involved.
- ``command``: use it to explicitely enter path to ``mp3gain`` or ``aacgain``
  executable, if beets cannot find it by itself.
  For example: '/Applications/MacMP3Gain.app/Contents/Resources/aacgain'
  Default: ``u''``
- ``noclip``: the use of ReplayGain can cause clipping if the average volume
  of a song is below the target level. By default, a "prevent clipping" option
  named ``noclip`` is enabled to reduce the amount of ReplayGain adjustment to
  whatever amount would keep clipping from occurring.
  Default: ``yes``.

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
