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
list), just use the `plugins` option in your :doc:`config.yaml </reference/config>` file, like so::

    plugins: inline convert web

The value for `plugins` can be a space-separated list of plugin names or a
YAML list like ``[foo, bar]``. You can see which plugins are currently enabled
by typing ``beet version``.

Each plugin has its own set of options that can be defined in a section bearing its name::

    plugins: inline convert web

    convert:
        auto: true

.. toctree::
   :hidden:

   acousticbrainz
   badfiles
   bpd
   bpm
   bucket
   chroma
   convert
   discogs
   duplicates
   echonest
   edit
   embedart
   embyupdate
   export
   fetchart
   fromfilename
   ftintitle
   fuzzy
   freedesktop
   hook
   ihate
   importadded
   importfeeds
   info
   inline
   ipfs
   keyfinder
   lastgenre
   lastimport
   lyrics
   mbcollection
   mbsubmit
   mbsync
   metasync
   missing
   mpdstats
   mpdupdate
   permissions
   play
   plexupdate
   random
   filefilter
   replaygain
   rewrite
   scrub
   smartplaylist
   spotify
   the
   thumbnails
   types
   web
   zero

Autotagger Extensions
---------------------

* :doc:`chroma`: Use acoustic fingerprinting to identify audio files with
  missing or incorrect metadata.
* :doc:`discogs`: Search for releases in the `Discogs`_ database.
* :doc:`fromfilename`: Guess metadata for untagged tracks from their
  filenames.

.. _Discogs: http://www.discogs.com/

Metadata
--------

* :doc:`acousticbrainz`: Fetch various AcousticBrainz metadata
* :doc:`bpm`: Measure tempo using keystrokes.
* :doc:`echonest`: Automatically fetch `acoustic attributes`_ from
  `the Echo Nest`_ (tempo, energy, danceability, ...).
* :doc:`edit`: Edit metadata from a text editor.
* :doc:`embedart`: Embed album art images into files' metadata.
* :doc:`fetchart`: Fetch album cover art from various sources.
* :doc:`ftintitle`: Move "featured" artists from the artist field to the title
  field.
* :doc:`keyfinder`: Use the `KeyFinder`_ program to detect the musical
  key from the audio.
* :doc:`importadded`: Use file modification times for guessing the value for
  the `added` field in the database.
* :doc:`lastgenre`: Fetch genres based on Last.fm tags.
* :doc:`lastimport`: Collect play counts from Last.fm.
* :doc:`lyrics`: Automatically fetch song lyrics.
* :doc:`mbsync`: Fetch updated metadata from MusicBrainz
* :doc:`metasync`: Fetch metadata from local or remote sources
* :doc:`mpdstats`: Connect to `MPD`_ and update the beets library with play
  statistics (last_played, play_count, skip_count, rating).
* :doc:`replaygain`: Calculate volume normalization for players that support it.
* :doc:`scrub`: Clean extraneous metadata from music files.
* :doc:`zero`: Nullify fields by pattern or unconditionally.

.. _Acoustic Attributes: http://developer.echonest.com/acoustic-attributes.html
.. _the Echo Nest: http://www.echonest.com
.. _KeyFinder: http://www.ibrahimshaath.co.uk/keyfinder/

Path Formats
------------

* :doc:`bucket`: Group your files into bucket directories that cover different
  field values ranges.
* :doc:`inline`: Use Python snippets to customize path format strings.
* :doc:`rewrite`: Substitute values in path formats.
* :doc:`the`: Move patterns in path formats (i.e., move "a" and "the" to the
  end).

Interoperability
----------------

* :doc:`embyupdate`: Automatically notifies `Emby`_ whenever the beets library changes.
* :doc:`importfeeds`: Keep track of imported files via ``.m3u`` playlist file(s) or symlinks.
* :doc:`ipfs`: Import libraries from friends and get albums from them via ipfs.
* :doc:`mpdupdate`: Automatically notifies `MPD`_ whenever the beets library
  changes.
* :doc:`play`: Play beets queries in your music player.
* :doc:`plexupdate`: Automatically notifies `Plex`_ whenever the beets library
  changes.
* :doc:`smartplaylist`: Generate smart playlists based on beets queries.
* :doc:`thumbnails`: Get thumbnails with the cover art on your album folders.
* :doc:`badfiles`: Check audio file integrity.


.. _Emby: http://emby.media
.. _Plex: http://plex.tv

Miscellaneous
-------------

* :doc:`bpd`: A music player for your beets library that emulates `MPD`_ and is
  compatible with `MPD clients`_.
* :doc:`convert`: Transcode music and embed album art while exporting to
  a different directory.
* :doc:`duplicates`: List duplicate tracks or albums.
* :doc:`export`: Export data from queries to a format.
* :doc:`fuzzy`: Search albums and tracks with fuzzy string matching.
* :doc:`hook`: Run a command when an event is emitted by beets.
* :doc:`ihate`: Automatically skip albums and tracks during the import process.
* :doc:`info`: Print music files' tags to the console.
* :doc:`mbcollection`: Maintain your MusicBrainz collection list.
* :doc:`mbsubmit`: Print an album's tracks in a MusicBrainz-friendly format.
* :doc:`missing`: List missing tracks.
* :doc:`random`: Randomly choose albums and tracks from your library.
* :doc:`filefilter`: Automatically skip files during the import process based
  on regular expressions.
* :doc:`spotify`: Create Spotify playlists from the Beets library.
* :doc:`types`: Declare types for flexible attributes.
* :doc:`web`: An experimental Web-based GUI for beets.

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

* `beets-alternatives`_ manages external files.

* `beets-follow`_ lets you check for new albums from artists you like.

* `beets-setlister`_ generate playlists from the setlists of a given artist.

* `beets-noimport`_ adds and removes directories from the incremental import skip list.

* `whatlastgenre`_ fetches genres from various music sites.

* `beets-usertag`_ lets you use keywords to tag and organize your music.

.. _beets-check: https://github.com/geigerzaehler/beets-check
.. _copyartifacts: https://github.com/sbarakat/beets-copyartifacts
.. _dsedivec: https://github.com/dsedivec/beets-plugins
.. _beets-artistcountry: https://github.com/agrausem/beets-artistcountry
.. _beetFs: https://code.google.com/p/beetfs/
.. _Beet-MusicBrainz-Collection:
    https://github.com/jeffayle/Beet-MusicBrainz-Collection/
.. _A cmus plugin:
    https://github.com/coolkehon/beets/blob/master/beetsplug/cmus.py
.. _cmus: http://cmus.sourceforge.net/
.. _beet-amazon: https://github.com/jmwatte/beet-amazon
.. _beets-alternatives: https://github.com/geigerzaehler/beets-alternatives
.. _beets-follow: https://github.com/nolsto/beets-follow
.. _beets-setlister: https://github.com/tomjaspers/beets-setlister
.. _beets-noimport: https://github.com/ttsda/beets-noimport
.. _whatlastgenre: https://github.com/YetAnotherNerd/whatlastgenre/tree/master/plugin/beets
.. _beets-usertag: https://github.com/igordertigor/beets-usertag
