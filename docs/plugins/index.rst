Plugins
=======

Plugins extend beets' core functionality. They add new commands, fetch
additional data during import, provide new metadata sources, and much more. If
beets by itself doesn't do what you want it to, you may just need to enable a
plugin---or, if you want to do something new, :doc:`writing a plugin
</dev/plugins>` is easy if you know a little Python.

.. _using-plugins:

Using Plugins
-------------

To use one of the plugins included with beets (see the rest of this page for a
list), just use the `plugins` option in your :doc:`config.yaml </reference/config>`: file, like so::

    plugins: inline discogs web

The value for `plugins` can be a space-separated list of plugin names or a
YAML list like ``[foo, bar]``. You can see which plugins are currently enabled
by typing ``beet version``.

.. toctree::
   :hidden:

   chroma
   lyrics
   echonest_tempo
   echonest
   bpd
   mpdupdate
   mpdstats
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
   play
   smartplaylist
   mbsync
   missing
   duplicates
   discogs
   beatport
   fromfilename
   ftintitle
   keyfinder
   bucket
   importadded

Autotagger Extensions
---------------------

* :doc:`chroma`: Use acoustic fingerprinting to identify audio files with
  missing or incorrect metadata.
* :doc:`discogs`: Search for releases in the `Discogs`_ database.
* :doc:`fromfilename`: Guess metadata for untagged tracks from their
  filenames.

.. _Beatport: http://www.beatport.com/
.. _Discogs: http://www.discogs.com/

Metadata
--------

* :doc:`lyrics`: Automatically fetch song lyrics.
* :doc:`echonest`: Automatically fetch `acoustic attributes`_ from
  `the Echo Nest`_ (tempo, energy, danceability, ...).
* :doc:`lastgenre`: Fetch genres based on Last.fm tags.
* :doc:`mbsync`: Fetch updated metadata from MusicBrainz
* :doc:`fetchart`: Fetch album cover art from various sources.
* :doc:`embedart`: Embed album art images into files' metadata.
* :doc:`replaygain`: Calculate volume normalization for players that support it.
* :doc:`scrub`: Clean extraneous metadata from music files.
* :doc:`zero`: Nullify fields by pattern or unconditionally.
* :doc:`ftintitle`: Move "featured" artists from the artist field to the title
  field.
* :doc:`mpdstats`: Connect to `MPD`_ and update the beets library with play
  statistics (last_played, play_count, skip_count, rating).
* :doc:`keyfinder`: Use the `KeyFinder`_ program to detect the musical
  key from the audio.
* :doc:`importadded`: Use file modification times for guessing the value for
  the `added` field in the database.

.. _Acoustic Attributes: http://developer.echonest.com/acoustic-attributes.html
.. _the Echo Nest: http://www.echonest.com
.. _KeyFinder: http://www.ibrahimshaath.co.uk/keyfinder/

Path Formats
------------

* :doc:`inline`: Use Python snippets to customize path format strings.
* :doc:`rewrite`: Substitute values in path formats.
* :doc:`the`: Move patterns in path formats (i.e., move "a" and "the" to the
  end).
* :doc:`bucket`: Group your files into bucket directories that cover different
  field values ranges.

Interoperability
----------------

* :doc:`mpdupdate`: Automatically notifies `MPD`_ whenever the beets library
  changes.
* :doc:`importfeeds`: Keep track of imported files via ``.m3u`` playlist file(s) or symlinks.
* :doc:`smartplaylist`: Generate smart playlists based on beets queries.
* :doc:`play`: Play beets queries in your music player.

Miscellaneous
-------------

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
* :doc:`missing`: List missing tracks.
* :doc:`duplicates`: List duplicate tracks or albums.

.. _MPD: http://www.musicpd.org/
.. _MPD clients: http://mpd.wikia.com/wiki/Clients

.. _other-plugins:

Other Plugins
-------------

In addition to the plugins that come with beets, there are several plugins
that are maintained by the beets community. To use an external plugin, there
are two options for installation:

* Make sure it's in the Python path (known as `sys.path` to developers). This
  just means the plugin has to be installed on your system (e.g., with a
  `setup.py` script or a command like `pip` or `easy_install`).

* Set the `pluginpath` config variable to point to the directory containing the
  plugin. (See :doc:`/reference/config`.)

Once the plugin is installed, enable it by placing its name on the `plugins`
line in your config file.

Here are a few of the plugins written by the beets community:

* `beetFs`_ is a FUSE filesystem for browsing the music in your beets library.
  (Might be out of date.)

* `A cmus plugin`_ integrates with the `cmus`_ console music player.

* `beets-artistcountry`_ fetches the artist's country of origin from
  MusicBrainz.

* `dsedivec`_ has two plugins: ``edit`` and ``moveall``.

* `beet-amazon`_ adds Amazon.com as a tagger data source.

* `copyartifacts`_ helps bring non-music files along during import.

* `beets-check`_ automatically checksums your files to detect corruption.

.. _beets-check: https://github.com/geigerzaehler/beets-check
.. _copyartifacts: https://github.com/sbarakat/beets-copyartifacts
.. _dsedivec: https://github.com/dsedivec/beets-plugins
.. _beets-artistcountry: https://github.com/agrausem/beets-artistcountry
.. _beetFs: http://code.google.com/p/beetfs/
.. _Beet-MusicBrainz-Collection:
    https://github.com/jeffayle/Beet-MusicBrainz-Collection/
.. _A cmus plugin:
    https://github.com/coolkehon/beets/blob/master/beetsplug/cmus.py
.. _cmus: http://cmus.sourceforge.net/
.. _beet-amazon: https://github.com/jmwatte/beet-amazon
