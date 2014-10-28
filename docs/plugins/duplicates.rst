Duplicates Plugin
=================

This plugin adds a new command, ``duplicates`` or ``dup``, which finds
and lists duplicate tracks or albums in your collection.

Usage
-----

To use the ``duplicates`` plugin, first enable it in your configuration (see
:ref:`using-plugins`).

By default, the ``beet duplicates`` command lists the names of tracks
in your library that are duplicates. It assumes that Musicbrainz track
and album ids are unique to each track or album. That is, it lists
every track or album with an ID that has been seen before in the
library.
You can customize the output format, count the number of duplicate
tracks or albums, and list all tracks that have duplicates or just the
duplicates themselves via command-line switches ::

  -h, --help            show this help message and exit
  -f FMT, --format=FMT  print with custom format
  -a, --album           show duplicate albums instead of tracks
  -c, --count           count duplicate tracks or albums
  -C PROG, --checksum=PROG
                        report duplicates based on arbitrary command
  -d, --delete          delete items from library and disk
  -F, --full            show all versions of duplicate tracks or albums
  -k, --keys            report duplicates based on keys
  -m DEST, --move=DEST  move items to dest
  -o DEST, --copy=DEST  copy items to dest
  -p, --path            print paths for matched items or albums
  -t TAG, --tag=TAG     tag matched items with 'k=v' attribute

Configuration
-------------

Available options (mirroring the CLI ones) :

- ``album`` lists duplicate albums instead of tracks.
  Default: ``no``.
- ``checksum`` enables the use of any arbitrary command to compute a checksum
  of items. It overrides the ``keys`` option the first time it is run; however,
  because it caches the resulting checksum as ``flexattrs`` in the database,
  you can use ``--keys=name_of_the_checksumming_program any_other_keys`` (or
  set configuration ``keys``option) the second time around.
  Default: ``ffmpeg -i {file} -f crc -``.
- ``copy`` takes a destination base directory into which it will copy matched
  items.
  Default: ``no``.
- `count` prints a count of duplicate tracks or albums, with ``format``
  hard-coded to ``$albumartist - $album - $title: $count`` or ``$albumartist -
  $album: $count`` (for the ``-a`` option).
  Default: ``no``.
- ``delete`` removes matched items from the library and from the disk.
  Default: ``no``
- `format` lets you specify a specific format with which to print every track
  or album. This uses the same template syntax as beets
  ’:doc:`path formats</reference/pathformat>`.  The usage is inspired by, and
  therefore similar to, the :ref:`list <list-cmd>` command.
  Default: :ref:`list_format_item`
- ``full`` lists every track or album that has duplicates, not just the
  duplicates themselves.
  Default: ``no``.
- ``keys`` defines in which track or album fields duplicates are to be
  searched. By default, the plugin uses the musicbrainz track and album IDs for
  this purpose. Using the ``keys`` option (as a YAML list in the configuration
  file, or as space-delimited strings in the command-line), you can extend this
  behavior to consider other attributes.
  Default: ``[mb_trackid, mb_albumid]``
- ``move`` takes a destination base directory into which it will move matched
  items.
  Default: ``no``.
- `path` is a convenience wrapper for ``-f \$path``.
  Default: ``no``.
- ``tag`` takes a ``key=value`` string, and adds a new ``key`` attribute with
  ``value`` value as a flexattr to the database.
  Default: ``no``.

Examples
--------

List all duplicate tracks in your collection::

  beet duplicates

List all duplicate tracks from 2008::

  beet duplicates year:2008

Print out a unicode histogram of duplicate track years using `spark`_::

  beet duplicates -f '$year' | spark
  ▆▁▆█▄▇▇▄▇▇▁█▇▆▇▂▄█▁██▂█▁▁██▁█▂▇▆▂▇█▇▇█▆▆▇█▇█▇▆██▂▇

Print out a listing of all albums with duplicate tracks, and respective
counts::

  beet duplicates -ac

The same as the above but include the original album, and show the path::

  beet duplicates -acf '$path'

Get tracks with the same title, artist, and album::

  beet duplicates -k title albumartist album

Compute Adler CRC32 or MD5 checksums, storing them as flexattrs, and report
back duplicates based on those values::

  beet dup -C 'ffmpeg -i {file} -f crc -'
  beet dup -C 'md5sum {file}'

Copy highly danceable items to ``party`` directory::

  beet dup --copy /tmp/party

Move likely duplicates to ``trash`` directory::

  beet dup --move ${HOME}/.Trash

Delete items (careful!), if they're Nickelback::

  beet duplicates --delete --keys albumartist albumartist:nickelback

Tag duplicate items with some flag::

  beet duplicates --tag dup=1


.. _spark: https://github.com/holman/spark
