Key Finder Plugin
=================

The `keyfinder` plugin uses the `KeyFinder`_ program to detect the
musical key of track from its audio data and store it in the
`initial_key` field of you database.  If enabled, it does so
automatically when importing music or through the ``beet keyfinder
[QUERY]`` command.

There are a couple of configuration options to customize the behavior of
the plugin. By default they are::

    keyfinder:
        bin: KeyFinder
        auto: yes
        overwrite: no

* ``bin``: The name of the `KeyFinder` program on your system or
  a path to the binary. If you installed the `KeyFinder`_ GUI on a Mac, for
  example, you want something like
  ``/Applications/KeyFinder.app/Contents/MacOS/KeyFinder``.
* ``auto``: If set to `yes`, the plugin will analyze every file on
  import. Otherwise, you need to use the ``beet keyfinder`` command
  explicitly.
* ``overwrite``: If set to `no`, the import hook and the command will skip
  any file that already has an `initial_key` in the database.

.. _KeyFinder: http://www.ibrahimshaath.co.uk/keyfinder/
