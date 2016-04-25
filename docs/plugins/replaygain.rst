ReplayGain Plugin
=================

This plugin adds support for `ReplayGain`_, a technique for normalizing audio
playback levels.

.. _ReplayGain: http://wiki.hydrogenaudio.org/index.php?title=ReplayGain


Installation
------------

This plugin can use one of four backends to compute the ReplayGain values:
GStreamer, mp3gain (and its cousin, aacgain), Python Audio Tools and bs1770gain. mp3gain
can be easier to install but GStreamer, Audio Tools and bs1770gain support more audio
formats.

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

Python Audio Tools
``````````````````

This backend uses the `Python Audio Tools`_ package to compute ReplayGain for
a range of different file formats. The package is not available via PyPI; it
must be installed manually (only versions preceding 3.x are compatible).

On OS X, most of the dependencies can be installed with `Homebrew`_::

    brew install mpg123 mp3gain vorbisgain faad2 libvorbis

.. _Python Audio Tools: http://audiotools.sourceforge.net

bs1770gain
``````````

To use this backend, you will need to install the `bs1770gain`_ command-line
tool. Follow the instructions at the `bs1770gain`_ Web site and ensure that
the tool is on your ``$PATH``.

.. _bs1770gain: http://bs1770gain.sourceforge.net/

Then, enable the plugin (see :ref:`using-plugins`) and specify the
backend in your configuration file::

    replaygain:
        backend: bs1770gain

For Windows users: the tool currently has issues with long and non-ASCII path
names. You may want to use the :ref:`asciify-paths` configuration option until
this is resolved.

Configuration
-------------

To configure the plugin, make a ``replaygain:`` section in your
configuration file. The available options are:

- **auto**: Enable ReplayGain analysis during import.
  Default: ``yes``.
- **backend**: The analysis backend; either ``gstreamer``, ``command``, or ``audiotools``.
  Default: ``command``.
- **overwrite**: Re-analyze files that already have ReplayGain tags.
  Default: ``no``.
- **targetlevel**: A number of decibels for the target loudness level.
  Default: 89.

These options only work with the "command" backend:

- **command**: The path to the ``mp3gain`` or ``aacgain`` executable (if beets
  cannot find it by itself).
  For example: ``/Applications/MacMP3Gain.app/Contents/Resources/aacgain``.
  Default: Search in your ``$PATH``.
- **noclip**: Reduce the amount of ReplayGain adjustment to whatever amount
  would keep clipping from occurring.
  Default: ``yes``.

These options only works with the "bs1770gain" backend:

- **method**: The loudness scanning standard: either `replaygain` for
  ReplayGain 2.0, `ebu` for EBU R128, or `atsc` for ATSC A/85. This dictates
  the reference level: -18, -23, or -24 LUFS respectively. Default:
  `replaygain`
- **chunk_at**: Splits an album in groups of tracks of this amount.
  Usefull when running into memory problems when analysing albums with
  an exceptionally large amount of tracks. Default:5000

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
