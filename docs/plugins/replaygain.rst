ReplayGain Plugin
=================

This plugin adds support for `ReplayGain`_, a technique for normalizing audio
playback levels.

Installation
------------

This plugin requires `GStreamer`_ with the `rganalysis`_ plugin (part of
`gst-plugins-good`_), `gst-python`_, and the `rgain`_ Python module.

.. _ReplayGain: http://wiki.hydrogenaudio.org/index.php?title=ReplayGain
.. _rganalysis: http://gstreamer.freedesktop.org/data/doc/gstreamer/head/gst-plugins-good-plugins/html/gst-plugins-good-plugins-rganalysis.html
.. _gst-plugins-good: http://gstreamer.freedesktop.org/modules/gst-plugins-good.html
.. _gst-python: http://gstreamer.freedesktop.org/modules/gst-python.html
.. _rgain: https://github.com/cacack/rgain
.. _pip: http://www.pip-installer.org/
.. _GStreamer: http://gstreamer.freedesktop.org/

First, install GStreamer, its "good" plugins, and the Python bindings if your
system doesn't have them already. (The :doc:`/plugins/bpd` and
:doc:`/plugins/chroma` pages have hints on getting GStreamer stuff installed.)
Then install `rgain`_ using `pip`_::

    $ pip install rgain

Finally, add ``replaygain`` to your ``plugins`` line in your
:doc:`/reference/config`, like so::

    [beets]
    plugins = replaygain

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
