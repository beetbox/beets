Play Plugin
===========

The ``play`` plugin allows you to pass the results of a query to a music
player in the form of an m3u playlist.

To use the plugin, enable it in your configuration (see
:ref:`using-plugins`). Then use it by invoking the ``beet play`` command with
a query. The command will create a temporary m3u file and open it using an
appropriate application.

By default, the playlist is opened using the ``open`` command on OS X,
``xdg-open`` on other Unixes, and ``start`` on Windows. To configure the
command, you can use a ``play:`` section in your configuration file::

    play:
        command: /Applications/VLC.app/Contents/MacOS/VLC

Enable beets' verbose logging to see the command's output if you need to
debug.
