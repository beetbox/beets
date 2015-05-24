Missing Plugin
==============

This plugin adds a new command, ``missing`` or ``miss``, which finds
and lists, for every album in your collection, which or how many
tracks are missing. Listing missing files requires one network call to
MusicBrainz. Merely counting missing files avoids any network calls.

Usage
-----

Add the ``missing`` plugin to your configuration (see :ref:`using-plugins`).
By default, the ``beet missing`` command lists the names of tracks that your
library is missing from each album.
You can customize the output format, count
the number of missing tracks per album, or total up the number of missing
tracks over your whole library, using command-line switches::

      -f FORMAT, --format=FORMAT
                            print with custom FORMAT
      -c, --count           count missing tracks per album
      -t, --total           count total of missing tracks

…or by editing corresponding options.

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
