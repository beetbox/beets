Duplicates Plugin
==============

This plugin adds a new command, ``duplicates`` or ``dup``, which finds
and lists duplicate tracks or albums in your collection.

Installation
------------

Enable the plugin by putting ``duplicates`` on your ``plugins`` line in
:doc:`config file </reference/config>`::

    plugins:
        duplicates
        ...

Configuration
-------------

By default, the ``beet duplicates`` command lists the names of tracks
in your library that are duplicates. It assumes that Musicbrainz track
and album ids are unique to each track or album. That is, it lists
every track or album with an ID that has been seen before in the
library.

You can customize the output format, count the number of duplicate
tracks or albums, and list all tracks that have duplicates or just the
duplicates themselves. These options can either be specified in the
config file::

    duplicates:
        format: $albumartist - $album - $title
        count: no
        album: no
        full: no

or on the command-line::

    -f FORMAT, --format=FORMAT
                          print with custom FORMAT
    -c, --count           count duplicate tracks or
                          albums
    -a, --album           show duplicate albums instead
                          of tracks
    -F, --full            show all versions of duplicate
                          tracks or albums

format
~~~~~~

The ``format`` option (default: :ref:`list_format_item`) lets you
specify a specific format with which to print every track or
album. This uses the same template syntax as beets’ :doc:`path formats
</reference/pathformat>`.  The usage is inspired by, and therefore
similar to, the :ref:`list <list-cmd>` command.

count
~~~~~

The ``count`` option (default: false) prints a count of duplicate
tracks or albums, with ``format`` hard-coded to ``$albumartist -
$album - $title: $count`` or ``$albumartist - $album: $count`` (for
the ``-a`` option).

album
~~~~~

The ``album`` option (default: false) lists duplicate albums instead
of tracks.

full
~~~~

The ``full`` option (default: false) lists every track or album that
has duplicates, not just the duplicates themselves.

Examples
--------

List all duplicate tracks in your collection::

  beet duplicates

List all duplicate tracks from 2008::

  beet duplicates year:2008

Print out a unicode histogram of duplicate track years using `spark`_::

  beet duplicates -f '$year' | spark
  ▆▁▆█▄▇▇▄▇▇▁█▇▆▇▂▄█▁██▂█▁▁██▁█▂▇▆▂▇█▇▇█▆▆▇█▇█▇▆██▂▇

Print out a listing of all albums with duplicate tracks, and respective counts::

  beet duplicates -ac

The same as the above but include the original album, and show the path::

  beet duplicates -acf '$path'


TODO
----

- Allow deleting duplicates.

.. _spark: https://github.com/holman/spark
