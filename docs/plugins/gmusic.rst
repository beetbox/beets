Gmusic Plugin
=============

The ``gmusic`` plugin lets you upload songs to Google Play Music and query
songs in your library.


Installation
------------

The plugin requires `gmusicapi`_. You can install it using `pip`::

    pip install gmusicapi

.. _gmusicapi: https://github.com/simon-weber/gmusicapi/

Then, you can enable the ``gmusic`` plugin in your configuration (see
:ref:`using-plugins`).


Usage
-----

To upload tracks to Google Play Music, use the ``gmusic-upload`` command::

    beet gmusic-upload [QUERY]

If you don't include a query, the plugin will upload your entire collection.

To query the songs in your collection, you will need to add your Google
credentials to your beets configuration file. Put your Google username and
password under a section called ``gmusic``, like so::

    gmusic:
        email: user@example.com
        password: seekrit

If you are using two-factor authentication you need to provide an app password (visit `settings` page to set up).

Then, use the ``gmusic-songs`` command to list music::

    beet gmusic-songs [-at] [ARGS]

.. _settings: https://github.com/beetbox/beets/issues/2660

Use the ``-a`` option to search by artist and ``-t`` to search by track. For
example::

    beet gmusic-songs -a John Frusciante
    beet gmusic-songs -t Black Hole Sun

For a list of all songs in your library, run ``beet gmusic-songs`` without any
arguments.
