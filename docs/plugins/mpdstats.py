MPDStats Plugin
================

``mpdstats`` is a plugin for beets that collects statistics about your listening
habits from `MPD`_.  It collects the following information about tracks::

* play_count: The number of times you *fully* listened to this track.
* skip_count: The number of times you *skipped* this track.
* last_played:  UNIX timestamp when you last played this track.
* rating: A rating based on *play_count* and *skip_count*.

.. _MPD: http://mpd.wikia.com/wiki/Music_Player_Daemon_Wiki

To use it, enable it in your ``config.yaml`` by putting ``mpdstats`` on your
``plugins`` line. Then, you'll probably want to configure the specifics of
your MPD server. You can do that using an ``mpd:`` section in your
``config.yaml``, which looks like this::

    mpd:
        host: localhost
        port: 6600
        password: seekrit

If your MPD library is at another location then the beets library e.g. because
one is mounted on a NFS share, you can specify the ```music_directory``` in
the config like this::

    mpdstats:
        music_directory: /PATH/TO/YOUR/FILES

Now use the ``mpdstats`` command to fire it up::

    $ beet mpdstats

This has only been tested with MPD versions >= 0.16.  It may have difficulties
on older versions.  If that is the case, please report an `Issue`_.

.. _Issue:  https://github.com/sampsyo/beets/issues
