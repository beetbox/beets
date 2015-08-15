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

The ``--args``-argument can be used to pass additional parameters to the
command. The position for these is marked by ``{}`` in the command-section.

For additional features and usage of the ``--args``-argument, see the example
below.

Configuration
-------------

To configure the plugin, make a ``play:`` section in your
configuration file. The available options are:

- **command**: The command used to open the playlist.
  Default: ``open`` on OS X, ``xdg-open`` on other Unixes and ``start`` on
  Windows. Insert ``{}`` to make use of the ``--args``-feature.
- **relative_to**: Emit paths relative to base directory.
  Default: None.
- **use_folders**: When using the ``-a`` option, the m3u will contain the
  paths to each track on the matched albums. Enable this option to
  store paths to folders instead.
  Default: ``no``.
- **optargs**: Static, additional parameters that may be inserted
  using ``--args``. For this to work, you need ``{}`` inserted into your
  command-section of the config file as well as into the parameter given to
  ``--args`` (see example)

Args-Example
------------

Assume you have the following in your config file::

    play:
	    command: player --opt1 arg1 {} --opt2
		args: --opt3

If you just call ``beet play`` without the usage of ``--args``, the command
will be called as if the ``{}`` wasn't there::

    player --opt1 arg1 --opt2

If ``--args`` is given, the ``{}`` gets replaced by the argument, thus
``beet play --args "--opt4"`` results in a call of::

    player --opt1 arg1 --opt4 --opt2

To insert the options configured with the args-key in the config-file,
call ``beet play --args "{}"``, resulting in::

    player --opt1 arg1 --opt3 --opt2

Of course, this can be combined with other parameters as well, like in
``beet play --args "{} --opt4"``, which calls the following::

    player --opt1 arg1 --opt3 --opt4 --opt2
