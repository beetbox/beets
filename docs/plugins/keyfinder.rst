Key Finder Plugin
=================

The `keyfinder` plugin uses the `KeyFinder`_ program to detect the
musical key of track from its audio data and store it in the
`initial_key` field of your database.  It does so
automatically when importing music or through the ``beet keyfinder
[QUERY]`` command.

To use the ``keyfinder`` plugin, enable it in your configuration (see
:ref:`using-plugins`).

Configuration
-------------

To configure the plugin, make a ``keyfinder:`` section in your
configuration file. The available options are:

- **auto**: Analyze every file on
  import. Otherwise, you need to use the ``beet keyfinder`` command
  explicitly.
  Default: ``yes``
- **bin**: The name of the `KeyFinder`_ program on your system or
  a path to the binary. If you installed the KeyFinder GUI on a Mac, for
  example, you want something like
  ``/Applications/KeyFinder.app/Contents/MacOS/KeyFinder``.
  Default: ``KeyFinder`` (i.e., search for the program in your ``$PATH``)..
- **overwrite**: Calculate a key even for files that already have an
  `initial_key` value.
  Default: ``no``.

.. _KeyFinder: http://www.ibrahimshaath.co.uk/keyfinder/
