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
  -s, --strict          report duplicates only if all attributes are set
  -k, --keys            report duplicates based on keys
  -M, --merge           merge duplicate items
  -m DEST, --move=DEST  move items to dest
  -o DEST, --copy=DEST  copy items to dest
  -p, --path            print paths for matched items or albums
  -t TAG, --tag=TAG     tag matched items with 'k=v' attribute

Configuration
-------------

To configure the plugin, make a ``duplicates:`` section in your configuration
file. The available options mirror the command-line options:

- **album**: List duplicate albums instead of tracks.
  Default: ``no``.
- **checksum**: Use an arbitrary command to compute a checksum
  of items. This overrides the ``keys`` option the first time it is run;
  however, because it caches the resulting checksum as ``flexattrs`` in the
  database, you can use ``--keys=name_of_the_checksumming_program
  any_other_keys`` (or set configuration ``keys`` option) the second time
  around.
  Default: ``ffmpeg -i {file} -f crc -``.
- **copy**: A destination base directory into which to copy matched
  items.
  Default: none (disabled).
- **count**: Print a count of duplicate tracks or albums in the format
  ``$albumartist - $album - $title: $count`` (for tracks) or ``$albumartist -
  $album: $count`` (for albums).
  Default: ``no``.
- **delete**: Removes matched items from the library and from the disk.
  Default: ``no``
- **format**: A specific format with which to print every track
  or album. This uses the same template syntax as beets'
  :doc:`path formats</reference/pathformat>`.  The usage is inspired by, and
  therefore similar to, the :ref:`list <list-cmd>` command.
  Default: :ref:`format_item`
- **full**: List every track or album that has duplicates, not just the
  duplicates themselves.
  Default: ``no``
- **keys**: Define in which track or album fields duplicates are to be
  searched. By default, the plugin uses the musicbrainz track and album IDs for
  this purpose. Using the ``keys`` option (as a YAML list in the configuration
  file, or as space-delimited strings in the command-line), you can extend this
  behavior to consider other attributes.
  Default: ``[mb_trackid, mb_albumid]``
- **merge**: Merge duplicate items by consolidating tracks and-or
  metadata where possible.
- **move**: A destination base directory into which it will move matched
  items.
  Default: none (disabled).
- **path**: Output the path instead of metadata when listing duplicates.
  Default: ``no``.
- **strict**: Do not report duplicate matches if some of the
  attributes are not defined (ie. null or empty).
  Default: ``no``
- **tag**: A ``key=value`` pair. The plugin will add a new ``key`` attribute
  with ``value`` value as a flexattr to the database for duplicate items.
  Default: ``no``.
- **tiebreak**: Dictionary of lists of attributes keyed by ``items``
  or ``albums`` to use when choosing duplicates. By default, the
  tie-breaking procedure favors the most complete metadata attribute
  set. If you would like to consider the lower bitrates as duplicates,
  for example, set ``tiebreak: items: [bitrate]``.
  Default: ``{}``.

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

Ignore items with undefined keys::

  beet duplicates --strict

Merge and delete duplicate albums with different missing tracks::

  beet duplicates --album --merge --delete

.. _spark: https://github.com/holman/spark
