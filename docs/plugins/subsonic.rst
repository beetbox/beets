Subsonic Plugin
===============

The ``subsonic`` plugin emulates a piece of ``subsonic`` server which allows
`subsonic clients`_ to play music from beets.

This plugin requires :doc:`web` and ``subsonic`` plugins enabled in your
configuration (see :ref:`using-plugins`).

.. _subsonic clients: http://www.subsonic.org/pages/apps.jsp

Install
-------

See how to install :ref:`web plugin <web-install>`.

Run the Server
--------------

See how to run :ref:`web plugin <web-run-the-server>` server.

Configuration
-------------

See how to configure :ref:`web plugin <web-configuration>`.

The API
-------

Only a subset of `subsonic API`_ is implemented. This subset is enough to play
your musics.
Current version of the plugin implements `subsonic API`_ version ``1.10.1``,
which should be compatible with the majority of the `subsonic clients`_.

.. _subsonic API: http://www.subsonic.org/pages/api.jsp

Implemented methods
+++++++++++++++++++
==========  =======
Category    Methods
==========  =======
System	    ping getLicense
Browsing    getMusicFolders getIndexes getMusicDirectory getArtists getArtist getAlbum getSong
Album/song  lists getAlbumList getAlbumList2 getRandomSongs
Searching   search2 search3
==========  =======