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

* Set the `pluginpath` config variable to point to the directory containing the
  plugin. (See :doc:`/reference/cli`.)

Then, set the `plugins` option in your `config.yaml` file, like so::

    plugins: mygreatplugin someotherplugin

The value for `plugins` can be a space-separated list of plugin names or
a YAML list like ``[foo, bar]``.

You can see which plugins are currently enabled by typing ``beet version``.

.. _included-plugins:

Plugins Included With Beets
---------------------------

There are a few plugins that are included with the beets distribution. They're
disabled by default, but you can turn them on as described above.

.. toctree::
   :hidden:

   chroma
   lyrics
   echonest_tempo
   bpd
   mpdupdate
   fetchart
   embedart
   web
   lastgenre
   replaygain
   inline
   scrub
   rewrite
   random
   mbcollection
   importfeeds
   the
   fuzzy
   zero
   ihate
   convert
   info

Autotagger Extensions
''''''''''''''''''''''

* :doc:`chroma`: Use acoustic fingerprinting to identify audio files with
  missing or incorrect metadata.

Metadata
''''''''

* :doc:`lyrics`: Automatically fetch song lyrics.
* :doc:`echonest_tempo`: Automatically fetch song tempos (bpm).
* :doc:`lastgenre`: Fetch genres based on Last.fm tags.
* :doc:`fetchart`: Fetch album cover art from various sources.
* :doc:`embedart`: Embed album art images into files' metadata.
* :doc:`replaygain`: Calculate volume normalization for players that support it.
* :doc:`scrub`: Clean extraneous metadata from music files.
* :doc:`zero`: Nullify fields by pattern or unconditionally.

Path Formats
''''''''''''

* :doc:`inline`: Use Python snippets to customize path format strings.
* :doc:`rewrite`: Substitute values in path formats.
* :doc:`the`: Move patterns in path formats (i.e., move "a" and "the" to the
  end).

Interoperability
''''''''''''''''

* :doc:`mpdupdate`: Automatically notifies `MPD`_ whenever the beets library
  changes.
* :doc:`importfeeds`: Keep track of imported files via ``.m3u`` playlist file(s) or symlinks.

Miscellaneous
'''''''''''''

* :doc:`web`: An experimental Web-based GUI for beets.
* :doc:`random`: Randomly choose albums and tracks from your library.
* :doc:`fuzzy`: Search albums and tracks with fuzzy string matching.
* :doc:`mbcollection`: Maintain your MusicBrainz collection list.
* :doc:`ihate`: Automatically skip albums and tracks during the import process.
* :doc:`bpd`: A music player for your beets library that emulates `MPD`_ and is
  compatible with `MPD clients`_.
* :doc:`convert`: Transcode music and embed album art while exporting to
  a different directory.
* :doc:`info`: Print music files' tags to the console.

.. _MPD: http://mpd.wikia.com/
.. _MPD clients: http://mpd.wikia.com/wiki/Clients

.. _other-plugins:

Other Plugins
-------------

Here are a few of the plugins written by the beets community:

* `beetFs`_ is a FUSE filesystem for browsing the music in your beets library.
  (Might be out of date.)

* `A cmus plugin`_ integrates with the `cmus`_ console music player.

* `featInTitle`_ moves featured artists from the artist tag to the title tag.

.. _beetFs: http://code.google.com/p/beetfs/
.. _Beet-MusicBrainz-Collection:
    https://github.com/jeffayle/Beet-MusicBrainz-Collection/
.. _A cmus plugin:
    https://github.com/coolkehon/beets/blob/master/beetsplug/cmus.py
.. _cmus: http://cmus.sourceforge.net/
.. _featInTitle: https://github.com/Verrus/beets-plugin-featInTitle/

Writing Plugins
---------------

If you know a little Python, you can write your own plugin to do almost anything
you can imagine with your music collection. See the :doc:`guide to writing beets
plugins </plugins/writing>`.

.. toctree::
    :hidden:
    
    writing
