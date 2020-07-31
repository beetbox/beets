Key Finder Plugin
=================

The `keyfinder` plugin uses either the `KeyFinder`_ or `keyfinder-cli`_
program to  detect the musical key of a track from its audio data and store
it in the `initial_key` field of your database.  It does so
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
- **bin**: The name of the program use for key analysis. You can use either
  `KeyFinder`_ or `keyfinder-cli`_.
  If you installed the KeyFinder GUI on a Mac, for example, you want
  something like
  ``/Applications/KeyFinder.app/Contents/MacOS/KeyFinder``.
  If using `keyfinder-cli`_, the binary must be named ``keyfinder-cli``.
  Default: ``KeyFinder`` (i.e., search for the program in your ``$PATH``)..
- **overwrite**: Calculate a key even for files that already have an
  `initial_key` value.
  Default: ``no``.

.. _KeyFinder: http://www.ibrahimshaath.co.uk/keyfinder/
.. _keyfinder-cli: https://github.com/EvanPurkhiser/keyfinder-cli/
