MPDStats Plugin
================

``mpdstats`` is a plugin for beets that collects statistics about your listening
habits from `MPD`_.  It collects the following information about tracks:

* play_count: The number of times you *fully* listened to this track.
* skip_count: The number of times you *skipped* this track.
* last_played:  UNIX timestamp when you last played this track.
* rating: A rating based on *play_count* and *skip_count*.

.. _MPD: http://mpd.wikia.com/wiki/Music_Player_Daemon_Wiki

Installing Dependencies
-----------------------

This plugin requires the python-mpd library in order to talk to the MPD
server.

Install the library from `pip`_, like so::

    $ pip install python-mpd

Configuring
-----------

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

If you don't want the plugin to automatically update the rating, you can
disable it with::

    mpdstats:
        rating: False

If you want to change the way the rating is calculated, you can set the
```rating_mix``` option like this::

    mpdstats:
        rating_mix: 1.0

For details, see below.


Usage
-----

Now use the ``mpdstats`` command to fire it up::

    $ beet mpdstats

A Word On Ratings
-----------------

Ratings are calculated based on the *play_count*, *skip_count* and the last
*action* (play or skip).  It consists in one part of a *stable_rating* and in
another part on a *rolling_rating*.  The *stable_rating* is calculated like
this::

    stable_rating = (play_count + 1.0) / (play_count + skip_count + 2.0)

So if the *play_count* equals the *skip_count*, the *stable_rating* is always
0.5.  More *play_counts* adjust the rating up to 1.0.  More *skip_counts*
adjust it down to 0.0.  One of the disadvantages of this rating system, is
that it doesn't really cover *recent developments*.  e.g. a song that you
loved last year and played over 50 times will keep a high rating even if you
skipped it the last 10 times.  That's were the *rolling_rating* comes in.

If a song has been fully played, the *rolling_rating* is calculated like
this::

    rolling_rating = old_rating + (1.0 - old_rating) / 2.0

If a song has been skipped, like this::

    rolling_rating = old_rating - old_rating / 2.0

So *rolling_rating* adapts pretty fast to *recent developments*.  But it's too
fast.  Taking the example from above, your old favorite with 50 plays will get
a negative rating (<0.5) the first time you skip it.  Also not good.

To take the best of both worlds, we mix the ratings together with the
``rating_mix`` factor.  A ``rating_mix`` of 0.0 means all
*rolling* and 1.0 means all *stable*.  We found 0.75 to be a good compromise,
but fell free to play with that.

Warning
-------

This has only been tested with MPD versions >= 0.16.  It may not work
on older versions.  If that is the case, please report an `Issue`_.

.. _Issue:  https://github.com/sampsyo/beets/issues
