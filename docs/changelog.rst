Changelog
=========

1.0b12 (January 16, 2012)
-------------------------

This release focuses on making beets' path formatting vastly more powerful. It
adds a function syntax for transforming text. Via a new plugin, arbitrary Python
code can also be used to define new path format fields. Each path format
template can now be activated conditionally based on a query. Character set
substitutions are also now configurable.

In addition, beets avoids problematic filename conflicts by appending numbers to
filenames that would otherwise conflict. Three new plugins (``inline``,
``scrub``, and ``rewrite``) are included in this release.

* **Functions in path formats** provide a simple way to write complex file
  naming rules: for example, ``%upper{%left{$artist,1}}`` will insert the
  capitalized first letter of the track's artist. For more details, see
  :doc:`/reference/pathformat`. If you're interested in adding your own template
  functions via a plugin, see :ref:`writing-plugins`.
* Plugins can also now define new path *fields* in addition to functions.
* The new :doc:`/plugins/inline` lets you **use Python expressions to customize
  path formats** by defining new fields in the config file.
* The configuration can **condition path formats based on queries**. That is,
  you can write a path format that is only used if an item matches a given
  query. (This supersedes the earlier functionality that only allowed
  conditioning on album type; if you used this feature in a previous version,
  you will need to replace, for example, ``soundtrack:`` with
  ``albumtype_soundtrack:``.) See :ref:`path-format-config`.
* **Filename substitutions are now configurable** via the ``replace`` config
  value. You can choose which characters you think should be allowed in your
  directory and music file names.  See :doc:`/reference/config`.
* Beets now ensures that files have **unique filenames** by appending a number
  to any filename that would otherwise conflict with an existing file.
* The new :doc:`/plugins/scrub` can remove extraneous metadata either manually
  or automatically.
* The new :doc:`/plugins/rewrite` can canonicalize names for path formats.
* The autotagging heuristics have been tweaked in situations where the
  MusicBrainz database did not contain track lengths. Previously, beets
  penalized matches where this was the case, leading to situations where
  seemingly good matches would have poor similarity. This penalty has been
  removed.
* Fix an incompatibility in BPD with libmpc (the library that powers mpc and
  ncmpc).
* Fix a crash when importing a partial match whose first track was missing.
* The ``lastgenre`` plugin now correctly writes discovered genres to imported
  files (when tag-writing is enabled).
* Add a message when skipping directories during an incremental import.
* The default ignore settings now ignore all files beginning with a dot.
* Date values in path formats (``$year``, ``$month``, and ``$day``) are now
  appropriately zero-padded.
* Removed the ``--path-format`` global flag for ``beet``.
* Removed the ``lastid`` plugin, which was deprecated in the previous version.

1.0b11 (December 12, 2011)
--------------------------

This version of beets focuses on transitioning the autotagger to the new version
of the MusicBrainz database (called NGS). This transition brings with it a
number of long-overdue improvements: most notably, predictable behavior when
tagging multi-disc albums and integration with the new `Acoustid`_ acoustic
fingerprinting technology.

The importer can also now tag *incomplete* albums when you're missing a few
tracks from a given release. Two other new plugins are also included with this
release: one for assigning genres and another for ReplayGain analysis.

* Beets now communicates with MusicBrainz via the new `Next Generation Schema`_
  (NGS) service via `python-musicbrainz-ngs`_. The bindings are included with
  this version of beets, but a future version will make them an external
  dependency.
* The importer now detects **multi-disc albums** and tags them together. Using a
  heuristic based on the names of directories, certain structures are classified
  as multi-disc albums: for example, if a directory contains subdirectories
  labeled "disc 1" and "disc 2", these subdirectories will be coalesced into a
  single album for tagging.
* The new :doc:`/plugins/chroma` uses the `Acoustid`_ **open-source acoustic
  fingerprinting** service. This replaces the old ``lastid`` plugin, which used
  Last.fm fingerprinting and is now deprecated. Fingerprinting with this library
  should be faster and more reliable.
* The importer can now perform **partial matches**. This means that, if you're
  missing a few tracks from an album, beets can still tag the remaining tracks
  as a single album. (Thanks to `Simon Chopin`_.)
* The new :doc:`/plugins/lastgenre` automatically **assigns genres to imported
  albums** and items based on Last.fm tags and an internal whitelist. (Thanks to
  `KraYmer`_.)
* The :doc:`/plugins/replaygain`, written by `Peter Brunner`_, has been merged
  into the core beets distribution. Use it to analyze audio and **adjust
  playback levels** in ReplayGain-aware music players.
* Albums are now tagged with their *original* release date rather than the date
  of any reissue, remaster, "special edition", or the like.
* The config file and library databases are now given better names and locations
  on Windows. Namely, both files now reside in ``%APPDATA%``; the config file is
  named ``beetsconfig.ini`` and the database is called ``beetslibrary.blb``
  (neither has a leading dot as on Unix). For backwards compatibility, beets
  will check the old locations first.
* When entering an ID manually during tagging, beets now searches for anything
  that looks like an MBID in the entered string. This means that full
  MusicBrainz URLs now work as IDs at the prompt. (Thanks to derwin.)
* The importer now ignores certain "clutter" files like ``.AppleDouble``
  directories and ``._*`` files. The list of ignored patterns is configurable
  via the ``ignore`` setting; see :doc:`/reference/config`.
* The database now keeps track of files' modification times so that, during
  an ``update``, unmodified files can be skipped. (Thanks to Jos van der Til.)
* The album art fetcher now uses `albumart.org`_ as a fallback when the Amazon
  art downloader fails.
* A new ``timeout`` config value avoids database locking errors on slow systems.
* Fix a crash after using the "as Tracks" option during import.
* Fix a Unicode error when tagging items with missing titles.
* Fix a crash when the state file (``~/.beetsstate``) became emptied or
  corrupted.

.. _KraYmer: https://github.com/KraYmer
.. _Next Generation Schema: http://musicbrainz.org/doc/XML_Web_Service/Version_2
.. _python-musicbrainz-ngs: https://github.com/alastair/python-musicbrainz-ngs
.. _acoustid: http://acoustid.org/
.. _Peter Brunner: https://github.com/Lugoues
.. _Simon Chopin: https://github.com/laarmen
.. _albumart.org: http://www.albumart.org/

1.0b10 (September 22, 2011)
---------------------------

This version of beets focuses on making it easier to manage your metadata
*after* you've imported it. A bumper crop of new commands has been added: a
manual tag editor (``modify``), a tool to pick up out-of-band deletions and
modifications (``update``), and functionality for moving and copying files
around (``move``). Furthermore, the concept of "re-importing" is new: you can
choose to re-run beets' advanced autotagger on any files you already have in
your library if you change your mind after you finish the initial import.

As a couple of added bonuses, imports can now automatically skip
previously-imported directories (with the ``-i`` flag) and there's an
:doc:`experimental Web interface </plugins/web>` to beets in a new standard
plugin.

* A new ``beet modify`` command enables **manual, command-line-based
  modification** of music metadata. Pass it a query along with ``field=value``
  pairs that specify the changes you want to make.

* A new ``beet update`` command updates the database to reflect **changes in the
  on-disk metadata**. You can now use an external program to edit tags on files,
  remove files and directories, etc., and then run ``beet update`` to make sure
  your beets library is in sync. This will also rename files to reflect their
  new metadata.

* A new ``beet move`` command can **copy or move files** into your library
  directory or to another specified directory.

* When importing files that are already in the library database, the items are
  no longer duplicated---instead, the library is updated to reflect the new
  metadata. This way, the import command can be transparently used as a
  **re-import**.

* Relatedly, the ``-L`` flag to the "import" command makes it take a query as
  its argument instead of a list of directories. The matched albums (or items,
  depending on the ``-s`` flag) are then re-imported.

* A new flag ``-i`` to the import command runs **incremental imports**, keeping
  track of and skipping previously-imported directories. This has the effect of
  making repeated import commands pick up only newly-added directories. The
  ``import_incremental`` config option makes this the default.

* When pruning directories, "clutter" files such as ``.DS_Store`` and
  ``Thumbs.db`` are ignored (and removed with otherwise-empty directories).

* The :doc:`/plugins/web` encapsulates a simple **Web-based GUI for beets**. The
  current iteration can browse the library and play music in browsers that
  support `HTML5 Audio`_.

* When moving items that are part of an album, the album art implicitly moves
  too.

* Files are no longer silently overwritten when moving and copying files.

* Handle exceptions thrown when running Mutagen.

* Fix a missing ``__future__`` import in ``embed art`` on Python 2.5.

* Fix ID3 and MPEG-4 tag names for the album-artist field.

* Fix Unicode encoding of album artist, album type, and label.

* Fix crash when "copying" an art file that's already in place.

.. _HTML5 Audio: http://www.w3.org/TR/html-markup/audio.html

1.0b9 (July 9, 2011)
--------------------

This release focuses on a large number of small fixes and improvements that turn
beets into a well-oiled, music-devouring machine. See the full release notes,
below, for a plethora of new features.

* **Queries can now contain whitespace.** Spaces passed as shell arguments are
  now preserved, so you can use your shell's escaping syntax (quotes or
  backslashes, for instance) to include spaces in queries. For example,
  typing``beet ls "the knife"`` or ``beet ls the\ knife``. Read more in
  :doc:`/reference/query`.

* Queries can **match items from the library by directory**. A ``path:`` prefix
  is optional; any query containing a path separator (/ on POSIX systems) is
  assumed to be a path query. Running ``beet ls path/to/music`` will show all
  the music in your library under the specified directory. The
  :doc:`/reference/query` reference again has more details.

* **Local album art** is now automatically discovered and copied from the
  imported directories when available.

* When choosing the "as-is" import album (or doing a non-autotagged import),
  **every album either has an "album artist" set or is marked as a compilation
  (Various Artists)**. The choice is made based on the homogeneity of the
  tracks' artists. This prevents compilations that are imported as-is from being
  scattered across many directories after they are imported.

* The release **label** for albums and tracks is now fetched from !MusicBrainz,
  written to files, and stored in the database.

* The "list" command now accepts a ``-p`` switch that causes it to **show
  paths** instead of titles. This makes the output of ``beet ls -p`` suitable
  for piping into another command such as `xargs`_.

* Release year and label are now shown in the candidate selection list to help
  disambiguate different releases of the same album.

* Prompts in the importer interface are now colorized for easy reading. The
  default option is always highlighted.

* The importer now provides the option to specify a MusicBrainz ID manually if
  the built-in searching isn't working for a particular album or track.

* ``$bitrate`` in path formats is now formatted as a human-readable kbps value
  instead of as a raw integer.

* The import logger has been improved for "always-on" use. First, it is now
  possible to specify a log file in .beetsconfig. Also, logs are now appended
  rather than overwritten and contain timestamps.

* Album art fetching and plugin events are each now run in separate pipeline
  stages during imports. This should bring additional performance when using
  album art plugins like embedart or beets-lyrics.

* Accents and other Unicode decorators on characters are now treated more fairly
  by the autotagger. For example, if you're missing the acute accent on the "e"
  in "café", that change won't be penalized.  This introduces a new dependency
  on the `unidecode`_ Python module.

* When tagging a track with no title set, the track's filename is now shown
  (instead of nothing at all).

* The bitrate of lossless files is now calculated from their file size (rather
  than being fixed at 0 or reflecting the uncompressed audio bitrate).

* Fixed a problem where duplicate albums or items imported at the same time
  would fail to be detected.

* BPD now uses a persistent "virtual filesystem" in order to fake a directory
  structure. This means that your path format settings are respected in BPD's
  browsing hierarchy. This may come at a performance cost, however. The virtual
  filesystem used by BPD is available for reuse by plugins (e.g., the FUSE
  plugin).

* Singleton imports (``beet import -s``) can now take individual files as
  arguments as well as directories.

* Fix Unicode queries given on the command line.

* Fix crasher in quiet singleton imports (``import -qs``).

* Fix crash when autotagging files with no metadata.

* Fix a rare deadlock when finishing the import pipeline.

* Fix an issue that was causing mpdupdate to run twice for every album.

* Fix a bug that caused release dates/years not to be fetched.

* Fix a crasher when setting MBIDs on MP3s file metadata.

* Fix a "broken pipe" error when piping beets' standard output.

* A better error message is given when the database file is unopenable.

* Suppress errors due to timeouts and bad responses from MusicBrainz.

* Fix a crash on album queries with item-only field names.

.. _xargs: http://en.wikipedia.org/wiki/xargs
.. _unidecode: http://pypi.python.org/pypi/Unidecode/0.04.1

1.0b8 (April 28, 2011)
----------------------

This release of beets brings two significant new features. First, beets now has
first-class support for "singleton" tracks. Previously, it was only really meant
to manage whole albums, but many of us have lots of non-album tracks to keep
track of alongside our collections of albums. So now beets makes it easy to tag,
catalog, and manipulate your individual tracks. Second, beets can now
(optionally) embed album art directly into file metadata rather than only
storing it in a "file on the side." Check out the :doc:`/plugins/embedart` for
that functionality.

* Better support for **singleton (non-album) tracks**. Whereas beets previously
  only really supported full albums, now it can also keep track of individual,
  off-album songs. The "singleton" path format can be used to customize where
  these tracks are stored. To import singleton tracks, provide the -s switch to
  the import command or, while doing a normal full-album import, choose the "as
  Tracks" (T) option to add singletons to your library.  To list only singleton
  or only album tracks, use the new ``singleton:`` query term: the query
  ``singleton:true`` matches only singleton tracks; ``singleton:false`` matches
  only album tracks. The ``lastid`` plugin has been extended to support
  matching individual items as well.

* The importer/autotagger system has been heavily refactored in this release.
  If anything breaks as a result, please get in touch or just file a bug.

* Support for **album art embedded in files**. A new :doc:`/plugins/embedart`
  implements this functionality. Enable the plugin to automatically embed
  downloaded album art into your music files' metadata. The plugin also provides
  the "embedart" and "extractart" commands for moving image files in and out of
  metadata. See the wiki for more details. (Thanks, daenney!)

* The "distance" number, which quantifies how different an album's current and
  proposed metadata are, is now displayed as "similarity" instead. This should
  be less noisy and confusing; you'll now see 99.5% instead of 0.00489323.

* A new "timid mode" in the importer asks the user every time, even when it
  makes a match with very high confidence. The ``-t`` flag on the command line
  and the ``import_timid`` config option control this mode. (Thanks to mdecker
  on GitHub!)

* The multithreaded importer should now abort (either by selecting aBort or by
  typing ^C) much more quickly. Previously, it would try to get a lot of work
  done before quitting; now it gives up as soon as it can.

* Added a new plugin event, ``album_imported``, which is called every time an
  album is added to the library. (Thanks, Lugoues!)

* A new plugin method, ``register_listener``, is an imperative alternative to
  the ``@listen`` decorator (Thanks again, Lugoues!)

* In path formats, ``$albumartist`` now falls back to ``$artist`` (as well as
  the other way around).

* The importer now prints "(unknown album)" when no tags are present.

* When autotagging, "and" is considered equal to "&".

* Fix some crashes when deleting files that don't exist.

* Fix adding individual tracks in BPD.

* Fix crash when ``~/.beetsconfig`` does not exist.


1.0b7 (April 5, 2011)
---------------------

Beta 7's focus is on better support for "various artists" releases. These albums
can be treated differently via the new ``[paths]`` config section and the
autotagger is better at handling them. It also includes a number of
oft-requested improvements to the ``beet`` command-line tool, including several
new configuration options and the ability to clean up empty directory subtrees.

* **"Various artists" releases** are handled much more gracefully. The
  autotagger now sets the ``comp`` flag on albums whenever the album is
  identified as a "various artists" release by !MusicBrainz. Also, there is now
  a distinction between the "album artist" and the "track artist", the latter of
  which is never "Various Artists" or other such bogus stand-in. *(Thanks to
  Jonathan for the bulk of the implementation work on this feature!)*

* The directory hierarchy can now be **customized based on release type**. In
  particular, the ``path_format`` setting in .beetsconfig has been replaced with
  a new ``[paths]`` section, which allows you to specify different path formats
  for normal and "compilation" (various artists) releases as well as for each
  album type (see below). The default path formats have been changed to use
  ``$albumartist`` instead of ``$artist``.

* A **new ``albumtype`` field** reflects the release type `as specified by
  MusicBrainz`_.

* When deleting files, beets now appropriately "prunes" the directory
  tree---empty directories are automatically cleaned up. *(Thanks to
  wlof on GitHub for this!)*

* The tagger's output now always shows the album directory that is currently
  being tagged. This should help in situations where files' current tags are
  missing or useless.

* The logging option (``-l``) to the ``import`` command now logs duplicate
  albums.

* A new ``import_resume`` configuration option can be used to disable the
  importer's resuming feature or force it to resume without asking. This option
  may be either ``yes``, ``no``, or ``ask``, with the obvious meanings. The
  ``-p`` and ``-P`` command-line flags override this setting and correspond to
  the "yes" and "no" settings.

* Resuming is automatically disabled when the importer is in quiet (``-q``)
  mode. Progress is still saved, however, and the ``-p`` flag (above) can be
  used to force resuming.

* The ``BEETSCONFIG`` environment variable can now be used to specify the
  location of the config file that is at ~/.beetsconfig by default.

* A new ``import_quiet_fallback`` config option specifies what should
  happen in quiet mode when there is no strong recommendation. The options are
  ``skip`` (the default) and "asis".

* When importing with the "delete" option and importing files that are already
  at their destination, files could be deleted (leaving zero copies afterward).
  This is fixed.

* The ``version`` command now lists all the loaded plugins.

* A new plugin, called ``info``, just prints out audio file metadata.

* Fix a bug where some files would be erroneously interpreted as MPEG-4 audio.

* Fix permission bits applied to album art files.

* Fix malformed !MusicBrainz queries caused by null characters.

* Fix a bug with old versions of the Monkey's Audio format.

* Fix a crash on broken symbolic links.

* Retry in more cases when !MusicBrainz servers are slow/overloaded.

* The old "albumify" plugin for upgrading databases was removed.

.. _as specified by MusicBrainz: http://wiki.musicbrainz.org/ReleaseType

1.0b6 (January 20, 2011)
------------------------

This version consists primarily of bug fixes and other small improvements. It's
in preparation for a more feature-ful release in beta 7. The most important
issue involves correct ordering of autotagged albums.

* **Quiet import:** a new "-q" command line switch for the import command
  suppresses all prompts for input; it pessimistically skips all albums that the
  importer is not completely confident about.

* Added support for the **WavPack** and **Musepack** formats. Unfortunately, due
  to a limitation in the Mutagen library (used by beets for metadata
  manipulation), Musepack SV8 is not yet supported. Here's the `upstream bug`_
  in question.

* BPD now uses a pure-Python socket library and no longer requires
  eventlet/greenlet (the latter of which is a C extension). For the curious, the
  socket library in question is called `Bluelet`_. 

* Non-autotagged imports are now resumable (just like autotagged imports).

* Fix a terrible and long-standing bug where track orderings were never applied.
  This manifested when the tagger appeared to be applying a reasonable ordering
  to the tracks but, later, the database reflects a completely wrong association
  of track names to files. The order applied was always just alphabetical by
  filename, which is frequently but not always what you want.

* We now use Windows' "long filename" support. This API is fairly tricky,
  though, so some instability may still be present---please file a bug if you
  run into pathname weirdness on Windows. Also, filenames on Windows now never
  end in spaces.

* Fix crash in lastid when the artist name is not available.

* Fixed a spurious crash when ``LANG`` or a related environment variable is set
  to an invalid value (such as ``'UTF-8'`` on some installations of Mac OS X).

* Fixed an error when trying to copy a file that is already at its destination.

* When copying read-only files, the importer now tries to make the copy
  writable. (Previously, this would just crash the import.)

* Fixed an ``UnboundLocalError`` when no matches are found during autotag.

* Fixed a Unicode encoding error when entering special characters into the
  "manual search" prompt.

* Added `` beet version`` command that just shows the current release version.

.. _upstream bug: http://code.google.com/p/mutagen/issues/detail?id=7
.. _Bluelet: https://github.com/sampsyo/bluelet

1.0b5 (September 28, 2010)
--------------------------

This version of beets focuses on increasing the accuracy of the autotagger. The
main addition is an included plugin that uses acoustic fingerprinting to match
based on the audio content (rather than existing metadata). Additional
heuristics were also added to the metadata-based tagger as well that should make
it more reliable. This release also greatly expands the capabilities of beets'
:doc:`plugin API </plugins/index>`. A host of other little features and fixes
are also rolled into this release.

* The ``lastid`` plugin adds Last.fm **acoustic fingerprinting
  support** to the autotagger. Similar to the PUIDs used by !MusicBrainz Picard,
  this system allows beets to recognize files that don't have any metadata at
  all. You'll need to install some dependencies for this plugin to work.

* To support the above, there's also a new system for **extending the autotagger
  via plugins**. Plugins can currently add components to the track and album
  distance functions as well as augment the MusicBrainz search. The new API is
  documented at :doc:`/plugins/index`.

* **String comparisons** in the autotagger have been augmented to act more
  intuitively. Previously, if your album had the title "Something (EP)" and it
  was officially called "Something", then beets would think this was a fairly
  significant change. It now checks for and appropriately reweights certain
  parts of each string. As another example, the title "The Great Album" is
  considered equal to "Great Album, The".

* New **event system for plugins** (thanks, Jeff!). Plugins can now get
  callbacks from beets when certain events occur in the core. Again, the API is
  documented in :doc:`/plugins/index`.

* The BPD plugin is now disabled by default. This greatly simplifies
  installation of the beets core, which is now 100% pure Python. To use BPD,
  though, you'll need to set ``plugins: bpd`` in your .beetsconfig.

* The ``import`` command can now remove original files when it copies items into
  your library. (This might be useful if you're low on disk space.) Set the
  ``import_delete`` option in your .beetsconfig to ``yes``.

* Importing without autotagging (``beet import -A``) now prints out album names
  as it imports them to indicate progress.

* The new :doc:`/plugins/mpdupdate` will automatically update your MPD server's
  index whenever your beets library changes.

* Efficiency tweak should reduce the number of !MusicBrainz queries per
  autotagged album.

* A new ``-v`` command line switch enables debugging output.

* Fixed bug that completely broke non-autotagged imports (``import -A``).

* Fixed bug that logged the wrong paths when using ``import -l``.

* Fixed autotagging for the creatively-named band `!!!`_.

* Fixed normalization of relative paths.

* Fixed escaping of ``/`` characters in paths on Windows.

.. _!!!: http://musicbrainz.org/artist/f26c72d3-e52c-467b-b651-679c73d8e1a7.html

1.0b4 (August 9, 2010)
----------------------

This thrilling new release of beets focuses on making the tagger more usable in
a variety of ways. First and foremost, it should now be much faster: the tagger
now uses a multithreaded algorithm by default (although, because the new tagger
is experimental, a single-threaded version is still available via a config
option). Second, the tagger output now uses a little bit of ANSI terminal
coloring to make changes stand out. This way, it should be faster to decide what
to do with a proposed match: the more red you see, the worse the match is.
Finally, the tagger can be safely interrupted (paused) and restarted later at
the same point. Just enter ``b`` for aBort at any prompt to stop the tagging
process and save its progress. (The progress-saving also works in the
unthinkable event that beets crashes while tagging.)

Among the under-the-hood changes in 1.0b4 is a major change to the way beets
handles paths (filenames). This should make the whole system more tolerant to
special characters in filenames, but it may break things (especially databases
created with older versions of beets). As always, let me know if you run into
weird problems with this release.

Finally, this release's ``setup.py`` should install a ``beet.exe`` startup stub
for Windows users. This should make running beets much easier: just type
``beet`` if you have your ``PATH`` environment variable set up correctly. The
:doc:`/guides/main` guide has some tips on installing beets on Windows.

Here's the detailed list of changes:

* **Parallel tagger.** The autotagger has been reimplemented to use multiple
  threads. This means that it can concurrently read files from disk, talk to the
  user, communicate with MusicBrainz, and write data back to disk. Not only does
  this make the tagger much faster because independent work may be performed in
  parallel, but it makes the tagging process much more pleasant for large
  imports. The user can let albums queue up in the background while making a
  decision rather than waiting for beets between each question it asks.  The
  parallel tagger is on by default but a sequential (single- threaded) version
  is still available by setting the ``threaded`` config value to ``no`` (because
  the parallel version is still quite experimental).

* **Colorized tagger output.** The autotagger interface now makes it a little
  easier to see what's going on at a glance by highlighting changes with
  terminal colors. This feature is on by default, but you can turn it off by
  setting ``color`` to ``no`` in your ``.beetsconfig`` (if, for example, your
  terminal doesn't understand colors and garbles the output).

* **Pause and resume imports.** The ``import`` command now keeps track of its
  progress, so if you're interrupted (beets crashes, you abort the process, an
  alien devours your motherboard, etc.), beets will try to resume from the point
  where you left off. The next time you run ``import`` on the same directory, it
  will ask if you want to resume. It accomplishes this by "fast-forwarding"
  through the albums in the directory until it encounters the last one it saw.
  (This means it might fail if that album can't be found.) Also, you can now
  abort the tagging process by entering ``b`` (for aBort) at any of the prompts.

* Overhauled methods for handling fileystem paths to allow filenames that have
  badly encoded special characters. These changes are pretty fragile, so please
  report any bugs involving ``UnicodeError`` or SQLite ``ProgrammingError``
  messages in this version.

* The destination paths (the library directory structure) now respect
  album-level metadata. This means that if you have an album in which two tracks
  have different album-level attributes (like year, for instance), they will
  still wind up in the same directory together.  (There's currently not a very
  smart method for picking the "correct" album-level metadata, but we'll fix
  that later.)

* Fixed a bug where the CLI would fail completely if the ``LANG`` environment
  variable was not set.

* Fixed removal of albums (``beet remove -a``): previously, the album record
  would stay around although the items were deleted.

* The setup script now makes a ``beet.exe`` startup stub on Windows; Windows
  users can now just type ``beet`` at the prompt to run beets.

* Fixed an occasional bug where Mutagen would complain that a tag was already
  present.

* Fixed a bug with reading invalid integers from ID3 tags.

* The tagger should now be a little more reluctant to reorder tracks that
  already have indices.

1.0b3 (July 22, 2010)
---------------------

This release features two major additions to the autotagger's functionality:
album art fetching and MusicBrainz ID tags. It also contains some important
under-the-hood improvements: a new plugin architecture is introduced
and the database schema is extended with explicit support for albums.

This release has one major backwards-incompatibility. Because of the new way
beets handles albums in the library, databases created with an old version of
beets might have trouble with operations that deal with albums (like the ``-a``
switch to ``beet list`` and ``beet remove``, as well as the file browser for
BPD). To "upgrade" an old database, you can use the included ``albumify`` plugin
(see the fourth bullet point below).

* **Album art.** The tagger now, by default, downloads album art from Amazon
  that is referenced in the MusicBrainz database. It places the album art
  alongside the audio files in a file called (for example) ``cover.jpg``. The
  ``import_art`` config option controls this behavior, as do the ``-r`` and
  ``-R`` options to the import command. You can set the name (minus extension)
  of the album art file with the ``art_filename`` config option. (See
  :doc:`/reference/config` for more information about how to configure the album
  art downloader.)

* **Support for MusicBrainz ID tags.** The autotagger now keeps track of the
  MusicBrainz track, album, and artist IDs it matched for each file. It also
  looks for album IDs in new files it's importing and uses those to look up data
  in MusicBrainz. Furthermore, track IDs are used as a component of the tagger's
  distance metric now. (This obviously lays the groundwork for a utility that
  can update tags if the MB database changes, but that's `for the future`_.)
  Tangentially, this change required the database code to support a lightweight
  form of migrations so that new columns could be added to old databases--this
  is a delicate feature, so it would be very wise to make a backup of your
  database before upgrading to this version.

* **Plugin architecture.** Add-on modules can now add new commands to the beets
  command-line interface. The ``bpd`` and ``dadd`` commands were removed from
  the beets core and turned into plugins; BPD is loaded by default. To load the
  non-default plugins, use the config options ``plugins`` (a space-separated
  list of plugin names) and ``pluginpath`` (a colon-separated list of
  directories to search beyond ``sys.path``). Plugins are just Python modules
  under the ``beetsplug`` namespace package containing subclasses of
  ``beets.plugins.BeetsPlugin``. See `the beetsplug directory`_ for examples or
  :doc:`/plugins/index` for instructions.

* As a consequence of adding album art, the database was significantly
  refactored to keep track of some information at an album (rather than item)
  granularity. Databases created with earlier versions of beets should work
  fine, but they won't have any "albums" in them--they'll just be a bag of
  items. This means that commands like ``beet ls -a`` and ``beet rm -a`` won't
  match anything. To "upgrade" your database, you can use the included
  ``albumify`` plugin. Running ``beets albumify`` with the plugin activated (set
  ``plugins=albumify`` in your config file) will group all your items into
  albums, making beets behave more or less as it did before.

* Fixed some bugs with encoding paths on Windows. Also, ``:`` is now replaced
  with ``-`` in path names (instead of ``_``) for readability.

* ``MediaFile``s now have a ``format`` attribute, so you can use ``$format`` in
  your library path format strings like ``$artist - $album ($format)`` to get
  directories with names like ``Paul Simon - Graceland (FLAC)``.

.. _for the future: http://code.google.com/p/beets/issues/detail?id=69
.. _the beetsplug directory:
    http://code.google.com/p/beets/source/browse/#hg/beetsplug

Beets also now has its first third-party plugin: `beetfs`_, by Martin Eve! It
exposes your music in a FUSE filesystem using a custom directory structure. Even
cooler: it lets you keep your files intact on-disk while correcting their tags
when accessed through FUSE. Check it out!

.. _beetfs: http://code.google.com/p/beetfs/

1.0b2 (July 7, 2010)
--------------------

This release focuses on high-priority fixes and conspicuously missing features.
Highlights include support for two new audio formats (Monkey's Audio and Ogg
Vorbis) and an option to log untaggable albums during import.

* **Support for Ogg Vorbis and Monkey's Audio** files and their tags. (This
  support should be considered preliminary: I haven't tested it heavily because
  I don't use either of these formats regularly.)

* An option to the ``beet import`` command for **logging albums that are
  untaggable** (i.e., are skipped or taken "as-is"). Use ``beet import -l
  LOGFILE PATHS``. The log format is very simple: it's just a status (either
  "skip" or "asis") followed by the path to the album in question. The idea is
  that you can tag a large collection and automatically keep track of the albums
  that weren't found in MusicBrainz so you can come back and look at them later.

* Fixed a ``UnicodeEncodeError`` on terminals that don't (or don't claim to)
  support UTF-8.

* Importing without autotagging (``beet import -A``) is now faster and doesn't
  print out a bunch of whitespace. It also lets you specify single files on the
  command line (rather than just directories).

* Fixed importer crash when attempting to read a corrupt file.

* Reorganized code for CLI in preparation for adding pluggable subcommands. Also
  removed dependency on the aging ``cmdln`` module in favor of `a hand-rolled
  solution`_.

.. _a hand-rolled solution: http://gist.github.com/462717

1.0b1 (June 17, 2010)
---------------------

Initial release.
