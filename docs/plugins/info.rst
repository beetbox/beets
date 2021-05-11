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

If you just want to see specific properties you can use the
``--include-keys`` option to filter them. The argument is a
comma-separated list of field names. For example::

    $ beet info -i 'title,mb_artistid' beatles

Will only show the ``title`` and ``mb_artistid`` properties.  You can add the
``-i`` option multiple times to the command line.

Additional command-line options include:

* ``--library`` or ``-l``: Show data from the library database instead of the
  files' tags.
* ``--summarize`` or ``-s``: Merge all the information from multiple files
  into a single list of values. If the tags differ across the files, print
  ``[various]``.
* ``--format`` or ``-f``: Specify a specific format with which to print every
  item. This uses the same template syntax as beets’ :doc:`path formats
  </reference/pathformat>`.
* ``--keys-only`` or ``-k``: Show the name of the tags without the values.

.. _id3v2: http://id3v2.sourceforge.net
.. _mp3info: https://www.ibiblio.org/mp3info/
