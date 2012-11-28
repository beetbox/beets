Info Plugin
===========

The ``info`` plugin provides a command that dumps the current tag values for
any file format supported by beets. It works like a supercharged version of
`mp3info`_ or `id3v2`_.

Enable the plugin and then type::

    $ beet info /path/to/music.flac

and the plugin will enumerate all the tags in the specified file. It also
accepts multiple filenames in a single command-line.

.. _id3v2: http://id3v2.sourceforge.net
.. _mp3info: http://www.ibiblio.org/mp3info/
