Gmusic Plugin
=============

This plugin allows you to manage your Google Play Music library with beets.


Installation
------------

The plugin requires `gmusic`_. You can install it using `pip`::

    pip install gmusicapi

.. _gmusic: https://github.com/simon-weber/gmusicapi/

Usage
-----

To use the ``gmusic`` plugin, enable it in your configuration file.

Then, add your Google email and password to configuration file under a ``gmusic`` section, if you want to be able to search for songs in your library.
It's not necessary if you only upload files. ::

    gmusic:
        email: email
        password: password


If you want to upload your tracks use ``gmusic-upload`` command::

    beet gmusic-upload [ARGS...]

If no arguments are provided, it will upload your entire beet collection.

In case you want to search for songs in your Google Music library just use::

    beet gmusic-songs [OPTS...] [ARGS...]

    Options:
    -a, --artist        search by artist name
    -t, --track         search by track

For example::

    beet gmusic-songs -a John Frusciante
    beet gmusic-songs -t Black Hole Sun

If you want a list of all songs simply leave it without arguments and options.