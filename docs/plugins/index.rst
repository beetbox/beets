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
list), just use the ``plugins`` option in your :doc:`config.yaml </reference/config>` file, like so::

    plugins: inline convert web

The value for ``plugins`` can be a space-separated list of plugin names or a
YAML list like ``[foo, bar]``. You can see which plugins are currently enabled
by typing ``beet version``.

Each plugin has its own set of options that can be defined in a section bearing its name::

    plugins: inline convert web

    convert:
        auto: true

Some plugins have special dependencies that you'll need to install. The
documentation page for each plugin will list them in the setup instructions.
For some, you can use ``pip``'s "extras" feature to install the dependencies,
like this::

    pip install beets[fetchart,lyrics,lastgenre]

.. _metadata-source-plugin-configuration:

Using Metadata Source Plugins
-----------------------------

Some plugins provide sources for metadata in addition to MusicBrainz. These
plugins share the following configuration option:

- **source_weight**: Penalty applied to matches during import. Set to 0.0 to
  disable.
  Default: ``0.5``.

For example, to equally consider matches from Discogs and MusicBrainz add the
following to your configuration::

    plugins: discogs

    discogs:
       source_weight: 0.0


.. toctree::
   :hidden:

   absubmit
   acousticbrainz
   aura
   badfiles
   bareasc
   beatport
   bpd
   bpm
   bpsync
   bucket
   chroma
   convert
   deezer
   discogs
   duplicates
   edit
   embedart
   embyupdate
   export
   fetchart
   filefilter
   fish
   freedesktop
   fromfilename
   ftintitle
   fuzzy
   gmusic
   hook
   ihate
   importadded
   importfeeds
   info
   inline
   ipfs
   keyfinder
   kodiupdate
   lastgenre
   lastimport
   loadext
   lyrics
   mbcollection
   mbsubmit
   mbsync
   metasync
   missing
   mpdstats
   mpdupdate
   parentwork
   permissions
   play
   playlist
   plexupdate
   random
   replaygain
   rewrite
   scrub
   smartplaylist
   sonosupdate
   spotify
   subsonicplaylist
   subsonicupdate
   the
   thumbnails
   types
   unimported
   web
   zero

Autotagger Extensions
---------------------

* :doc:`chroma`: Use acoustic fingerprinting to identify audio files with
  missing or incorrect metadata.
* :doc:`discogs`: Search for releases in the `Discogs`_ database.
* :doc:`spotify`: Search for releases in the `Spotify`_ database.
* :doc:`deezer`: Search for releases in the `Deezer`_ database.
* :doc:`fromfilename`: Guess metadata for untagged tracks from their
  filenames.

.. _Discogs: https://www.discogs.com/
.. _Spotify: https://www.spotify.com
.. _Deezer: https://www.deezer.com/

Metadata
--------

* :doc:`absubmit`: Analyse audio with the `streaming_extractor_music`_ program and submit the metadata to the AcousticBrainz server
* :doc:`acousticbrainz`: Fetch various AcousticBrainz metadata
* :doc:`bpm`: Measure tempo using keystrokes.
* :doc:`bpsync`: Fetch updated metadata from Beatport.
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
* :doc:`mbsync`: Fetch updated metadata from MusicBrainz.
* :doc:`metasync`: Fetch metadata from local or remote sources
* :doc:`mpdstats`: Connect to `MPD`_ and update the beets library with play
  statistics (last_played, play_count, skip_count, rating).
* :doc:`parentwork`: Fetch work titles and works they are part of. 
* :doc:`replaygain`: Calculate volume normalization for players that support it.
* :doc:`scrub`: Clean extraneous metadata from music files.
* :doc:`zero`: Nullify fields by pattern or unconditionally.

.. _KeyFinder: http://www.ibrahimshaath.co.uk/keyfinder/
.. _streaming_extractor_music: https://acousticbrainz.org/download

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

* :doc:`aura`: A server implementation of the `AURA`_ specification.
* :doc:`badfiles`: Check audio file integrity.
* :doc:`embyupdate`: Automatically notifies `Emby`_ whenever the beets library changes.
* :doc:`fish`: Adds `Fish shell`_ tab autocompletion to ``beet`` commands.
* :doc:`importfeeds`: Keep track of imported files via ``.m3u`` playlist file(s) or symlinks.
* :doc:`ipfs`: Import libraries from friends and get albums from them via ipfs.
* :doc:`kodiupdate`: Automatically notifies `Kodi`_ whenever the beets library
  changes.
* :doc:`mpdupdate`: Automatically notifies `MPD`_ whenever the beets library
  changes.
* :doc:`play`: Play beets queries in your music player.
* :doc:`playlist`: Use M3U playlists to query the beets library.
* :doc:`plexupdate`: Automatically notifies `Plex`_ whenever the beets library
  changes.
* :doc:`smartplaylist`: Generate smart playlists based on beets queries.
* :doc:`sonosupdate`: Automatically notifies `Sonos`_ whenever the beets library
  changes.
* :doc:`thumbnails`: Get thumbnails with the cover art on your album folders.
* :doc:`subsonicupdate`: Automatically notifies `Subsonic`_ whenever the beets
  library changes.


.. _AURA: https://auraspec.readthedocs.io
.. _Emby: https://emby.media
.. _Fish shell: https://fishshell.com/
.. _Plex: https://plex.tv
.. _Kodi: https://kodi.tv
.. _Sonos: https://sonos.com
.. _Subsonic: http://www.subsonic.org/

Miscellaneous
-------------

* :doc:`bareasc`: Search albums and tracks with bare ASCII string matching.
* :doc:`bpd`: A music player for your beets library that emulates `MPD`_ and is
  compatible with `MPD clients`_.
* :doc:`convert`: Transcode music and embed album art while exporting to
  a different directory.
* :doc:`duplicates`: List duplicate tracks or albums.
* :doc:`export`: Export data from queries to a format.
* :doc:`filefilter`: Automatically skip files during the import process based
  on regular expressions.
* :doc:`fuzzy`: Search albums and tracks with fuzzy string matching.
* :doc:`gmusic`: Search and upload files to Google Play Music.
* :doc:`hook`: Run a command when an event is emitted by beets.
* :doc:`ihate`: Automatically skip albums and tracks during the import process.
* :doc:`info`: Print music files' tags to the console.
* :doc:`loadext`: Load SQLite extensions.
* :doc:`mbcollection`: Maintain your MusicBrainz collection list.
* :doc:`mbsubmit`: Print an album's tracks in a MusicBrainz-friendly format.
* :doc:`missing`: List missing tracks.
* `mstream`_: A music streaming server + webapp that can be used alongside beets.
* :doc:`random`: Randomly choose albums and tracks from your library.
* :doc:`spotify`: Create Spotify playlists from the Beets library.
* :doc:`types`: Declare types for flexible attributes.
* :doc:`web`: An experimental Web-based GUI for beets.

.. _MPD: https://www.musicpd.org/
.. _MPD clients: https://mpd.wikia.com/wiki/Clients
.. _mstream: https://github.com/IrosTheBeggar/mStream

.. _other-plugins:

Other Plugins
-------------

In addition to the plugins that come with beets, there are several plugins
that are maintained by the beets community. To use an external plugin, there
are two options for installation:

* Make sure it's in the Python path (known as ``sys.path`` to developers). This
  just means the plugin has to be installed on your system (e.g., with a
  ``setup.py`` script or a command like ``pip`` or ``easy_install``).

* Set the ``pluginpath`` config variable to point to the directory containing the
  plugin. (See :doc:`/reference/config`.)

Once the plugin is installed, enable it by placing its name on the ``plugins``
line in your config file.

Here are a few of the plugins written by the beets community:

* `beetFs`_ is a FUSE filesystem for browsing the music in your beets library.
  (Might be out of date.)

* `A cmus plugin`_ integrates with the `cmus`_ console music player.

* `beets-artistcountry`_ fetches the artist's country of origin from
  MusicBrainz.

* `dsedivec`_ has two plugins: ``edit`` and ``moveall``.

* `beet-amazon`_ adds Amazon.com as a tagger data source.

* `beets-copyartifacts`_ helps bring non-music files along during import.

* `beets-check`_ automatically checksums your files to detect corruption.

* `beets-alternatives`_ manages external files.

* `beets-follow`_ lets you check for new albums from artists you like.

* `beets-ibroadcast`_ uploads tracks to the `iBroadcast`_ cloud service.

* `beets-setlister`_ generate playlists from the setlists of a given artist.

* `beets-noimport`_ adds and removes directories from the incremental import skip list.

* `whatlastgenre`_ fetches genres from various music sites.

* `beets-usertag`_ lets you use keywords to tag and organize your music.

* `beets-popularity`_ fetches popularity values from Spotify.

* `beets-barcode`_ lets you scan or enter barcodes for physical media to
  search for their metadata.

* `beets-ydl`_ downloads audio from youtube-dl sources and import into beets.

* `beet-summarize`_ can compute lots of counts and statistics about your music
  library.

* `beets-mosaic`_ generates a montage of a mosaic from cover art.

* `beets-goingrunning`_ generates playlists to go with your running sessions.

* `beets-xtractor`_ extracts low- and high-level musical information from your songs.

* `beets-yearfixer`_ attempts to fix all missing ``original_year`` and ``year`` fields.

* `beets-autofix`_ automates repetitive tasks to keep your library in order.

* `beets-describe`_ gives you the full picture of a single attribute of your library items.

* `beets-bpmanalyser`_ analyses songs and calculates their tempo (BPM).

* `beets-originquery`_ augments MusicBrainz queries with locally-sourced data
  to improve autotagger results.

* `drop2beets`_ automatically imports singles as soon as they are dropped in a
  folder (using Linux's ``inotify``). You can also set a sub-folders
  hierarchy to set flexible attributes by the way.

.. _beets-barcode: https://github.com/8h2a/beets-barcode
.. _beets-check: https://github.com/geigerzaehler/beets-check
.. _beets-copyartifacts: https://github.com/adammillerio/beets-copyartifacts
.. _dsedivec: https://github.com/dsedivec/beets-plugins
.. _beets-artistcountry: https://github.com/agrausem/beets-artistcountry
.. _beetFs: https://github.com/jbaiter/beetfs
.. _Beet-MusicBrainz-Collection:
    https://github.com/jeffayle/Beet-MusicBrainz-Collection/
.. _A cmus plugin:
    https://github.com/coolkehon/beets/blob/master/beetsplug/cmus.py
.. _cmus: http://cmus.sourceforge.net/
.. _beet-amazon: https://github.com/jmwatte/beet-amazon
.. _beets-alternatives: https://github.com/geigerzaehler/beets-alternatives
.. _beets-follow: https://github.com/nolsto/beets-follow
.. _beets-ibroadcast: https://github.com/ctrueden/beets-ibroadcast
.. _iBroadcast: https://ibroadcast.com/
.. _beets-setlister: https://github.com/tomjaspers/beets-setlister
.. _beets-noimport: https://gitlab.com/tiago.dias/beets-noimport
.. _whatlastgenre: https://github.com/YetAnotherNerd/whatlastgenre/tree/master/plugin/beets
.. _beets-usertag: https://github.com/igordertigor/beets-usertag
.. _beets-popularity: https://github.com/abba23/beets-popularity
.. _beets-ydl: https://github.com/vmassuchetto/beets-ydl
.. _beet-summarize: https://github.com/steven-murray/beet-summarize
.. _beets-mosaic: https://github.com/SusannaMaria/beets-mosaic
.. _beets-goingrunning: https://pypi.org/project/beets-goingrunning
.. _beets-xtractor: https://github.com/adamjakab/BeetsPluginXtractor
.. _beets-yearfixer: https://github.com/adamjakab/BeetsPluginYearFixer
.. _beets-autofix: https://github.com/adamjakab/BeetsPluginAutofix
.. _beets-describe: https://github.com/adamjakab/BeetsPluginDescribe
.. _beets-bpmanalyser: https://github.com/adamjakab/BeetsPluginBpmAnalyser
.. _beets-originquery: https://github.com/x1ppy/beets-originquery
.. _drop2beets: https://github.com/martinkirch/drop2beets
