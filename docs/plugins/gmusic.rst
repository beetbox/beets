Gmusic Plugin
=============

This plugin allows you to manage your Google Play Music library with beets.

Usage
-----

To use the ``gmusic`` plugin, enable it in your configuration file.

Then, add your Google email and password to configuration file under a ``gmusic`` section, if you want to be able to search for songs in your library::

    gmusic:
        email: email
        password: password

It's not necessary if you only upload files.

Now if you want to upload your tracks use ``gmusic-upload`` command::

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