Plugins
=======

Plugins can extend beets' core functionality. Plugins can add new commands to
the command-line interface, respond to events in beets, augment the autotagger,
or provide new path template functions.

Using Plugins
-------------

To use a plugin, you have two options:

* Make sure it's in the Python path (known as `sys.path` to developers). This
  just means the plugin has to be installed on your system (e.g., with a
  `setup.py` script or a command like `pip` or `easy_install`).

* Set the `pythonpath` config variable to point to the directory containing the
  plugin. (See :doc:`/reference/cli`.)

Then, set the `plugins` option in your `~/.beetsconfig` file, like so::

    [beets]
    plugins = mygreatplugin someotherplugin

The value for `plugins` should be a space-separated list of plugin module names.

.. _included-plugins:

Plugins Included With Beets
---------------------------

There are a few plugins that are included with the beets distribution. They're
disabled by default, but you can turn them on as described above.

.. toctree::
   :hidden:

   chroma
   lyrics
   bpd
   mpdupdate
   embedart
   web
   lastgenre
   replaygain
   inline
   scrub
   rewrite
   m3uupdate

Autotagger Extensions
''''''''''''''''''''''

* :doc:`chroma`: Use acoustic fingerprinting to identify audio files with
  missing or incorrect metadata.

Metadata
''''''''

* :doc:`lyrics`: Automatically fetch song lyrics.
* :doc:`lastgenre`: Fetch genres based on Last.fm tags.
* :doc:`embedart`: Embed album art images into files' metadata. (By default,
  beets uses image files "on the side" instead of embedding images.)
* :doc:`replaygain`: Calculate volume normalization for players that support it.
* :doc:`scrub`: Clean extraneous metadata from music files.

Path Formats
''''''''''''

* :doc:`inline`: Use Python snippets to customize path format strings.
* :doc:`rewrite`: Substitute values in path formats.

Interoperability
''''''''''''''''

* :doc:`mpdupdate`: Automatically notifies `MPD`_ whenever the beets library
  changes.
* :doc:`m3uupdate`: Catalog imported files in an ``.m3u`` playlist file.

Miscellaneous
'''''''''''''

* :doc:`web`: An experimental Web-based GUI for beets.
* :doc:`rdm`: Randomly choose albums and tracks from your library.
* :doc:`bpd`: A music player for your beets library that emulates `MPD`_ and is
  compatible with `MPD clients`_.

.. _MPD: http://mpd.wikia.com/
.. _MPD clients: http://mpd.wikia.com/wiki/Clients

.. _other-plugins:

Other Plugins
-------------

Here are a few of the plugins written by the beets community:

* `beetFs`_ is a FUSE filesystem for browsing the music in your beets library.
  (Might be out of date.)

* `Beet-MusicBrainz-Collection`_ lets you add albums from your library to your
  MusicBrainz `"music collection"`_.

* `A cmus plugin`_ integrates with the `cmus`_ console music player.

.. _beetFs: http://code.google.com/p/beetfs/
.. _Beet-MusicBrainz-Collection:
    https://github.com/jeffayle/Beet-MusicBrainz-Collection/
.. _"music collection": http://musicbrainz.org/show/collection/
.. _A cmus plugin:
    https://github.com/coolkehon/beets/blob/master/beetsplug/cmus.py
.. _cmus: http://cmus.sourceforge.net/

Writing Plugins
---------------

If you know a little Python, you can write your own plugin to do almost anything
you can imagine with your music collection. See the :doc:`guide to writing beets
plugins </plugins/writing>`.

.. toctree::
    :hidden:
    
    writing
