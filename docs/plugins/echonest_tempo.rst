Echo Nest Tempo Plugin
======================

.. note::

  A newer :doc:`echonest` is available that supersedes this plugin. In
  addition to the tempo, the new plugin can fetch the Echo Nest's full
  complement of acoustic attributes. This older tempo-specific plugin is
  **deprecated**.

The ``echonest_tempo`` plugin fetches and stores a track's tempo (the "bpm"
field) from the `Echo Nest API`_.

.. _Echo Nest API: http://developer.echonest.com/

Installing Dependencies
-----------------------

This plugin requires the pyechonest library in order to talk to the EchoNest
API.

There are packages for most major linux distributions, you can download the
library from the Echo Nest, or you can install the library from `pip`_,
like so::

    $ pip install pyechonest

.. _pip: http://pip.openplans.org/

Configuration
-------------

Available options:

- ``auto``: set to ``no``to disable automatic tempo fetching during import.
  Default: ``true``.
- ``apikey``: set this option to specify your own EchoNest API key.
  You can `apply for your own`_ for free from the EchoNest.
  Default: beets includes its own Echo Nest API key.

.. _apply for your own: http://developer.echonest.com/account/register

Fetch Tempo During Import
-------------------------

To automatically fetch the tempo for songs you import, just enable the plugin
by putting ``echonest_tempo`` on your config file's ``plugins`` line (see
:doc:`/plugins/index`). When importing new files, beets will now fetch the
tempo for files that don't already have them. The bpm field will be stored in
the beets database. If the ``import.write`` config option is on, then the tempo
will also be written to the files' tags.

This behavior can be disabled with the ``autofetch`` config option (see below).

Fetching Tempo Manually
-----------------------

The ``tempo`` command provided by this plugin fetches tempos for
items that match a query (see :doc:`/reference/query`). For example,
``beet tempo magnetic fields absolutely cuckoo`` will get the tempo for the
appropriate Magnetic Fields song, ``beet tempo magnetic fields`` will get
tempos for all my tracks by that band, and ``beet tempo`` will get tempos for
my entire library. The tempos will be added to the beets database and, if
``import.write`` is on, embedded into files' metadata.

The ``-p`` option to the ``tempo`` command makes it print tempos out to the
console so you can view the fetched (or previously-stored) tempos.
