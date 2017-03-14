KodiUpdate Plugin
=================

The ``kodinfo`` plugin lets you automatically generate .nfo `files`_ used by `KODI`_ 
and other similar media servers like `Plex`_ whenever you import albums and tracks your beets library.

To use the ``kodinfo`` plugin, enable it in your configuration
(see :ref:`using-plugins`).

Once enabled, the plugin will generate the artist.nfo file under the album artist's 
folder, and one album.nfo for each imported album inside its corresponding folder. These 
files will then be loaded by Kodi automatically when it attempts to get metadata for these tracks. 
For singletons, ``kodinfo`` will generate an individual .nfo file with the name of the track for each 
file. 

.. _files: http://kodi.wiki/view/NFO_files/music
.. _KODI: http://kodi.tv/
.. _Plex: https://www.plex.tv
.. _requests: http://docs.python-requests.org/en/latest/

Configuration
-------------

The ``kodi:`` section has no configurable options.


A note on folder structure configuration
----------------------------------------

``kodinfo`` will only work for configurations where the artist path is the direct parent of the album 
paths. 