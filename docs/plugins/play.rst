Play Plugin
===========

The ``play`` plugin allows you to pass the results of a query to a music
player in the form of an m3u playlist.

To use the plugin, enable it in your configuration (see
:ref:`using-plugins`). Then use it by invoking the ``beet play`` command with
a query. The command will create a temporary m3u file and open it using an
appropriate application. You can query albums instead of tracks using the
``-a`` option.

By default, the playlist is opened using the ``open`` command on OS X,
``xdg-open`` on other Unixes, and ``start`` on Windows. To configure the
command, you can use a ``play:`` section in your configuration file::

    play:
        command: /Applications/VLC.app/Contents/MacOS/VLC

You can also specify additional space-separated options to command (like you
would on the command-line)::

    play:
        command: /usr/bin/command --option1 --option2 some_other_option

When using the ``-a`` option, the m3u will have the paths to each track on
the matched albums. If you wish to have folders instead, you can change that
by setting ``use_files: False`` in your configuration file.

Enable beets' verbose logging to see the command's output if you need to
debug.
