Info Plugin
===========

The ``info`` plugin provides a command that dumps the current tag values for
any file format supported by beets. It works like a supercharged version of
`mp3info`_ or `id3v2`_.

Enable the ``info`` plugin in your configuration (see :ref:`using-plugins`) and
then type::

    $ beet info /path/to/music.flac

and the plugin will enumerate all the tags in the specified file. It also
accepts multiple filenames in a single command-line.

You can also enter a :doc:`query </reference/query>` to inspect music from
your library::

    $ beet info beatles

Command-line options include:

* ``--library`` or ``-l``: Show data from the library database instead of the
  files' tags.
* ``--summarize`` or ``-s``: Merge all the information from multiple files
  into a single list of values. If the tags differ across the files, print
  ``[various]``.

.. _id3v2: http://id3v2.sourceforge.net
.. _mp3info: http://www.ibiblio.org/mp3info/
