Missing Tracks Plugin
=====================

This plugin adds a new command, ``missing`` or ``miss``, which finds and
lists, for every album in your collection, which tracks are missing.
Optionally, it downloads each track it can find on
`Grooveshark <https://grooveshark.com/>`_, by default to a temporary
directory of your choosing for a later ``import``, or directly into your
music collection base directory.

Listing missing files requires one network call to MusicBrainz the first
time it is run. Subsequent listings will retrieve cached entries from
the library [#]_.

Downloading missing files requires four additional network calls: three
to determine with no ambiguity which stream to choose [#]_ and
one to actually download the file.

Installation
------------

The plugin requires `pygrooveshark`_, which you can install using `pip`_
by typing::

    pip install pygrooveshark

After you have ``pygrooveshark`` installed, enable the plugin by putting
``fetchgroove`` on your ``plugins`` line in :doc:`config file
</reference/config>`::

    plugins:
        fetchgroove
        ...

Configuration
-------------

The plugin accepts four configuration directives, either in your
configuration file::

    fetchgroove:
        download: no
        move: no
        format: FMTSTR
        tmpdir: TMPDIR

or in the command-line::

    $ beet missing --help
    Usage: beet missing [options]

    Options:
      -h, --help            show this help message and exit
      -d, --download        download missing songs
      -m, --move            move new items to library
      -f FORMAT, --format=FORMAT
                            print with custom FORMAT
      -t DIR, --tmpdir=DIR  temp DIR to save songs

download
~~~~~~~~

The ``download`` option (default: ``no``) activates the downloading of
all possible missing tracks. Determining whether Grooveshark likes this
or not is left as an exercise to do reader.

move
~~~~

The ``move`` option (default: ``no``) [#]_ renames the downloaded files
to their proper destination in your library. Currently, this option does
*not* trigger an actual ``import`` task. As a result, any actions that
depend on that event will not start. This means no lyrics, art, etc.,
will be fetched automatically during this process.

format
~~~~~~

The ``format`` option (default: ``None``) lets you specify a specific
format with which to print every track. This uses the same template
syntax as beets’ :doc:`path formats </reference/pathformat>`.  The usage
is inspired by, and therefore similar to, the :ref:`list <list-cmd>`
command.

tmpdir
~~~~~~

The ``tmpdir`` option (default: ``None``) skips creating a random
directory and instead lets you choose an incoming files directory, for
example. Unless you plan to import the new files into your collection at
a later time, you shouldn’t need to use this option.

Examples
-------------------------

List all missing tracks in your collection::

    beet missing

List all missing tracks from 2008::

    beet missing year:2008

Download all missing tracks from `Calexico`_ to an incoming directory::

    beet miss --download --tmpdir /tmp/incoming artist:Calexico
    beet import /tmp/incoming ### later...

Download and automatically import all missing tracks::

    beet miss -d -m

Print out a unicode histogram of the missing track years using `spark`_::

    beet missing -f '$year' | spark.py

--------------

.. _pygrooveshark: https://github.com/koehlma/pygrooveshark
.. _pip: http://www.pip-installer.org/
.. _Calexico: http://www.casadecalexico.com/
.. _spark: https://github.com/holman/spark

.. [#] This has the potential to break some use cases that assume each item in
       the collection has a path field (that is, some existing file is attached
       to the item.)

.. [#] Due to a quirk with the Grooveshark search API, we need to search for
       the track title, album, and artist separately.

.. [#] This a separate option from the importer ``move`` option.
