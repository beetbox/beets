Plugins
=======

Plugins extend beets' core functionality. They add new commands, fetch
additional data during import, provide new metadata sources, and much more. If
beets by itself doesn't do what you want it to, you may just need to enable a
plugin---or, if you want to do something new, :doc:`writing a plugin
</dev/plugins/index>` is easy if you know a little Python.

.. _using-plugins:

Using Plugins
-------------

To use one of the plugins included with beets (see the rest of this page for a
list), just use the ``plugins`` option in your :doc:`config.yaml
</reference/config>` file:

.. code-block:: sh

    plugins: musicbrainz inline convert web

The value for ``plugins`` can be a space-separated list of plugin names or a
YAML list like ``[foo, bar]``. You can see which plugins are currently enabled
by typing ``beet version``.

Each plugin has its own set of options that can be defined in a section bearing
its name:

.. code-block:: yaml

    plugins: musicbrainz inline convert web

    convert:
        auto: true

Some plugins have special dependencies that you'll need to install. The
documentation page for each plugin will list them in the setup instructions. For
some, you can use ``pip``'s "extras" feature to install the dependencies:

.. code-block:: sh

    pip install "beets[fetchart,lyrics,lastgenre]"

.. _metadata-source-plugin-configuration:

Using Metadata Source Plugins
-----------------------------

We provide several :ref:`autotagger_extensions` that fetch metadata from online
databases. They share the following configuration options:

.. include:: ./shared_metadata_source_config.rst

.. toctree::
    :hidden:

    absubmit
    acousticbrainz
    advancedrewrite
    albumtypes
    aura
    autobpm
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
    hook
    ihate
    importadded
    importsource
    importfeeds
    info
    inline
    ipfs
    keyfinder
    kodiupdate
    lastgenre
    lastimport
    limit
    listenbrainz
    loadext
    lyrics
    mbsync
    metasync
    missing
    mpdstats
    mpdupdate
    musicbrainz
    mbcollection
    mbsubmit
    parentwork
    permissions
    play
    playlist
    plexupdate
    random
    replace
    replaygain
    rewrite
    scrub
    smartplaylist
    sonosupdate
    spotify
    subsonicplaylist
    subsonicupdate
    substitute
    the
    thumbnails
    titlecase
    types
    unimported
    web
    zero

.. _autotagger_extensions:

Autotagger Extensions
---------------------

:doc:`chroma <chroma>`
    Use acoustic fingerprinting to identify audio files with missing or
    incorrect metadata.

:doc:`deezer <deezer>`
    Search for releases in the Deezer_ database.

:doc:`discogs <discogs>`
    Search for releases in the Discogs_ database.

:doc:`fromfilename <fromfilename>`
    Guess metadata for untagged tracks from their filenames.

:doc:`musicbrainz <musicbrainz>`
    Search for releases in the MusicBrainz_ database.

:doc:`spotify <spotify>`
    Search for releases in the Spotify_ database.

.. _deezer: https://www.deezer.com

.. _discogs: https://www.discogs.com

.. _musicbrainz: https://www.musicbrainz.com

.. _spotify: https://www.spotify.com

Metadata
--------

:doc:`absubmit <absubmit>`
    Analyse audio with the streaming_extractor_music_ program and submit the
    metadata to an AcousticBrainz server

:doc:`acousticbrainz <acousticbrainz>`
    Fetch various AcousticBrainz metadata

:doc:`autobpm <autobpm>`
    Use Librosa_ to calculate the BPM from the audio.

:doc:`bpm <bpm>`
    Measure tempo using keystrokes.

:doc:`bpsync <bpsync>`
    Fetch updated metadata from Beatport.

:doc:`edit <edit>`
    Edit metadata from a text editor.

:doc:`embedart <embedart>`
    Embed album art images into files' metadata.

:doc:`fetchart <fetchart>`
    Fetch album cover art from various sources.

:doc:`ftintitle <ftintitle>`
    Move "featured" artists from the artist field to the title field.

:doc:`keyfinder <keyfinder>`
    Use the KeyFinder_ program to detect the musical key from the audio.

:doc:`importadded <importadded>`
    Use file modification times for guessing the value for the ``added`` field
    in the database.

:doc:`lastgenre <lastgenre>`
    Fetch genres based on Last.fm tags.

:doc:`lastimport <lastimport>`
    Collect play counts from Last.fm.

:doc:`lyrics <lyrics>`
    Automatically fetch song lyrics.

:doc:`mbsync <mbsync>`
    Fetch updated metadata from MusicBrainz.

:doc:`metasync <metasync>`
    Fetch metadata from local or remote sources

:doc:`mpdstats <mpdstats>`
    Connect to MPD_ and update the beets library with play statistics
    (last_played, play_count, skip_count, rating).

:doc:`parentwork <parentwork>`
    Fetch work titles and works they are part of.

:doc:`replaygain <replaygain>`
    Calculate volume normalization for players that support it.

:doc:`scrub <scrub>`
    Clean extraneous metadata from music files.

:doc:`zero <zero>`
    Nullify fields by pattern or unconditionally.

.. _keyfinder: http://www.ibrahimshaath.co.uk/keyfinder/

.. _librosa: https://github.com/librosa/librosa/

.. _streaming_extractor_music: https://acousticbrainz.org/download

Path Formats
------------

:doc:`albumtypes <albumtypes>`
    Format album type in path formats.

:doc:`bucket <bucket>`
    Group your files into bucket directories that cover different field values
    ranges.

:doc:`inline <inline>`
    Use Python snippets to customize path format strings.

:doc:`rewrite <rewrite>`
    Substitute values in path formats.

:doc:`advancedrewrite <advancedrewrite>`
    Substitute field values for items matching a query.

:doc:`substitute <substitute>`
    As an alternative to :doc:`rewrite <rewrite>`, use this plugin. The main
    difference between them is that this plugin never modifies the files
    metadata.

:doc:`the <the>`
    Move patterns in path formats (i.e., move "a" and "the" to the end).

Interoperability
----------------

:doc:`aura <aura>`
    A server implementation of the AURA_ specification.

:doc:`badfiles <badfiles>`
    Check audio file integrity.

:doc:`embyupdate <embyupdate>`
    Automatically notifies Emby_ whenever the beets library changes.

:doc:`fish <fish>`
    Adds `Fish shell`_ tab autocompletion to ``beet`` commands.

:doc:`importfeeds <importfeeds>`
    Keep track of imported files via ``.m3u`` playlist file(s) or symlinks.

:doc:`ipfs <ipfs>`
    Import libraries from friends and get albums from them via ipfs.

:doc:`kodiupdate <kodiupdate>`
    Automatically notifies Kodi_ whenever the beets library changes.

:doc:`mpdupdate <mpdupdate>`
    Automatically notifies MPD_ whenever the beets library changes.

:doc:`play <play>`
    Play beets queries in your music player.

:doc:`playlist <playlist>`
    Use M3U playlists to query the beets library.

:doc:`plexupdate <plexupdate>`
    Automatically notifies Plex_ whenever the beets library changes.

:doc:`smartplaylist <smartplaylist>`
    Generate smart playlists based on beets queries.

:doc:`sonosupdate <sonosupdate>`
    Automatically notifies Sonos_ whenever the beets library changes.

:doc:`thumbnails <thumbnails>`
    Get thumbnails with the cover art on your album folders.

:doc:`subsonicupdate <subsonicupdate>`
    Automatically notifies Subsonic_ whenever the beets library changes.

.. _aura: https://auraspec.readthedocs.io

.. _emby: https://emby.media

.. _fish shell: https://fishshell.com/

.. _kodi: https://kodi.tv

.. _plex: https://plex.tv

.. _sonos: https://sonos.com

.. _subsonic: http://www.subsonic.org/

Miscellaneous
-------------

:doc:`bareasc <bareasc>`
    Search albums and tracks with bare ASCII string matching.

:doc:`bpd <bpd>`
    A music player for your beets library that emulates MPD_ and is compatible
    with `MPD clients`_.

:doc:`convert <convert>`
    Transcode music and embed album art while exporting to a different
    directory.

:doc:`duplicates <duplicates>`
    List duplicate tracks or albums.

:doc:`export <export>`
    Export data from queries to a format.

:doc:`filefilter <filefilter>`
    Automatically skip files during the import process based on regular
    expressions.

:doc:`fuzzy <fuzzy>`
    Search albums and tracks with fuzzy string matching.

:doc:`hook <hook>`
    Run a command when an event is emitted by beets.

:doc:`ihate <ihate>`
    Automatically skip albums and tracks during the import process.

:doc:`info <info>`
    Print music files' tags to the console.

:doc:`loadext <loadext>`
    Load SQLite extensions.

:doc:`mbcollection <mbcollection>`
    Maintain your MusicBrainz collection list.

:doc:`mbsubmit <mbsubmit>`
    Print an album's tracks in a MusicBrainz-friendly format.

:doc:`missing <missing>`
    List missing tracks.

mstream_
    A music streaming server + webapp that can be used alongside beets.

:doc:`random <random>`
    Randomly choose albums and tracks from your library.

:doc:`spotify <spotify>`
    Create Spotify playlists from the Beets library.

:doc:`types <types>`
    Declare types for flexible attributes.

:doc:`web <web>`
    An experimental Web-based GUI for beets.

.. _mpd: https://www.musicpd.org/

.. _mpd clients: https://mpd.wikia.com/wiki/Clients

.. _mstream: https://github.com/IrosTheBeggar/mStream

.. _other-plugins:

Other Plugins
-------------

In addition to the plugins that come with beets, there are several plugins that
are maintained by the beets community. To use an external plugin, there are two
options for installation:

- Make sure it's in the Python path (known as ``sys.path`` to developers). This
  just means the plugin has to be installed on your system (e.g., with a
  ``setup.py`` script or a command like ``pip`` or ``easy_install``).
- Set the ``pluginpath`` config variable to point to the directory containing
  the plugin. (See :doc:`/reference/config`.)

Once the plugin is installed, enable it by placing its name on the ``plugins``
line in your config file.

Here are a few of the plugins written by the beets community:

beets-alternatives_
    Manages external files.

beet-amazon_
    Adds Amazon.com as a tagger data source.

beets-artistcountry_
    Fetches the artist's country of origin from MusicBrainz.

beets-autofix_
    Automates repetitive tasks to keep your library in order.

beets-autogenre_
    Assigns genres to your library items using the :doc:`lastgenre <lastgenre>`
    and beets-xtractor_ plugins as well as additional rules.

beets-audible_
    Adds Audible as a tagger data source and provides other features for
    managing audiobook collections.

beets-barcode_
    Lets you scan or enter barcodes for physical media to search for their
    metadata.

beetcamp_
    Enables **bandcamp.com** autotagger with a fairly extensive amount of
    metadata.

beetstream_
    Server implementation of the `Subsonic API`_ specification, serving the
    beets library and (:doc:`smartplaylist <smartplaylist>` plugin generated)
    M3U playlists, allowing you to stream your music on a multitude of clients.

beets-bpmanalyser_
    Analyses songs and calculates their tempo (BPM).

beets-check_
    Automatically checksums your files to detect corruption.

`A cmus plugin`_
    Integrates with the cmus_ console music player.

beets-copyartifacts_
    Helps bring non-music files along during import.

beets-describe_
    Gives you the full picture of a single attribute of your library items.

drop2beets_
    Automatically imports singles as soon as they are dropped in a folder (using
    Linux's ``inotify``). You can also set a sub-folders hierarchy to set
    flexible attributes by the way.

dsedivec_
    Has two plugins: ``edit`` and ``moveall``.

beets-filetote_
    Helps bring non-music extra files, attachments, and artifacts during imports
    and CLI file manipulation actions (``beet move``, etc.).

beets-fillmissing_
    Interactively prompts you to fill in missing or incomplete metadata fields
    for music tracks.

beets-follow_
    Lets you check for new albums from artists you like.

beetFs_
    Is a FUSE filesystem for browsing the music in your beets library. (Might be
    out of date.)

beets-goingrunning_
    Generates playlists to go with your running sessions.

beets-ibroadcast_
    Uploads tracks to the iBroadcast_ cloud service.

beets-id3extract_
    Maps arbitrary ID3 tags to beets custom fields.

beets-importreplace_
    Lets you perform regex replacements on incoming metadata.

beets-jiosaavn_
    Adds JioSaavn.com as a tagger data source.

beets-more_
    Finds versions of indexed releases with more tracks, like deluxe and
    anniversary editions.

beets-mosaic_
    Generates a montage of a mosaic from cover art.

beets-mpd-utils_
    Plugins to interface with MPD_. Comes with ``mpd_tracker`` (track play/skip
    counts from MPD) and ``mpd_dj`` (auto-add songs to your queue.)

beets-noimport_
    Adds and removes directories from the incremental import skip list.

beets-originquery_
    Augments MusicBrainz queries with locally-sourced data to improve autotagger
    results.

beets-plexsync_
    Allows you to sync your Plex library with your beets library, create smart
    playlists in Plex, and import online playlists (from services like Spotify)
    into Plex.

beets-setlister_
    Generate playlists from the setlists of a given artist.

beet-summarize_
    Can compute lots of counts and statistics about your music library.

beets-usertag_
    Lets you use keywords to tag and organize your music.

beets-webm3u_
    Serves the (:doc:`smartplaylist <smartplaylist>` plugin generated) M3U
    playlists via HTTP.

beets-webrouter_
    Serves multiple beets webapps (e.g. :doc:`web <web>`, beets-webm3u_,
    beetstream_, :doc:`aura <aura>`) using a single command/process/host/port,
    each under a different path.

whatlastgenre_
    Fetches genres from various music sites.

beets-xtractor_
    Extracts low- and high-level musical information from your songs.

beets-ydl_
    Downloads audio from youtube-dl sources and import into beets.

beets-ytimport_
    Download and import your liked songs from YouTube into beets.

beets-yearfixer_
    Attempts to fix all missing ``original_year`` and ``year`` fields.

beets-youtube_
    Adds YouTube Music as a tagger data source.

.. _a cmus plugin: https://github.com/coolkehon/beets/blob/master/beetsplug/cmus.py

.. _beet-amazon: https://github.com/jmwatte/beet-amazon

.. _beet-musicbrainz-collection: https://github.com/jeffayle/Beet-MusicBrainz-Collection/

.. _beet-summarize: https://github.com/steven-murray/beet-summarize

.. _beetcamp: https://github.com/snejus/beetcamp

.. _beetfs: https://github.com/jbaiter/beetfs

.. _beets-alternatives: https://github.com/geigerzaehler/beets-alternatives

.. _beets-artistcountry: https://github.com/agrausem/beets-artistcountry

.. _beets-audible: https://github.com/Neurrone/beets-audible

.. _beets-autofix: https://github.com/adamjakab/BeetsPluginAutofix

.. _beets-autogenre: https://github.com/mgoltzsche/beets-autogenre

.. _beets-barcode: https://github.com/8h2a/beets-barcode

.. _beets-bpmanalyser: https://github.com/adamjakab/BeetsPluginBpmAnalyser

.. _beets-check: https://github.com/geigerzaehler/beets-check

.. _beets-copyartifacts: https://github.com/adammillerio/beets-copyartifacts

.. _beets-describe: https://github.com/adamjakab/BeetsPluginDescribe

.. _beets-filetote: https://github.com/gtronset/beets-filetote

.. _beets-fillmissing: https://github.com/amiv1/beets-fillmissing

.. _beets-follow: https://github.com/nolsto/beets-follow

.. _beets-goingrunning: https://pypi.org/project/beets-goingrunning

.. _beets-ibroadcast: https://github.com/ctrueden/beets-ibroadcast

.. _beets-id3extract: https://github.com/bcotton/beets-id3extract

.. _beets-importreplace: https://github.com/edgars-supe/beets-importreplace

.. _beets-jiosaavn: https://github.com/arsaboo/beets-jiosaavn

.. _beets-more: https://forgejo.sny.sh/sun/beetsplug/src/branch/main/more

.. _beets-mosaic: https://github.com/SusannaMaria/beets-mosaic

.. _beets-mpd-utils: https://github.com/thekakkun/beets-mpd-utils

.. _beets-noimport: https://gitlab.com/tiago.dias/beets-noimport

.. _beets-originquery: https://github.com/x1ppy/beets-originquery

.. _beets-plexsync: https://github.com/arsaboo/beets-plexsync

.. _beets-setlister: https://github.com/tomjaspers/beets-setlister

.. _beets-usertag: https://github.com/edgars-supe/beets-usertag

.. _beets-webm3u: https://github.com/mgoltzsche/beets-webm3u

.. _beets-webrouter: https://github.com/mgoltzsche/beets-webrouter

.. _beets-xtractor: https://github.com/adamjakab/BeetsPluginXtractor

.. _beets-ydl: https://github.com/vmassuchetto/beets-ydl

.. _beets-yearfixer: https://github.com/adamjakab/BeetsPluginYearFixer

.. _beets-youtube: https://github.com/arsaboo/beets-youtube

.. _beets-ytimport: https://github.com/mgoltzsche/beets-ytimport

.. _beetstream: https://github.com/BinaryBrain/Beetstream

.. _cmus: http://cmus.sourceforge.net/

.. _drop2beets: https://github.com/martinkirch/drop2beets

.. _dsedivec: https://github.com/dsedivec/beets-plugins

.. _ibroadcast: https://ibroadcast.com/

.. _subsonic api: http://www.subsonic.org/pages/api.jsp

.. _whatlastgenre: https://github.com/YetAnotherNerd/whatlastgenre/tree/master/plugin/beets
