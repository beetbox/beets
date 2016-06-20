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

* On Mac OS X, you can use `Homebrew`_. Run ``brew install gstreamer`` and then
  ``brew install pygobject3``.

.. _homebrew-versions: https://github.com/Homebrew/homebrew-versions

* On Linux, you need to install GStreamer 1.0 and the GObject bindings for
  python. Under Ubuntu, they are called `python-gi` and `gstreamer1.0`.

* On Windows, you may want to try `GStreamer WinBuilds`_ (caveat emptor: I
  haven't tried this).

You will also need the various GStreamer plugin packages to make everything
work. See the :doc:`/plugins/chroma` documentation for more information on
installing GStreamer plugins.

.. _GStreamer WinBuilds: http://www.gstreamer-winbuild.ylatuya.es/
.. _Homebrew: http://mxcl.github.com/homebrew/

Usage
-----

To use the ``bpd`` plugin, first enable it in your configuration (see
:ref:`using-plugins`).
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

Configuration
-------------

To configure the plugin, make a ``bpd:`` section in your configuration file.
The available options are:

- **host**:
  Default: Bind to all interfaces.
- **port**:
  Default: 6600
- **password**:
  Default: No password.
- **volume**: Initial volume, as a percentage.
  Default: 100

Here's an example::

    bpd:
        host: 127.0.0.1
        port: 6600
        password: seekrit
        volume: 100

Implementation Notes
--------------------

In the real MPD, the user can browse a music directory as it appears on disk.
In beets, we like to abstract away from the directory structure. Therefore, BPD
creates a "virtual" directory structure (artist/album/track) to present to
clients. This is static for now and cannot be reconfigured like the real
on-disk directory structure can. (Note that an obvious solution to this is just
string matching on items' destination, but this requires examining the entire
library Python-side for every query.)

We don't currently support versioned playlists. Many clients, however, use
plchanges instead of playlistinfo to get the current playlist, so plchanges
contains a dummy implementation that just calls playlistinfo.

The ``stats`` command always send zero for ``playtime``, which is supposed to
indicate the amount of time the server has spent playing music. BPD doesn't
currently keep track of this.

The ``update`` command regenerates the directory tree from the beets database.

Unimplemented Commands
----------------------

These are the commands from `the MPD protocol`_ that have not yet been
implemented in BPD.

.. _the MPD protocol: http://www.musicpd.org/doc/protocol/

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
