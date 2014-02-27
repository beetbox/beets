Changelog
=========

1.3.4 (February 26, 2014)
-------------------------

Version 1.3.3 brings a bunch changes to how item and album fields work
internally. Along with laying the groundwork for some great things in the
future, this brings a number of improvements to how you interact with beets.
Here's what's new with fields in particular:

* Plugin-provided fields can now be used in queries. For example, if you use
  the :doc:`/plugins/inline` to define a field called ``era``, you can now
  filter your library based on that field by typing something like
  ``beet list era:goldenage``.
* Album-level flexible attributes and plugin-provided attributes can now be
  used in path formats (and other item-level templates).
* :ref:`Date-based queries <datequery>` are now possible. Try getting every
  track you added in February 2014 with ``beet ls added:2014-02`` or in the
  whole decade with ``added:2010..``. Thanks to Stig Inge Lea Bjørnsen.
* The :ref:`modify-cmd` command is now better at parsing and formatting
  fields. You can assign to boolean fields like ``comp``, for example, using
  either the words "true" or "false" or the numerals 1 and 0. Any
  boolean-esque value is normalized to a real boolean. The :ref:`update-cmd`
  and :ref:`write-cmd` commands also got smarter at formatting and colorizing
  changes.

For developers, the short version of the story is that Item and Album objects
provide *uniform access* across fixed, flexible, and computed attributes. You
can write ``item.foo`` to access the ``foo`` field without worrying about
where the data comes from.

Unrelated new stuff:

* The importer has a new interactive option (*G* for "Group albums"),
  command-line flag (``--group-albums``), and config option
  (:ref:`group_albums`) that lets you split apart albums that are mixed
  together in a single directory. Thanks to geigerzaehler.
* A new ``--config`` command-line option lets you specify an additional
  configuration file. This option *combines* config settings with your default
  config file. (As part of this change, the ``BEETSDIR`` environment variable
  no longer combines---it *replaces* your default config file.) Thanks again
  to geigerzaehler.
* :doc:`/plugins/ihate`: The plugin's configuration interface was overhauled.
  Its configuration is now much simpler---it uses beets queries instead of an
  ad-hoc per-field configuration. This is *backwards-incompatible*---if you
  use this plugin, you will need to update your configuration. Thanks to
  BrainDamage.

Other little fixes:

* :doc:`/plugins/echonest`: Tempo (BPM) is now always stored as an integer.
  Thanks to Heinz Wiesinger.
* Fix Python 2.6 compatibility in some logging statements in
  :doc:`/plugins/chroma` and :doc:`/plugins/lastgenre`.
* Prevent some crashes when things go really wrong when writing file metadata
  at the end of the import process.
* New plugin events: ``item_removed`` (thanks to Romuald Conty) and
  ``item_copied`` (thanks to Stig Inge Lea Bjørnsen).
* The ``pluginpath`` config option can now point to the directory containing
  plugin code. (Previously, it awkwardly needed to point at a directory
  containing a ``beetsplug`` directory, which would then contain your code.
  This is preserved as an option for backwards compatibility.) This change
  should also work around a long-standing issue when using ``pluginpath`` when
  beets is installed using pip. Many thanks to geigerzaehler.
* :doc:`/plugins/web`: The ``/item/`` and ``/album/`` API endpoints now
  produce full details about albums and items, not just lists of IDs. Thanks
  to geigerzaehler.
* Fix a potential crash when using image resizing with the
  :doc:`/plugins/fetchart` or :doc:`/plugins/embedart` without ImageMagick
  installed.
* Also, when invoking ``convert`` for image resizing fails, we now log an
  error instead of crashing.
* :doc:`/plugins/fetchart`: The ``beet fetchart`` command can now associate
  local images with albums (unless ``--force`` is provided). Thanks to
  brilnius.
* :doc:`/plugins/fetchart`: Command output is now colorized. Thanks again to
  brilnius.
* The :ref:`modify-cmd` command avoids writing files and committing to the
  database when nothing has changed. Thanks once more to brilnius.
* The importer now uses the album artist field when guessing existing
  metadata for albums (rather than just the track artist field). Thanks to
  geigerzaehler.
* :doc:`/plugins/fromfilename`: Fix a crash when a filename contained only a
  track number (e.g., ``02.mp3``).
* :doc:`/plugins/convert`: Transcoding should now work on Windows.
* :doc:`/plugins/duplicates`: The ``move`` and ``copy`` destination arguments
  are now treated as directories. Thanks to Pedro Silva.
* The :ref:`modify-cmd` command now skips confirmation and prints a message if
  no changes are necessary. Thanks to brilnius.
* :doc:`/plugins/fetchart`: When using the ``remote_priority`` config option,
  local image files are no longer completely ignored.
* :doc:`/plugins/echonest`: Fix an issue causing the plugin to appear twice in
  the output of the ``beet version`` command.
* :doc:`/plugins/lastgenre`: Fix an occasional crash when no tag weight was
  returned by Last.fm.
* :doc:`/plugins/mpdstats`: Restore the ``last_played`` field. Thanks to
  Johann Klähn.
* The :ref:`modify-cmd` command's output now clearly shows when a file has
  been deleted.
* Album art in files with Vorbis Comments is now marked with the "front cover"
  type. Thanks to Jason Lefley.


1.3.2 (December 22, 2013)
-------------------------

This update brings new plugins for fetching acoustic metrics and listening
statistics, many more options for the duplicate detection plugin, and flexible
options for fetching multiple genres.

The "core" of beets gained a new built-in command: :ref:`beet write
<write-cmd>` updates the metadata tags for files, bringing them back
into sync with your database. Thanks to Heinz Wiesinger.

We added some plugins and overhauled some existing ones:

* The new :doc:`/plugins/echonest` plugin can fetch a wide range of `acoustic
  attributes`_ from `The Echo Nest`_, including the "speechiness" and
  "liveness" of each track. The new plugin supersedes an older version
  (``echonest_tempo``) that only fetched the BPM field. Thanks to Pedro Silva
  and Peter Schnebel.

* The :doc:`/plugins/duplicates` got a number of new features, thanks to Pedro
  Silva:

  * The ``keys`` option lets you specify the fields used detect duplicates.
  * You can now use checksumming (via an external command) to find
    duplicates instead of metadata via the ``checksum`` option.
  * The plugin can perform actions on the duplicates it find. The new
    ``copy``, ``move``, ``delete``, ``delete_file``, and ``tag`` options
    perform those actions.

* The new :doc:`/plugins/mpdstats` collects statistics about your
  listening habits from `MPD`_. Thanks to Peter Schnebel and Johann Klähn.

* :doc:`/plugins/lastgenre`: The new ``multiple`` option has been replaced
  with the ``count`` option, which lets you limit the number of genres added
  to your music. (No more thousand-character genre fields!) Also, the
  ``min_weight`` field filters out nonsense tags to make your genres more
  relevant. Thanks to Peter Schnebel and rashley60.

* :doc:`/plugins/lyrics`: A new ``--force`` option optionally re-downloads
  lyrics even when files already have them. Thanks to Bitdemon.

As usual, there are also innumerable little fixes and improvements:

* When writing ID3 tags for ReplayGain normalization, tags are written with
  both upper-case and lower-case TXXX frame descriptions. Previous versions of
  beets used only the upper-case style, which seems to be more standard, but
  some players (namely, Quod Libet and foobar2000) seem to only use lower-case
  names.
* :doc:`/plugins/missing`: Avoid a possible error when an album's
  ``tracktotal`` field is missing.
* :doc:`/plugins/ftintitle`: Fix an error when the sort artist is missing.
* :doc:`/plugins/echonest_tempo`: The plugin should now match songs more
  reliably (i.e., fewer "no tempo found" messages). Thanks to Peter Schnebel.
* :doc:`/plugins/convert`: Fix an "Item has no library" error when using the
  ``auto`` config option.
* :doc:`/plugins/convert`: Fix an issue where files of the wrong format would
  have their transcoding skipped (and files with the right format would be
  needlessly transcoded). Thanks to Jakob Schnitzer.
* Fix an issue that caused the :ref:`id3v23` option to work only occasionally.
* Also fix using :ref:`id3v23` in conjunction with the ``scrub`` and
  ``embedart`` plugins. Thanks to Chris Cogburn.
* :doc:`/plugins/ihate`: Fix an error when importing singletons. Thanks to
  Mathijs de Bruin.
* The :ref:`clutter` option can now be a whitespace-separated list in addition
  to a YAML list.
* Values for the :ref:`replace` option can now be empty (i.e., null is
  equivalent to the empty string).
* :doc:`/plugins/lastgenre`: Fix a conflict between canonicalization and
  multiple genres.
* When a match has a year but not a month or day, the autotagger now "zeros
  out" the month and day fields after applying the year.
* For plugin developers: added an ``optparse`` callback utility function for
  performing actions based on arguments. Thanks to Pedro Silva.
* :doc:`/plugins/scrub`: Fix scrubbing of MPEG-4 files. Thanks to Yevgeny
  Bezman.


.. _Acoustic Attributes: http://developer.echonest.com/acoustic-attributes.html
.. _MPD: http://mpd.wikia.com/wiki/Music_Player_Daemon_Wiki


1.3.1 (October 12, 2013)
------------------------

This release boasts a host of new little features, many of them contributed by
beets' amazing and prolific community. It adds support for `Opus`_ files,
transcoding to any format, and two new plugins: one that guesses metadata for
"blank" files based on their filenames and one that moves featured artists
into the title field.

Here's the new stuff:

* Add `Opus`_ audio support. Thanks to Rowan Lewis.
* :doc:`/plugins/convert`: You can now transcode files to any audio format,
  rather than just MP3. Thanks again to Rowan Lewis.
* The new :doc:`/plugins/fromfilename` guesses tags from the filenames during
  import when metadata tags themselves are missing. Thanks to Jan-Erik Dahlin.
* The :doc:`/plugins/ftintitle`, by `@Verrus`_, is now distributed with beets.
  It helps you rewrite tags to move "featured" artists from the artist field
  to the title field.
* The MusicBrainz data source now uses track artists over recording
  artists. This leads to better metadata when tagging classical music. Thanks
  to Henrique Ferreiro.
* :doc:`/plugins/lastgenre`: You can now get multiple genres per album or
  track using the ``multiple`` config option. Thanks to rashley60 on GitHub.
* A new :ref:`id3v23` config option makes beets write MP3 files' tags using
  the older ID3v2.3 metadata standard. Use this if you want your tags to be
  visible to Windows and some older players.

And some fixes:

* :doc:`/plugins/fetchart`: Better error message when the image file has an
  unrecognized type.
* :doc:`/plugins/mbcollection`: Detect, log, and skip invalid MusicBrainz IDs
  (instead of failing with an API error).
* :doc:`/plugins/info`: Fail gracefully when used erroneously with a
  directory.
* :doc:`/plugins/echonest_tempo`: Fix an issue where the plugin could use the
  tempo from the wrong song when the API did not contain the requested song.
* Fix a crash when a file's metadata included a very large number (one wider
  than 64 bits). These huge numbers are now replaced with zeroes in the
  database.
* When a track on a MusicBrainz release has a different length from the
  underlying recording's length, the track length is now used instead.
* With :ref:`per_disc_numbering` enabled, the ``tracktotal`` field is now set
  correctly (i.e., to the number of tracks on the disc).
* :doc:`/plugins/scrub`: The ``scrub`` command now restores album art in
  addition to other (database-backed) tags.
* :doc:`/plugins/mpdupdate`: Domain sockets can now begin with a tilde (which
  is correctly expanded to ``$HOME``) as well as a slash. Thanks to Johann
  Klähn.
* :doc:`/plugins/lastgenre`: Fix a regression that could cause new genres
  found during import not to be persisted.
* Fixed a crash when imported album art was also marked as "clutter" where the
  art would be deleted before it could be moved into place. This led to a
  "image.jpg not found during copy" error. Now clutter is removed (and
  directories pruned) much later in the process, after the
  ``import_task_files`` hook.
* :doc:`/plugins/missing`: Fix an error when printing missing track names.
  Thanks to Pedro Silva.
* Fix an occasional KeyError in the :ref:`update-cmd` command introduced in
  1.3.0.
* :doc:`/plugins/scrub`: Avoid preserving certain non-standard ID3 tags such
  as NCON.

.. _Opus: http://www.opus-codec.org/
.. _@Verrus: https://github.com/Verrus


1.3.0 (September 11, 2013)
--------------------------

Albums and items now have **flexible attributes**. This means that, when you
want to store information about your music in the beets database, you're no
longer constrained to the set of fields it supports out of the box (title,
artist, track, etc.). Instead, you can use any field name you can think of and
treat it just like the built-in fields.

For example, you can use the :ref:`modify-cmd` command to set a new field on a
track::

    $ beet modify mood=sexy artist:miguel

and then query your music based on that field::

    $ beet ls mood:sunny

or use templates to see the value of the field::

    $ beet ls -f '$title: $mood'

While this feature is nifty when used directly with the usual command-line
suspects, it's especially useful for plugin authors and for future beets
features. Stay tuned for great things built on this flexible attribute
infrastructure.

One side effect of this change: queries that include unknown fields will now
match *nothing* instead of *everything*. So if you type ``beet ls
fieldThatDoesNotExist:foo``, beets will now return no results, whereas
previous versions would spit out a warning and then list your entire library.

There's more detail than you could ever need `on the beets blog`_.

.. _on the beets blog: http://beets.radbox.org/blog/flexattr.html


1.2.2 (August 27, 2013)
-----------------------

This is a bugfix release. We're in the midst of preparing for a large change
in beets 1.3, so 1.2.2 resolves some issues that came up over the last few
weeks. Stay tuned!

The improvements in this release are:

* A new plugin event, ``item_moved``, is sent when files are moved on disk.
  Thanks to dsedivec.
* :doc:`/plugins/lyrics`: More improvements to the Google backend by Fabrice
  Laporte.
* :doc:`/plugins/bpd`: Fix for a crash when searching, thanks to Simon Chopin.
* Regular expression queries (and other query types) over paths now work.
  (Previously, special query types were ignored for the ``path`` field.)
* :doc:`/plugins/fetchart`: Look for images in the Cover Art Archive for
  the release group in addition to the specific release. Thanks to Filipe
  Fortes.
* Fix a race in the importer that could cause files to be deleted before they
  were imported. This happened when importing one album, importing a duplicate
  album, and then asking for the first album to be replaced with the second.
  The situation could only arise when importing music from the library
  directory and when the two albums are imported close in time.


1.2.1 (June 22, 2013)
---------------------

This release introduces a major internal change in the way that similarity
scores are handled. It means that the importer interface can now show you
exactly why a match is assigned its score and that the autotagger gained a few
new options that let you customize how matches are prioritized and
recommended.

The refactoring work is due to the continued efforts of Tai Lee. The
changes you'll notice while using the autotagger are:

* The top 3 distance penalties are now displayed on the release listing,
  and all album and track penalties are now displayed on the track changes
  list. This should make it clear exactly which metadata is contributing to a
  low similarity score.
* When displaying differences, the colorization has been made more consistent
  and helpful: red for an actual difference, yellow to indicate that a
  distance penalty is being applied, and light gray for no penalty (e.g., case
  changes) or disambiguation data.

There are also three new (or overhauled) configuration options that let you
customize the way that matches are selected:

* The :ref:`ignored` setting lets you instruct the importer not to show you
  matches that have a certain penalty applied.
* The :ref:`preferred` collection of settings specifies a sorted list of
  preferred countries and media types, or prioritizes releases closest to the
  original year for an album.
* The :ref:`max_rec` settings can now be used for any distance penalty
  component. The recommendation will be downgraded if a non-zero penalty is
  being applied to the specified field.

And some little enhancements and bug fixes:

* Multi-disc directory names can now contain "disk" (in addition to "disc").
  Thanks to John Hawthorn.
* :doc:`/plugins/web`: Item and album counts are now exposed through the API
  for use with the Tomahawk resolver. Thanks to Uwe L. Korn.
* Python 2.6 compatibility for :doc:`/plugins/beatport`,
  :doc:`/plugins/missing`, and :doc:`/plugins/duplicates`. Thanks to Wesley
  Bitter and Pedro Silva.
* Don't move the config file during a null migration. Thanks to Theofilos
  Intzoglou.
* Fix an occasional crash in the :doc:`/plugins/beatport` when a length
  field was missing from the API response. Thanks to Timothy Appnel.
* :doc:`/plugins/scrub`: Handle and log I/O errors.
* :doc:`/plugins/lyrics`: The Google backend should now turn up more results.
  Thanks to Fabrice Laporte.
* :doc:`/plugins/random`: Fix compatibility with Python 2.6. Thanks to
  Matthias Drochner.


1.2.0 (June 5, 2013)
--------------------

There's a *lot* of new stuff in this release: new data sources for the
autotagger, new plugins to look for problems in your library, tracking the
date that you acquired new music, an awesome new syntax for doing queries over
numeric fields, support for ALAC files, and major enhancements to the
importer's UI and distance calculations. A special thanks goes out to all the
contributors who helped make this release awesome.

For the first time, beets can now tag your music using additional **data
sources** to augment the matches from MusicBrainz. When you enable either of
these plugins, the importer will start showing you new kinds of matches:

* New :doc:`/plugins/discogs`: Get matches from the `Discogs`_ database.
  Thanks to Artem Ponomarenko and Tai Lee.
* New :doc:`/plugins/beatport`: Get matches from the `Beatport`_ database.
  Thanks to Johannes Baiter.

We also have two other new plugins that can scan your library to check for
common problems, both by Pedro Silva:

* New :doc:`/plugins/duplicates`: Find tracks or albums in your
  library that are **duplicated**.
* New :doc:`/plugins/missing`: Find albums in your library that are **missing
  tracks**.

There are also three more big features added to beets core:

* Your library now keeps track of **when music was added** to it. The new
  ``added`` field is a timestamp reflecting when each item and album was
  imported and the new ``%time{}`` template function lets you format this
  timestamp for humans. Thanks to Lucas Duailibe.
* When using queries to match on quantitative fields, you can now use
  **numeric ranges**. For example, you can get a list of albums from the '90s
  by typing ``beet ls year:1990..1999`` or find high-bitrate music with
  ``bitrate:128000..``. See :ref:`numericquery`. Thanks to Michael Schuerig.
* **ALAC files** are now marked as ALAC instead of being conflated with AAC
  audio. Thanks to Simon Luijk.

In addition, the importer saw various UI enhancements, thanks to Tai Lee:

* More consistent format and colorization of album and track metadata.
* Display data source URL for matches from the new data source plugins. This
  should make it easier to migrate data from Discogs or Beatport into
  MusicBrainz.
* Display album disambiguation and disc titles in the track listing, when
  available.
* Track changes are highlighted in yellow when they indicate a change in
  format to or from the style of :ref:`per_disc_numbering`. (As before, no
  penalty is applied because the track number is still "correct", just in a
  different format.)
* Sort missing and unmatched tracks by index and title and group them
  together for better readability.
* Indicate MusicBrainz ID mismatches.

The calculation of the similarity score for autotagger matches was also
improved, again thanks to Tai Lee. These changes, in general, help deal with
the new metadata sources and help disambiguate between similar releases in the
same MusicBrainz release group:

* Strongly prefer releases with a matching MusicBrainz album ID. This helps
  beets re-identify the same release when re-importing existing files.
* Prefer releases that are closest to the tagged ``year``. Tolerate files
  tagged with release or original year.
* The new ``preferred_media`` config option lets you prefer a certain media
  type when the ``media`` field is unset on an album.
* Apply minor penalties across a range of fields to differentiate between
  nearly identical releases: ``disctotal``, ``label``, ``catalognum``,
  ``country`` and ``albumdisambig``.

As usual, there were also lots of other great littler enhancements:

* :doc:`/plugins/random`: A new ``-e`` option gives an equal chance to each
  artist in your collection to avoid biasing random samples to prolific
  artists. Thanks to Georges Dubus.
* The :ref:`modify-cmd` now correctly converts types when modifying non-string
  fields. You can now safely modify the "comp" flag and the "year" field, for
  example. Thanks to Lucas Duailibe.
* :doc:`/plugins/convert`: You can now configure the path formats for
  converted files separately from your main library. Thanks again to Lucas
  Duailibe.
* The importer output now shows the number of audio files in each album.
  Thanks to jayme on GitHub.
* Plugins can now provide fields for both Album and Item templates, thanks
  to Pedro Silva. Accordingly, the :doc:`/plugins/inline` can also now define
  album fields. For consistency, the ``pathfields`` configuration section has
  been renamed ``item_fields`` (although the old name will still work for
  compatibility).
* Plugins can also provide metadata matches for ID searches. For example, the
  new Discogs plugin lets you search for an album by its Discogs ID from the
  same prompt that previously just accepted MusicBrainz IDs. Thanks to
  Johannes Baiter.
* The :ref:`fields-cmd` command shows template fields provided by plugins.
  Thanks again to Pedro Silva.
* :doc:`/plugins/mpdupdate`: You can now communicate with MPD over a Unix
  domain socket. Thanks to John Hawthorn.

And a batch of fixes:

* Album art filenames now respect the :ref:`replace` configuration.
* Friendly error messages are now printed when trying to read or write files
  that go missing.
* The :ref:`modify-cmd` command can now change albums' album art paths (i.e.,
  ``beet modify artpath=...`` works). Thanks to Lucas Duailibe.
* :doc:`/plugins/zero`: Fix a crash when nulling out a field that contains
  None.
* Templates can now refer to non-tag item fields (e.g., ``$id`` and
  ``$album_id``).
* :doc:`/plugins/lyrics`: Lyrics searches should now turn up more results due
  to some fixes in dealing with special characters.

.. _Discogs: http://discogs.com/
.. _Beatport: http://www.beatport.com/


1.1.0 (April 29, 2013)
----------------------

This final release of 1.1 brings a little polish to the betas that introduced
the new configuration system. The album art and lyrics plugins also got a
little love.

If you're upgrading from 1.0.0 or earlier, this release (like the 1.1 betas)
will automatically migrate your configuration to the new system. See
:doc:`/guides/migration`.

* :doc:`/plugins/embedart`: The ``embedart`` command now embeds each album's
  associated art by default. The ``--file`` option invokes the old behavior,
  in which a specific image file is used.
* :doc:`/plugins/lyrics`: A new (optional) Google Custom Search backend was
  added for finding lyrics on a wide array of sites. Thanks to Fabrice
  Laporte.
* When automatically detecting the filesystem's maximum filename length, never
  guess more than 200 characters. This prevents errors on systems where the
  maximum length was misreported. You can, of course, override this default
  with the :ref:`max_filename_length` option.
* :doc:`/plugins/fetchart`: Two new configuration options were added:
  ``cover_names``, the list of keywords used to identify preferred images, and
  ``cautious``, which lets you avoid falling back to images that don't contain
  those keywords. Thanks to Fabrice Laporte.
* Avoid some error cases in the ``update`` command and the ``embedart`` and
  ``mbsync`` plugins. Invalid or missing files now cause error logs instead of
  crashing beets. Thanks to Lucas Duailibe.
* :doc:`/plugins/lyrics`: Searches now strip "featuring" artists when
  searching for lyrics, which should increase the hit rate for these tracks.
  Thanks to Fabrice Laporte.
* When listing the items in an album, the items are now always in track-number
  order. This should lead to more predictable listings from the
  :doc:`/plugins/importfeeds`.
* :doc:`/plugins/smartplaylist`: Queries are now split using shell-like syntax
  instead of just whitespace, so you can now construct terms that contain
  spaces.
* :doc:`/plugins/lastgenre`: The ``force`` config option now defaults to true
  and controls the behavior of the import hook. (Previously, new genres were
  always forced during import.)
* :doc:`/plugins/web`: Fix an error when specifying the hostname on the
  command line.
* :doc:`/plugins/web`: The underlying API was expanded slightly to support
  `Tomahawk`_ collections. And file transfers now have a "Content-Length"
  header. Thanks to Uwe L. Korn.
* :doc:`/plugins/lastgenre`: Fix an error when using genre canonicalization.

.. _Tomahawk: http://www.tomahawk-player.org/

1.1b3 (March 16, 2013)
----------------------

This third beta of beets 1.1 brings a hodgepodge of little new features (and
internal overhauls that will make improvements easier in the future). There
are new options for getting metadata in a particular language and seeing more
detail during the import process. There's also a new plugin for synchronizing
your metadata with MusicBrainz. Under the hood, plugins can now extend the
query syntax.

New configuration options:

* :ref:`languages` controls the preferred languages when selecting an alias
  from MusicBrainz. This feature requires `python-musicbrainz-ngs`_ 0.3 or
  later. Thanks to Sam Doshi.
* :ref:`detail` enables a mode where all tracks are listed in the importer UI,
  as opposed to only changed tracks.
* The ``--flat`` option to the ``beet import`` command treats an entire
  directory tree of music files as a single album. This can help in situations
  where a multi-disc album is split across multiple directories.
* :doc:`/plugins/importfeeds`: An option was added to use absolute, rather
  than relative, paths. Thanks to Lucas Duailibe.

Other stuff:

* A new :doc:`/plugins/mbsync` provides a command that looks up each item and
  track in MusicBrainz and updates your library to reflect it. This can help
  you easily correct errors that have been fixed in the MB database. Thanks to
  Jakob Schnitzer.
* :doc:`/plugins/fuzzy`: The ``fuzzy`` command was removed and replaced with a
  new query type. To perform fuzzy searches, use the ``~`` prefix with
  :ref:`list-cmd` or other commands. Thanks to Philippe Mongeau.
* As part of the above, plugins can now extend the query syntax and new kinds
  of matching capabilities to beets. See :ref:`extend-query`. Thanks again to
  Philippe Mongeau.
* :doc:`/plugins/convert`: A new ``--keep-new`` option lets you store
  transcoded files in your library while backing up the originals (instead of
  vice-versa). Thanks to Lucas Duailibe.
* :doc:`/plugins/convert`: Also, a new ``auto`` config option will transcode
  audio files automatically during import. Thanks again to Lucas Duailibe.
* :doc:`/plugins/chroma`: A new ``fingerprint`` command lets you generate and
  store fingerprints for items that don't yet have them. One more round of
  applause for Lucas Duailibe.
* :doc:`/plugins/echonest_tempo`: API errors now issue a warning instead of
  exiting with an exception. We also avoid an error when track metadata
  contains newlines.
* When the importer encounters an error (insufficient permissions, for
  example) when walking a directory tree, it now logs an error instead of
  crashing.
* In path formats, null database values now expand to the empty string instead
  of the string "None".
* Add "System Volume Information" (an internal directory found on some
  Windows filesystems) to the default ignore list.
* Fix a crash when ReplayGain values were set to null.
* Fix a crash when iTunes Sound Check tags contained invalid data.
* Fix an error when the configuration file (``config.yaml``) is completely
  empty.
* Fix an error introduced in 1.1b1 when importing using timid mode. Thanks to
  Sam Doshi.
* :doc:`/plugins/convert`: Fix a bug when creating files with Unicode
  pathnames.
* Fix a spurious warning from the Unidecode module when matching albums that
  are missing all metadata.
* Fix Unicode errors when a directory or file doesn't exist when invoking the
  import command. Thanks to Lucas Duailibe.
* :doc:`/plugins/mbcollection`: Show friendly, human-readable errors when
  MusicBrainz exceptions occur.
* :doc:`/plugins/echonest_tempo`: Catch socket errors that are not handled by
  the Echo Nest library.
* :doc:`/plugins/chroma`: Catch Acoustid Web service errors when submitting
  fingerprints.

1.1b2 (February 16, 2013)
-------------------------

The second beta of beets 1.1 uses the fancy new configuration infrastructure to
add many, many new config options. The import process is more flexible;
filenames can be customized in more detail; and more. This release also
supports Windows Media (ASF) files and iTunes Sound Check volume normalization.

This version introduces one **change to the default behavior** that you should
be aware of. Previously, when importing new albums matched in MusicBrainz, the
date fields (``year``, ``month``, and ``day``) would be set to the release date
of the *original* version of the album, as opposed to the specific date of the
release selected. Now, these fields reflect the specific release and
``original_year``, etc., reflect the earlier release date. If you want the old
behavior, just set :ref:`original_date` to true in your config file.

New configuration options:

* :ref:`default_action` lets you determine the default (just-hit-return) option
  is when considering a candidate.
* :ref:`none_rec_action` lets you skip the prompt, and automatically choose an
  action, when there is no good candidate. Thanks to Tai Lee.
* :ref:`max_rec` lets you define a maximum recommendation for albums with
  missing/extra tracks or differing track lengths/numbers. Thanks again to Tai
  Lee.
* :ref:`original_date` determines whether, when importing new albums, the
  ``year``, ``month``, and ``day`` fields should reflect the specific (e.g.,
  reissue) release date or the original release date. Note that the original
  release date is always available as ``original_year``, etc.
* :ref:`clutter` controls which files should be ignored when cleaning up empty
  directories. Thanks to Steinþór Pálsson.
* :doc:`/plugins/lastgenre`: A new configuration option lets you choose to
  retrieve artist-level tags as genres instead of album- or track-level tags.
  Thanks to Peter Fern and Peter Schnebel.
* :ref:`max_filename_length` controls truncation of long filenames. Also, beets
  now tries to determine the filesystem's maximum length automatically if you
  leave this option unset.
* :doc:`/plugins/fetchart`: The ``remote_priority`` option searches remote
  (Web) art sources even when local art is present.
* You can now customize the character substituted for path separators (e.g., /)
  in filenames via ``path_sep_replace``. The default is an underscore. Use this
  setting with caution.

Other new stuff:

* Support for Windows Media/ASF audio files. Thanks to Dave Hayes.
* New :doc:`/plugins/smartplaylist`: generate and maintain m3u playlist files
  based on beets queries. Thanks to Dang Mai Hai.
* ReplayGain tags on MPEG-4/AAC files are now supported. And, even more
  astonishingly, ReplayGain values in MP3 and AAC files are now compatible with
  `iTunes Sound Check`_. Thanks to Dave Hayes.
* Track titles in the importer UI's difference display are now either aligned
  vertically or broken across two lines for readability. Thanks to Tai Lee.
* Albums and items have new fields reflecting the *original* release date
  (``original_year``, ``original_month``, and ``original_day``). Previously,
  when tagging from MusicBrainz, *only* the original date was stored; now, the
  old fields refer to the *specific* release date (e.g., when the album was
  reissued).
* Some changes to the way candidates are recommended for selection, thanks to
  Tai Lee:

  * According to the new :ref:`max_rec` configuration option, partial album
    matches are downgraded to a "low" recommendation by default.
  * When a match isn't great but is either better than all the others or the
    only match, it is given a "low" (rather than "medium") recommendation.
  * There is no prompt default (i.e., input is required) when matches are
    bad: "low" or "none" recommendations or when choosing a candidate
    other than the first.

* The importer's heuristic for coalescing the directories in a multi-disc album
  has been improved. It can now detect when two directories alongside each
  other share a similar prefix but a different number (e.g., "Album Disc 1" and
  "Album Disc 2") even when they are not alone in a common parent directory.
  Thanks once again to Tai Lee.
* Album listings in the importer UI now show the release medium (CD, Vinyl,
  3xCD, etc.) as well as the disambiguation string. Thanks to Peter Schnebel.
* :doc:`/plugins/lastgenre`: The plugin can now get different genres for
  individual tracks on an album. Thanks to Peter Schnebel.
* When getting data from MusicBrainz, the album disambiguation string
  (``albumdisambig``) now reflects both the release and the release group.
* :doc:`/plugins/mpdupdate`: Sends an update message whenever *anything* in the
  database changes---not just when importing. Thanks to Dang Mai Hai.
* When the importer UI shows a difference in track numbers or durations, they
  are now colorized based on the *suffixes* that differ. For example, when
  showing the difference between 2:01 and 2:09, only the last digit will be
  highlighted.
* The importer UI no longer shows a change when the track length difference is
  less than 10 seconds. (This threshold was previously 2 seconds.)
* Two new plugin events were added: *database_change* and *cli_exit*. Thanks
  again to Dang Mai Hai.
* Plugins are now loaded in the order they appear in the config file. Thanks to
  Dang Mai Hai.
* :doc:`/plugins/bpd`: Browse by album artist and album artist sort name.
  Thanks to Steinþór Pálsson.
* :doc:`/plugins/echonest_tempo`: Don't attempt a lookup when the artist or
  track title is missing.
* Fix an error when migrating the ``.beetsstate`` file on Windows.
* A nicer error message is now given when the configuration file contains tabs.
  (YAML doesn't like tabs.)
* Fix the ``-l`` (log path) command-line option for the ``import`` command.

.. _iTunes Sound Check: http://support.apple.com/kb/HT2425

1.1b1 (January 29, 2013)
------------------------

This release entirely revamps beets' configuration system. The configuration
file is now a `YAML`_ document and is located, along with other support files,
in a common directory (e.g., ``~/.config/beets`` on Unix-like systems). If
you're upgrading from an earlier version, please see :doc:`/guides/migration`.

.. _YAML: http://en.wikipedia.org/wiki/YAML

* Renamed plugins: The ``rdm`` plugin has been renamed to ``random`` and
  ``fuzzy_search`` has been renamed to ``fuzzy``.
* Renamed config options: Many plugins have a flag dictating whether their
  action runs at import time. This option had many names (``autofetch``,
  ``autoembed``, etc.) but is now consistently called ``auto``.
* Reorganized import config options: The various ``import_*`` options are now
  organized under an ``import:`` heading and their prefixes have been removed.
* New default file locations: The default filename of the library database is
  now ``library.db`` in the same directory as the config file, as opposed to
  ``~/.beetsmusic.blb`` previously. Similarly, the runtime state file is now
  called ``state.pickle`` in the same directory instead of ``~/.beetsstate``.

It also adds some new features:

* :doc:`/plugins/inline`: Inline definitions can now contain statements or
  blocks in addition to just expressions. Thanks to Florent Thoumie.
* Add a configuration option, :ref:`terminal_encoding`, controlling the text
  encoding used to print messages to standard output.
* The MusicBrainz hostname (and rate limiting) are now configurable. See
  :ref:`musicbrainz-config`.
* You can now configure the similarity thresholds used to determine when the
  autotagger automatically accepts a metadata match. See :ref:`match-config`.
* :doc:`/plugins/importfeeds`: Added a new configuration option that controls
  the base for relative paths used in m3u files. Thanks to Philippe Mongeau.

1.0.0 (January 29, 2013)
------------------------

After fifteen betas and two release candidates, beets has finally hit
one-point-oh. Congratulations to everybody involved. This version of beets will
remain stable and receive only bug fixes from here on out. New development is
ongoing in the betas of version 1.1.

* :doc:`/plugins/scrub`: Fix an incompatibility with Python 2.6.
* :doc:`/plugins/lyrics`: Fix an issue that failed to find lyrics when metadata
  contained "real" apostrophes.
* :doc:`/plugins/replaygain`: On Windows, emit a warning instead of
  crashing when analyzing non-ASCII filenames.
* Silence a spurious warning from version 0.04.12 of the Unidecode module.

1.0rc2 (December 31, 2012)
--------------------------

This second release candidate follows quickly after rc1 and fixes a few small
bugs found since that release. There were a couple of regressions and some bugs
in a newly added plugin.

* :doc:`/plugins/echonest_tempo`: If the Echo Nest API limit is exceeded or a
  communication error occurs, the plugin now waits and tries again instead of
  crashing. Thanks to Zach Denton.
* :doc:`/plugins/fetchart`: Fix a regression that caused crashes when art was
  not available from some sources.
* Fix a regression on Windows that caused all relative paths to be "not found".

1.0rc1 (December 17, 2012)
--------------------------

The first release candidate for beets 1.0 includes a deluge of new features
contributed by beets users. The vast majority of the credit for this release
goes to the growing and vibrant beets community. A million thanks to everybody
who contributed to this release.

There are new plugins for transcoding music, fuzzy searches, tempo collection,
and fiddling with metadata. The ReplayGain plugin has been rebuilt from
scratch. Album art images can now be resized automatically. Many other smaller
refinements make things "just work" as smoothly as possible.

With this release candidate, beets 1.0 is feature-complete. We'll be fixing
bugs on the road to 1.0 but no new features will be added. Concurrently, work
begins today on features for version 1.1.

* New plugin: :doc:`/plugins/convert` **transcodes** music and embeds album art
  while copying to a separate directory. Thanks to Jakob Schnitzer and Andrew G.
  Dunn.
* New plugin: :doc:`/plugins/fuzzy` lets you find albums and tracks
  using **fuzzy string matching** so you don't have to type (or even remember)
  their exact names. Thanks to Philippe Mongeau.
* New plugin: :doc:`/plugins/echonest_tempo` fetches **tempo** (BPM) information
  from `The Echo Nest`_. Thanks to David Brenner.
* New plugin: :doc:`/plugins/the` adds a template function that helps format
  text for nicely-sorted directory listings. Thanks to Blemjhoo Tezoulbr.
* New plugin: :doc:`/plugins/zero` **filters out undesirable fields** before
  they are written to your tags. Thanks again to Blemjhoo Tezoulbr.
* New plugin: :doc:`/plugins/ihate` automatically skips (or warns you about)
  importing albums that match certain criteria. Thanks once again to Blemjhoo
  Tezoulbr.
* :doc:`/plugins/replaygain`: This plugin has been completely overhauled to use
  the `mp3gain`_ or `aacgain`_ command-line tools instead of the failure-prone
  Gstreamer ReplayGain implementation. Thanks to Fabrice Laporte.
* :doc:`/plugins/fetchart` and :doc:`/plugins/embedart`: Both plugins can now
  **resize album art** to avoid excessively large images. Use the ``maxwidth``
  config option with either plugin. Thanks to Fabrice Laporte.
* :doc:`/plugins/scrub`: Scrubbing now removes *all* types of tags from a file
  rather than just one. For example, if your FLAC file has both ordinary FLAC
  tags and ID3 tags, the ID3 tags are now also removed.
* :ref:`stats-cmd` command: New ``--exact`` switch to make the file size
  calculation more accurate (thanks to Jakob Schnitzer).
* :ref:`list-cmd` command: Templates given with ``-f`` can now show items' and
  albums' paths (using ``$path``).
* The output of the :ref:`update-cmd`, :ref:`remove-cmd`, and :ref:`modify-cmd`
  commands now respects the :ref:`list_format_album` and
  :ref:`list_format_item` config options. Thanks to Mike Kazantsev.
* The :ref:`art-filename` option can now be a template rather than a simple
  string. Thanks to Jarrod Beardwood.
* Fix album queries for ``artpath`` and other non-item fields.
* Null values in the database can now be matched with the empty-string regular
  expression, ``^$``.
* Queries now correctly match non-string values in path format predicates.
* When autotagging a various-artists album, the album artist field is now
  used instead of the majority track artist.
* :doc:`/plugins/lastgenre`: Use the albums' existing genre tags if they pass
  the whitelist (thanks to Fabrice Laporte).
* :doc:`/plugins/lastgenre`: Add a ``lastgenre`` command for fetching genres
  post facto (thanks to Jakob Schnitzer).
* :doc:`/plugins/fetchart`: Local image filenames are now used in alphabetical
  order.
* :doc:`/plugins/fetchart`: Fix a bug where cover art filenames could lack
  a ``.jpg`` extension.
* :doc:`/plugins/lyrics`: Fix an exception with non-ASCII lyrics.
* :doc:`/plugins/web`: The API now reports file sizes (for use with the
  `Tomahawk resolver`_).
* :doc:`/plugins/web`: Files now download with a reasonable filename rather
  than just being called "file" (thanks to Zach Denton).
* :doc:`/plugins/importfeeds`: Fix error in symlink mode with non-ASCII
  filenames.
* :doc:`/plugins/mbcollection`: Fix an error when submitting a large number of
  releases (we now submit only 200 releases at a time instead of 350). Thanks
  to Jonathan Towne.
* :doc:`/plugins/embedart`: Made the method for embedding art into FLAC files
  `standard
  <https://wiki.xiph.org/VorbisComment#METADATA_BLOCK_PICTURE>`_-compliant.
  Thanks to Daniele Sluijters.
* Add the track mapping dictionary to the ``album_distance`` plugin function.
* When an exception is raised while reading a file, the path of the file in
  question is now logged (thanks to Mike Kazantsev).
* Truncate long filenames based on their *bytes* rather than their Unicode
  *characters*, fixing situations where encoded names could be too long.
* Filename truncation now incorporates the length of the extension.
* Fix an assertion failure when the MusicBrainz main database and search server
  disagree.
* Fix a bug that caused the :doc:`/plugins/lastgenre` and other plugins not to
  modify files' tags even when they successfully change the database.
* Fix a VFS bug leading to a crash in the :doc:`/plugins/bpd` when files had
  non-ASCII extensions.
* Fix for changing date fields (like "year") with the :ref:`modify-cmd`
  command.
* Fix a crash when input is read from a pipe without a specified encoding.
* Fix some problem with identifying files on Windows with Unicode directory
  names in their path.
* Fix a crash when Unicode queries were used with ``import -L`` re-imports.
* Fix an error when fingerprinting files with Unicode filenames on Windows.
* Warn instead of crashing when importing a specific file in singleton mode.
* Add human-readable error messages when writing files' tags fails or when a
  directory can't be created.
* Changed plugin loading so that modules can be imported without
  unintentionally loading the plugins they contain.

.. _The Echo Nest: http://the.echonest.com/
.. _Tomahawk resolver: http://beets.radbox.org/blog/tomahawk-resolver.html
.. _mp3gain: http://mp3gain.sourceforge.net/download.php
.. _aacgain: http://aacgain.altosdesign.com

1.0b15 (July 26, 2012)
----------------------

The fifteenth (!) beta of beets is compendium of small fixes and features, most
of which represent long-standing requests. The improvements include matching
albums with extra tracks, per-disc track numbering in multi-disc albums, an
overhaul of the album art downloader, and robustness enhancements that should
keep beets running even when things go wrong. All these smaller changes should
help us focus on some larger changes coming before 1.0.

Please note that this release contains one backwards-incompatible change: album
art fetching, which was previously baked into the import workflow, is now
encapsulated in a plugin (the :doc:`/plugins/fetchart`). If you want to continue
fetching cover art for your music, enable this plugin after upgrading to beets
1.0b15.

* The autotagger can now find matches for albums when you have **extra tracks**
  on your filesystem that aren't present in the MusicBrainz catalog. Previously,
  if you tried to match album with 15 audio files but the MusicBrainz entry had
  only 14 tracks, beets would ignore this match. Now, beets will show you
  matches even when they are "too short" and indicate which tracks from your
  disk are unmatched.
* Tracks on multi-disc albums can now be **numbered per-disc** instead of
  per-album via the :ref:`per_disc_numbering` config option.
* The default output format for the ``beet list`` command is now configurable
  via the :ref:`list_format_item` and :ref:`list_format_album` config options.
  Thanks to Fabrice Laporte.
* Album **cover art fetching** is now encapsulated in the
  :doc:`/plugins/fetchart`. Be sure to enable this plugin if you're using this
  functionality. As a result of this new organization, the new plugin has gained
  a few new features:

  * "As-is" and non-autotagged imports can now have album art imported from
    the local filesystem (although Web repositories are still not searched in
    these cases).
  * A new command, ``beet fetchart``, allows you to download album art
    post-import. If you only want to fetch art manually, not automatically
    during import, set the new plugin's ``autofetch`` option to ``no``.
  * New album art sources have been added.

* Errors when communicating with MusicBrainz now log an error message instead of
  halting the importer.
* Similarly, filesystem manipulation errors now print helpful error messages
  instead of a messy traceback. They still interrupt beets, but they should now
  be easier for users to understand. Tracebacks are still available in verbose
  mode.
* New metadata fields for `artist credits`_: ``artist_credit`` and
  ``albumartist_credit`` can now contain release- and recording-specific
  variations of the artist's name. See :ref:`itemfields`.
* Revamped the way beets handles concurrent database access to avoid
  nondeterministic SQLite-related crashes when using the multithreaded importer.
  On systems where SQLite was compiled without ``usleep(3)`` support,
  multithreaded database access could cause an internal error (with the message
  "database is locked"). This release synchronizes access to the database to
  avoid internal SQLite contention, which should avoid this error.
* Plugins can now add parallel stages to the import pipeline. See
  :ref:`writing-plugins`.
* Beets now prints out an error when you use an unrecognized field name in a
  query: for example, when running ``beet ls -a artist:foo`` (because ``artist``
  is an item-level field).
* New plugin events:

  * ``import_task_choice`` is called after an import task has an action
    assigned.
  * ``import_task_files`` is called after a task's file manipulation has
    finished (copying or moving files, writing metadata tags).
  * ``library_opened`` is called when beets starts up and opens the library
    database.

* :doc:`/plugins/lastgenre`: Fixed a problem where path formats containing
  ``$genre`` would use the old genre instead of the newly discovered one.
* Fix a crash when moving files to a Samba share.
* :doc:`/plugins/mpdupdate`: Fix TypeError crash (thanks to Philippe Mongeau).
* When re-importing files with ``import_copy`` enabled, only files inside the
  library directory are moved. Files outside the library directory are still
  copied. This solves a problem (introduced in 1.0b14) where beets could crash
  after adding files to the library but before finishing copying them; during
  the next import, the (external) files would be moved instead of copied.
* Artist sort names are now populated correctly for multi-artist tracks and
  releases. (Previously, they only reflected the first artist.)
* When previewing changes during import, differences in track duration are now
  shown as "2:50 vs. 3:10" rather than separated with ``->`` like track numbers.
  This should clarify that beets isn't doing anything to modify lengths.
* Fix a problem with query-based path format matching where a field-qualified
  pattern, like ``albumtype_soundtrack``, would match everything.
* :doc:`/plugins/chroma`: Fix matching with ambiguous Acoustids. Some Acoustids
  are identified with multiple recordings; beets now considers any associated
  recording a valid match. This should reduce some cases of errant track
  reordering when using chroma.
* Fix the ID3 tag name for the catalog number field.
* :doc:`/plugins/chroma`: Fix occasional crash at end of fingerprint submission
  and give more context to "failed fingerprint generation" errors.
* Interactive prompts are sent to stdout instead of stderr.
* :doc:`/plugins/embedart`: Fix crash when audio files are unreadable.
* :doc:`/plugins/bpd`: Fix crash when sockets disconnect (thanks to Matteo
  Mecucci).
* Fix an assertion failure while importing with moving enabled when the file was
  already at its destination.
* Fix Unicode values in the ``replace`` config option (thanks to Jakob Borg).
* Use a nicer error message when input is requested but stdin is closed.
* Fix errors on Windows for certain Unicode characters that can't be represented
  in the MBCS encoding. This required a change to the way that paths are
  represented in the database on Windows; if you find that beets' paths are out
  of sync with your filesystem with this release, delete and recreate your
  database with ``beet import -AWC /path/to/music``.
* Fix ``import`` with relative path arguments on Windows.

.. _artist credits: http://wiki.musicbrainz.org/Artist_Credit

1.0b14 (May 12, 2012)
---------------------

The centerpiece of this beets release is the graceful handling of
similarly-named albums. It's now possible to import two albums with the same
artist and title and to keep them from conflicting in the filesystem. Many other
awesome new features were contributed by the beets community, including regular
expression queries, artist sort names, moving files on import. There are three
new plugins: random song/album selection; MusicBrainz "collection" integration;
and a plugin for interoperability with other music library systems.

A million thanks to the (growing) beets community for making this a huge
release.

* The importer now gives you **choices when duplicates are detected**.
  Previously, when beets found an existing album or item in your library
  matching the metadata on a newly-imported one, it would just skip the new
  music to avoid introducing duplicates into your library. Now, you have three
  choices: skip the new music (the previous behavior), keep both, or remove the
  old music. See the :ref:`guide-duplicates` section in the autotagging guide
  for details.
* Beets can now avoid storing identically-named albums in the same directory.
  The new ``%aunique{}`` template function, which is included in the default
  path formats, ensures that Crystal Castles' albums will be placed into
  different directories. See :ref:`aunique` for details.
* Beets queries can now use **regular expressions**. Use an additional ``:`` in
  your query to enable regex matching. See :ref:`regex` for the full details.
  Thanks to Matteo Mecucci.
* Artist **sort names** are now fetched from MusicBrainz. There are two new data
  fields, ``artist_sort`` and ``albumartist_sort``, that contain sortable artist
  names like "Beatles, The". These fields are also used to sort albums and items
  when using the ``list`` command. Thanks to Paul Provost.
* Many other **new metadata fields** were added, including ASIN, label catalog
  number, disc title, encoder, and MusicBrainz release group ID. For a full list
  of fields, see :ref:`itemfields`.
* :doc:`/plugins/chroma`: A new command, ``beet submit``, will **submit
  fingerprints** to the Acoustid database. Submitting your library helps
  increase the coverage and accuracy of Acoustid fingerprinting. The Chromaprint
  fingerprint and Acoustid ID are also now stored for all fingerprinted tracks.
  This version of beets *requires* at least version 0.6 of `pyacoustid`_ for
  fingerprinting to work.
* The importer can now **move files**. Previously, beets could only copy files
  and delete the originals, which is inefficient if the source and destination
  are on the same filesystem. Use the ``import_move`` configuration option and
  see :doc:`/reference/config` for more details. Thanks to Domen Kožar.
* New :doc:`/plugins/random`: Randomly select albums and tracks from your library.
  Thanks to Philippe Mongeau.
* The :doc:`/plugins/mbcollection` by Jeffrey Aylesworth was added to the core
  beets distribution.
* New :doc:`/plugins/importfeeds`: Catalog imported files in ``m3u`` playlist
  files or as symlinks for easy importing to other systems. Thanks to Fabrice
  Laporte.
* The ``-f`` (output format) option to the ``beet list`` command can now contain
  template functions as well as field references. Thanks to Steve Dougherty.
* A new command ``beet fields`` displays the available metadata fields (thanks
  to Matteo Mecucci).
* The ``import`` command now has a ``--noincremental`` or ``-I`` flag to disable
  incremental imports (thanks to Matteo Mecucci).
* When the autotagger fails to find a match, it now displays the number of
  tracks on the album (to help you guess what might be going wrong) and a link
  to the FAQ.
* The default filename character substitutions were changed to be more
  conservative. The Windows "reserved characters" are substituted by default
  even on Unix platforms (this causes less surprise when using Samba shares to
  store music). To customize your character substitutions, see :ref:`the replace
  config option <replace>`.
* :doc:`/plugins/lastgenre`: Added a "fallback" option when no suitable genre
  can be found (thanks to Fabrice Laporte).
* :doc:`/plugins/rewrite`: Unicode rewriting rules are now allowed (thanks to
  Nicolas Dietrich).
* Filename collisions are now avoided when moving album art.
* :doc:`/plugins/bpd`: Print messages to show when directory tree is being
  constructed.
* :doc:`/plugins/bpd`: Use Gstreamer's ``playbin2`` element instead of the
  deprecated ``playbin``.
* :doc:`/plugins/bpd`: Random and repeat modes are now supported (thanks to
  Matteo Mecucci).
* :doc:`/plugins/bpd`: Listings are now sorted (thanks once again to Matteo
  Mecucci).
* Filenames are normalized with Unicode Normal Form D (NFD) on Mac OS X and NFC
  on all other platforms.
* Significant internal restructuring to avoid SQLite locking errors. As part of
  these changes, the not-very-useful "save" plugin event has been removed.

.. _pyacoustid: https://github.com/sampsyo/pyacoustid


1.0b13 (March 16, 2012)
-----------------------

Beets 1.0b13 consists of a plethora of small but important fixes and
refinements. A lyrics plugin is now included with beets; new audio properties
are catalogged; the ``list`` command has been made more powerful; the autotagger
is more tolerant of different tagging styles; and importing with original file
deletion now cleans up after itself more thoroughly. Many, many bugs—including
several crashers—were fixed. This release lays the foundation for more features
to come in the next couple of releases.

* The :doc:`/plugins/lyrics`, originally by `Peter Brunner`_, is revamped and
  included with beets, making it easy to fetch **song lyrics**.
* Items now expose their audio **sample rate**, number of **channels**, and
  **bits per sample** (bitdepth). See :doc:`/reference/pathformat` for a list of
  all available audio properties. Thanks to Andrew Dunn.
* The ``beet list`` command now accepts a "format" argument that lets you **show
  specific information about each album or track**. For example, run ``beet ls
  -af '$album: $tracktotal' beatles`` to see how long each Beatles album is.
  Thanks to Philippe Mongeau.
* The autotagger now tolerates tracks on multi-disc albums that are numbered
  per-disc. For example, if track 24 on a release is the first track on the
  second disc, then it is not penalized for having its track number set to 1
  instead of 24.
* The autotagger sets the disc number and disc total fields on autotagged
  albums.
* The autotagger now also tolerates tracks whose track artists tags are set
  to "Various Artists".
* Terminal colors are now supported on Windows via `Colorama`_ (thanks to Karl).
* When previewing metadata differences, the importer now shows discrepancies in
  track length.
* Importing with ``import_delete`` enabled now cleans up empty directories that
  contained deleting imported music files.
* Similarly, ``import_delete`` now causes original album art imported from the
  disk to be deleted.
* Plugin-supplied template values, such as those created by ``rewrite``, are now
  properly sanitized (for example, ``AC/DC`` properly becomes ``AC_DC``).
* Filename extensions are now always lower-cased when copying and moving files.
* The ``inline`` plugin now prints a more comprehensible error when exceptions
  occur in Python snippets.
* The ``replace`` configuration option can now remove characters entirely (in
  addition to replacing them) if the special string ``<strip>`` is specified as
  the replacement.
* New plugin API: plugins can now add fields to the MediaFile tag abstraction
  layer. See :ref:`writing-plugins`.
* A reasonable error message is now shown when the import log file cannot be
  opened.
* The import log file is now flushed and closed properly so that it can be used
  to monitor import progress, even when the import crashes.
* Duplicate track matches are no longer shown when autotagging singletons.
* The ``chroma`` plugin now logs errors when fingerprinting fails.
* The ``lastgenre`` plugin suppresses more errors when dealing with the Last.fm
  API.
* Fix a bug in the ``rewrite`` plugin that broke the use of multiple rules for
  a single field.
* Fix a crash with non-ASCII characters in bytestring metadata fields (e.g.,
  MusicBrainz IDs).
* Fix another crash with non-ASCII characters in the configuration paths.
* Fix a divide-by-zero crash on zero-length audio files.
* Fix a crash in the ``chroma`` plugin when the Acoustid database had no
  recording associated with a fingerprint.
* Fix a crash when an autotagging with an artist or album containing "AND" or
  "OR" (upper case).
* Fix an error in the ``rewrite`` and ``inline`` plugins when the corresponding
  config sections did not exist.
* Fix bitrate estimation for AAC files whose headers are missing the relevant
  data.
* Fix the ``list`` command in BPD (thanks to Simon Chopin).

.. _Colorama: http://pypi.python.org/pypi/colorama

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
