Duplicates Plugin
=================

This plugin adds a new command, ``duplicates`` or ``dup``, which finds
and lists duplicate tracks or albums in your collection.

Installation
------------

Enable the plugin by putting ``duplicates`` on your ``plugins`` line in
your :doc:`config file </reference/config>`::

    plugins: duplicates

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
	checksum: no
	copy: no
	keys: mb_trackid album
        album: no
        count: no
        delete: no
        delete_file: no
        format: "$albumartist - $album - $title"
        full: no
        move: no
        path: no
        tag: no
	
	
or on the command-line::

  -h, --help            show this help message and exit
  -f FMT, --format=FMT  print with custom format
  -a, --album           show duplicate albums instead of tracks
  -c, --count           count duplicate tracks or albums
  -C PROG, --checksum=PROG
                        report duplicates based on arbitrary command
  -d, --delete          delete items from library
  -D, --delete-file     delete items from library and disk
  -F, --full            show all versions of duplicate tracks or albums
  -k, --keys            report duplicates based on keys
  -m DEST, --move=DEST  move items to dest
  -o DEST, --copy=DEST  copy items to dest
  -p, --path            print paths for matched items or albums
  -t TAG, --tag=TAG     tag matched items with 'k=v' attribute


format
~~~~~~

The ``format`` option (default: :ref:`list_format_item`) lets you
specify a specific format with which to print every track or
album. This uses the same template syntax as beets’ :doc:`path formats
</reference/pathformat>`.  The usage is inspired by, and therefore
similar to, the :ref:`list <list-cmd>` command.

path
~~~~

Convenience wrapper for ``-f \$path``.

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

keys
~~~~

The ``keys`` option (default: ``[mb_trackid, mb_albumid]``) defines in which track
or album fields duplicates are to be searched. By default, the plugin
uses the musicbrainz track and album IDs for this purpose. Using the
``keys`` option (as a YAML list in the configuration file, or as
space-delimited strings in the command-line), you can extend this behavior
to consider other attributes.

checksum
~~~~~~~~

The ``checksum`` option (default: ``ffmpeg -i {file} -f crc -``) enables the use of
any arbitrary command to compute a checksum of items. It overrides the ``keys``
option the first time it is run; however, because it caches the resulting checksums
as ``flexattrs`` in the database, you can use
``--keys=name_of_the_checksumming_program any_other_keys`` the second time around.

copy
~~~~

The ``copy`` option (default: ``no``) takes a destination base directory into which
it will copy matched items.

move
~~~~

The ``move`` option (default: ``no``) takes a destination base directory into which
it will move matched items.

delete
~~~~~~

The ``delete`` option (default: ``no``) removes matched items from the library.

delete_files
~~~~~~~~~~~~

The ``delete_files`` option (default: ``no``) removes matched items from the library
*and* the disk.

tag
~~~

The ``tag`` option (default: ``no``) takes a ``key=value`` string, and adds a new
``key`` attribute with ``value`` value as a flexattr to the database.

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

Get tracks with the same title, artist, and album::

  beet duplicates -k title albumartist album

Compute Adler CRC32 or MD5 checksums, storing them as flexattrs, and report back
duplicates based on those values::

  beet dup -C 'ffmpeg -i {file} -f crc -'
  beet dup -C 'md5sum {file}'

Copy highly danceable items to ``party`` directory::

  beet dup --copy /tmp/party

Move likely duplicates to ``trash`` directory::

  beet dup --move ${HOME}/.Trash

Delete items from library, and optionally the disk (carefull), if they're Nickelback::

  beet duplicates --delete{-file} --keys albumartist albumartist:nickelback

Tag duplicate items with some flag::
  
  beet duplicates --tag dup=1

TODO
----

- better duplicate disambiaguation strategies (eg, based on bitrate, etc)

.. _spark: https://github.com/holman/spark
