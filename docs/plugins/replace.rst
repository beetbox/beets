Replace Plugin
==============

The ``replace`` plugin provides a command that replaces the audio file of a
track, while keeping the name and tags intact. It should save some time when you
get the wrong version of a song.

Enable the ``replace`` plugin in your configuration (see :ref:`using-plugins`)
and then type:

::

    $ beet replace <query> <path>

The plugin will show you a list of files for you to pick from, and then ask for
confirmation.

The file you pick will be replaced with the file at `path`. Then, the new file's metadata
will be synced with the database. This means that the tags in the database for that track
(`title`, `artist`, etc.) will be written to the new file, and the `path` and `mtime` fields
in the database will be updated to match the new file's path and the current modification time.

Consider using the ``replaygain`` command from the :doc:`/plugins/replaygain`
plugin, if you usually use it during imports.
