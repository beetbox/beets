MPDUpdate Plugin
================

``mpdupdate`` is a very simple plugin for beets that lets you automatically
update `MPD`_'s index whenever you change your beets library.

.. _MPD: http://mpd.wikia.com/wiki/Music_Player_Daemon_Wiki

To use it, enable it in your ``.beetsconfig`` by putting ``mpdupdate`` on your ``plugins`` line. Your ``.beetsconfig`` should look like this::

    [beets]
    plugins: mpdupdate

Then, you'll probably want to configure the specifics of your MPD server. You
can do that using an ``[mpdupdate]`` section in your ``.beetsconfig``, which
looks like this::

    [mpdupdate]
    host = localhost
    port = 6600
    password = seekrit

With that all in place, you'll see beets send the "update" command to your MPD server every time you change your beets library.
