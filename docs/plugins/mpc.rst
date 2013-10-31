MPC Plugin
================

``mpc`` is a plugin for beets that collects statistics about your listening
habits from `MPD`_.  It collects the following information about tracks::

* play_count: The number of times you *fully* listened to this track.
* skip_count: The number of times you *skipped* this track.
* last_played:  UNIX timestamp when you last played this track.
* rating: A rating based on *play_count* and *skip_count*.

.. _MPD: http://mpd.wikia.com/wiki/Music_Player_Daemon_Wiki

To use it, enable it in your ``config.yaml`` by putting ``mpc`` on your
``plugins`` line. Then, you'll probably want to configure the specifics of your
MPD server. You can do that using an ``mpc:`` section in your
``config.yaml``, which looks like this::

    mpc:
        host: localhost
        port: 6600
        password: seekrit

Now use the ``mpc`` command to fire it up::

    $ beet mpc
