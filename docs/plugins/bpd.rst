BPD Plugin
==========

BPD is a music player using music from a beets library. It runs as a daemon and
implements the MPD protocol, so it's compatible with all the great MPD clients
out there. I'm using `Theremin`_, `gmpc`_, `Sonata`_, and `Ario`_ successfully.

.. _Theremin: https://theremin.sigterm.eu/
.. _gmpc: http://gmpc.wikia.com/wiki/Gnome_Music_Player_Client
.. _Sonata: http://sonata.berlios.de/
.. _Ario: http://ario-player.sourceforge.net/

Dependencies
------------

Before you can use BPD, you'll need the media library called GStreamer (along
with its Python bindings) on your system.

* On Mac OS X, you should use `MacPorts`_ and run ``port install
  py26-gst-python``. (Note that you'll almost certainly need the Mac OS X
  Developer Tools.)

* On Linux, it's likely that you already have gst-python. (If not, your
  distribution almost certainly has a package for it.)

* On Windows, you may want to try `GStreamer WinBuilds`_ (cavet emptor: I
  haven't tried this).

.. _MacPorts: http://www.macports.org/
.. _GStreamer WinBuilds: http://www.gstreamer-winbuild.ylatuya.es/

Using and Configuring
---------------------

BPD is a plugin for beets. It comes with beets, but it's disabled by default. To
enable it, you'll need to edit your ``.beetsconfig`` file and add the line
``plugins: bpd``. Like so::

    [beets]
    plugins: bpd

Then, you can run BPD by invoking::

    $ beet bpd

Fire up your favorite MPD client to start playing music. The MPD site has `a
long list of available clients`_. Here are my favorites:

.. _a long list of available clients: http://mpd.wikia.com/wiki/Clients

* Linux: `gmpc`_, `Sonata`_

* Mac: `Theremin`_

* Windows: I don't know. Get in touch if you have a recommendation.

* iPhone/iPod touch: `MPoD`_

.. _MPoD: http://www.katoemba.net/makesnosenseatall/mpod/

One nice thing about MPD's (and thus BPD's) client-server architecture is that
the client can just as easily on a different computer from the server as it can
be run locally. Control your music from your laptop (or phone!) while it plays
on your headless server box. Rad!

To configure the BPD server, add a ``[bpd]`` section to your ``.beetsconfig``
file. The configuration values, which are pretty self-explanatory, are ``host``,
``port``, and ``password``. Here's an example::

    [bpd]
    host: 127.0.0.1
    port: 6600
    password: seekrit

Implementation Notes
--------------------

In the real MPD, the user can browse a music directory as it appears on disk. In
beets, we like to abstract away from the directory structure. Therefore, BPD
creates a "virtual" directory structure (artist/album/track) to present to
clients. This is static for now and cannot be reconfigured like the real on-disk
directory structure can. (Note that an obvious solution to this is just string
matching on items' destination, but this requires examining the entire library
Python-side for every query.)

We don't currently support versioned playlists. Many clients, however, use
plchanges instead of playlistinfo to get the current playlist, so plchanges
contains a dummy implementation that just calls playlistinfo.

The ``stats`` command always send zero for ``playtime``, which is supposed to
indicate the amount of time the server has spent playing music. BPD doesn't
currently keep track of this. Also, because database updates aren't yet
supported, ``db_update`` is just the time the server was started.

Unimplemented Commands
----------------------

These are the commands from `the MPD protocol`_ that have not yet been
implemented in BPD.

.. _the MPD protocol: http://mpd.wikia.com/wiki/MusicPlayerDaemonCommands

Database:

* update

Saved playlists:

* playlistclear
* playlistdelete
* playlistmove
* playlistadd
* playlistsearch
* listplaylist
* listplaylistinfo
* playlistfind
* rm
* save
* load
* rename

Deprecated:

* playlist
* volume
