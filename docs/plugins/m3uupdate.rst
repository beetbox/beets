m3uUpdate Plugin
================

The ``m3uupdate`` plugin keeps track of newly imported music in a central
``.m3u`` playlist file. This file can be used to add new music to other players,
such as iTunes.

To use the plugin, just put ``m3uupdate`` on the ``plugins`` line in your
:doc:`/reference/config`::

    [beets]
    plugins: m3uupdate

Every time an album or singleton item is imported, new paths will be written to
the playlist file. By default, the plugin uses a file called ``imported.m3u``
inside your beets library directory. To use a different file, just set the
``m3u`` parameter inside the ``m3uupdate`` config section, like so::

    [m3uupdate]
    m3u: ~/music.m3u
