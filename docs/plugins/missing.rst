Missing Plugin
==============

This plugin adds a new command, ``missing`` or ``miss``, which finds and lists
missing tracks for albums in your collection. Each album requires one network
call to album data source.

Usage
-----

Add the ``missing`` plugin to your configuration (see :ref:`using-plugins`).
The ``beet missing`` command fetches album information from the origin data
source and lists names of the **tracks** that are missing from your library.

It can also list the names of missing **albums** for each artist, although this
is limited to albums from the MusicBrainz data source only.

You can customize the output format, show missing counts instead of track
titles, or display the total number of missing entities across your entire
library::

      -f FORMAT, --format=FORMAT
                            print with custom FORMAT
      -c, --count           count missing tracks per album
      -t, --total           count totals across the entire library
      -a, --album           show missing albums for artist instead of tracks for album

…or by editing the corresponding configuration options.

.. warning::

    Option ``-c`` is ignored when used with ``-a``.

Configuration
-------------

To configure the plugin, make a ``missing:`` section in your
configuration file. The available options are:

- **count**: Print a count of missing tracks per album, with ``format``
  defaulting to ``$albumartist - $album: $missing``.
  Default: ``no``.
- **format**: A specific format with which to print every
  track. This uses the same template syntax as beets'
  :doc:`path formats </reference/pathformat>`. The usage is inspired by, and
  therefore similar to, the :ref:`list <list-cmd>` command.
  Default: :ref:`format_item`.
- **total**: Print a single count of missing tracks in all albums.
  Default: ``no``.

Here's an example ::

    missing:
        format: $albumartist - $album - $title
        count: no
        total: no

Template Fields
---------------

With this plugin enabled, the ``$missing`` template field expands to the
number of tracks missing from each album.

Examples
--------

List all missing tracks in your collection::

  beet missing

List all missing albums in your collection::

  beet missing -a

List all missing tracks from 2008::

  beet missing year:2008

Print out a unicode histogram of the missing track years using `spark`_::

  beet missing -f '$year' | spark
  ▆▁▆█▄▇▇▄▇▇▁█▇▆▇▂▄█▁██▂█▁▁██▁█▂▇▆▂▇█▇▇█▆▆▇█▇█▇▆██▂▇

Print out a listing of all albums with missing tracks, and respective counts::

  beet missing -c

Print out a count of the total number of missing tracks::

  beet missing -t

Call this plugin from other beet commands::

  beet ls -a -f '$albumartist - $album: $missing'

.. _spark: https://github.com/holman/spark
