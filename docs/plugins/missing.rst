Missing Plugin
==============

This plugin adds a new command, ``missing`` or ``miss``, which finds
and lists, for every album in your collection, which tracks are
missing. Listing missing files requires one network call to
MusicBrainz.

Installation
------------

Enable the plugin by putting ``missing`` on your ``plugins`` line in
:doc:`config file </reference/config>`::

    plugins:
        missing
        ...

Configuration
-------------

The plugin accepts a single configuration directive, ``format``,
either in your configuration file::

    missing:
        format: FMTSTR

or in the command-line::

    $ beet missing --help
    Usage: beet missing [options]

    Options:
      -h, --help            show this help message and exit
      -f FORMAT, --format=FORMAT
                            print with custom FORMAT

format
~~~~~~

The ``format`` option (default: ``None``) lets you specify a specific
format with which to print every track. This uses the same template
syntax as beets’ :doc:`path formats </reference/pathformat>`.  The usage
is inspired by, and therefore similar to, the :ref:`list <list-cmd>`
command.

Examples
-------------------------

List all missing tracks in your collection::

    beet missing

List all missing tracks from 2008::

    beet missing year:2008

Print out a unicode histogram of the missing track years using `spark`_::

    beet missing -f '$year' | spark
    ▆▁▆█▄▇▇▄▇▇▁█▇▆▇▂▄█▁██▂█▁▁██▁█▂▇▆▂▇█▇▇█▆▆▇█▇█▇▆██▂▇


TODO
----

- Add caching.
 
--------------

.. _spark: https://github.com/holman/spark
