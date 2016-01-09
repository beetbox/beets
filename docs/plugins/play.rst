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
  Windows. Insert ``{}`` to make use of the ``--args``-feature.
- **relative_to**: If set, emit paths relative to this directory.
  Default: None.
- **use_folders**: When using the ``-a`` option, the m3u will contain the
  paths to each track on the matched albums. Enable this option to
  store paths to folders instead.
  Default: ``no``.
- **raw**: Instead of creating a temporary m3u playlist and then opening it,
  simply call the command with the paths returned by the query as arguments.
  Default: ``no``.
- **warning_threshold**: Set the minimum number of files to play which will
  trigger a warning to be emitted. If set to ``no``, warning are never issued.
  Default: 100.

Optional Arguments
------------------

The ``--args`` (or ``-A``) flag to the ``play`` command lets you specify
additional arguments for your player command. Options are inserted after the
configured ``command`` string and before the playlist filename.

For example, if you have the plugin configured like this::

    play:
        command: mplayer -quiet

and you occasionally want to shuffle the songs you play, you can type::

    $ beet play --args -shuffle

to get beets to execute this command::

    mplayer -quiet -shuffle /path/to/playlist.m3u

instead of the default.

If you need to insert arguments somewhere other than the end of the
``command`` string, use ``$args`` to indicate where to insert them. For
example::

    play:
        command: mpv $args --playlist

indicates that you need to insert extra arguments before specifying the
playlist.

Note on the Leakage of the Generated Playlists
_______________________________________________

Because the command that will open the generated ``.m3u`` files can be
arbitrarily configured by the user, beets won't try to delete those files. For
this reason, using this plugin will leave one or several playlist(s) in the
directory selected to create temporary files (Most likely ``/tmp/`` on Unix-like
systems. See `tempfile.tempdir`_.). Leaking those playlists until they are
externally wiped could be an issue for privacy or storage reasons. If this is
the case for you, you might want to use the ``raw`` config option described
above.

.. _tempfile.tempdir: https://docs.python.org/2/library/tempfile.html#tempfile.tempdir
