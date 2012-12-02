EchoNest Tempo Plugin
=============

The ``echonest_tempo`` plugin fetches and stores a track's tempo (bpm field)
 from the `EchoNest API`_

.. _EchoNest API: http://developer.echonest.com/

Installing Dependencies
-----------------------

This plugin requires the pyechonest library in order to talk to the EchoNest 
API.

There are packages for most major linux distributions, you can download the
library from the EchoNest, or you can install the library from `pip`_, 
like so::

    $ pip install pyacoustid

.. _pip: http://pip.openplans.org/

Configuring
-----------

The plugin requires an EchoNest API key in order to function. To do this,
first `apply for an API key`_ from the EchoNest.  Then, add the key to 
your :doc:`/reference/config` as the value ``apikey`` in a section called 
``echonest_tempo`` like so::

    [echonest_tempo]
    apikey=YOUR_API_KEY

In addition, this plugin has one configuration option, ``autofetch``, which 
lets you disable automatic tempo fetching during import. To do so, add this
to your ``~/.beetsconfig``::

    [echonest_tempo]
    apikey=YOUR_API_KEY
    autofetch: no

.. _apply for an API key: http://developer.echonest.com/account/register

Fetch Tempo During Import
--------------------------

To automatically fetch the tempo for songs you import, just enable the plugin 
by putting ``echonest_tempo`` on your config file's ``plugins`` line (see
:doc:`/plugins/index`), along with adding your EchoNest API key to your
``~/.beetsconfig``.  When importing new files, beets will now fetch the 
tempo for files that don't already have them. The bpm field will be stored in 
the beets database. If the ``import_write`` config option is on, then the 
tempo will also be written to the files' tags.

This behavior can be disabled with the ``autofetch`` config option (see below).

Fetching Tempo Manually
------------------------

The ``echonest_tempo`` command provided by this plugin fetches tempos for 
items that match a query (see :doc:`/reference/query`). For example, 
``beet tempo magnetic fields absolutely cuckoo`` will get the tempo for the 
appropriate Magnetic Fields song, ``beet tempo magnetic fields`` will get 
tempos for all my tracks by that band, and ``beet tempo`` will get tempos for 
my entire library. The tempos will be added to the beets database and, if 
``import_write`` is on, embedded into files' metadata.

The ``-p`` option to the ``tempo`` command makes it print tempos out to the
console so you can view the fetched (or previously-stored) tempos.
