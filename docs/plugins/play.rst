Play Plugin
===========

The ``play`` plugin allows you to pass the results of a query to a music
player in the form of an m3u playlist.

Usage
-----

To use the ``play`` plugin, enable it in your configuration (see
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

While playing you'll be able to interact with the player if it is a
command-line oriented, and you'll get its output in real time.

Configuration
-------------

To configure the plugin, make a ``play:`` section in your
configuration file. The available options are:

- **command**: The command used to open the playlist.
  Default: ``open`` on OS X, ``xdg-open`` on other Unixes and ``start`` on
  Windows.
- **relative_to**: Emit paths relative to base directory.
  Default: None.
- **use_folders**: When using the ``-a`` option, the m3u will contain the
  paths to each track on the matched albums. Enable this option to
  store paths to folders instead.
  Default: ``no``.
