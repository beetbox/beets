Key Finder Plugin
=================

The `keyfinder` plugin uses the `KeyFinder`_ program to detect the
musical key of track from its audio data and store it in the
'initial_key' field of you database.  It does so
automatically when importing music or through the ``beet keyfinder
[QUERY]`` command.

To use the ``keyfinder`` plugin, enable it in your configuration (see
:ref:`using-plugins`).

Configuration
-------------

Available options:

- ``bin``: The name of the `KeyFinder` program on your system or
  a path to the binary. If you installed the `KeyFinder`_ GUI on a Mac, for
  example, you want something like
  ``/Applications/KeyFinder.app/Contents/MacOS/KeyFinder``.
  Default: ``KeyFinder``.
- ``auto``: If set to `yes`, the plugin will analyze every file on
  import. Otherwise, you need to use the ``beet keyfinder`` command
  explicitly. Default: ``yes``.
- ``overwrite``: If set to ``no``, the import hook and the command will skip
  any file that already has an 'initial_key' in the database.
  Default: ``no``.

.. _KeyFinder: http://www.ibrahimshaath.co.uk/keyfinder/
