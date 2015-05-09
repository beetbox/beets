BetterListing Plugin
====================

The ``betterlisting`` plugin allows you to query and list your collection
with extended queries and listing formats. This plugin provides several
query modifiers, template fields and functions for use in your beets
configuration. Please, note that, this plugin is intended for advanced
users, and may confuse initial users.

Installation
------------

To use the ``betterlisting`` plugin, first enable it in your configuration
(see :ref:`using-plugins`). Then, read on to know the various fields and
functions provided by this plugin. For getting a taste of what this plugin
can do for you, please add ``$icons`` in ``format_item`` and
``format_album`` configuration option for ``beets``.

Template Functions
------------------

This plugin provides several template functions (see
:ref:`template-functions`) to perfectly layout your queries on the
terminal.

* ``%colorize{text,color}``: Color ``text`` using ``color`` for the
  terminal. Available colors are: ``black darkred darkgreen brown
  darkblue purple teal lightgray darkgray red green yellow blue fuchsia
  turquoise white``

  For example, you can colorize your albums in a blue color like this::

    format_album: %colorize{$album,blue}

* ``%rpad{text,n}``: Right pad the given ``text`` to ``n`` characters.
  This is useful in aligning your query results, and hence, display them
  in a tabular format. Note that, if the ``text`` exceeds this length, the
  whole ``text`` will be displayed, which can skew your tabular listing.

  For example, you can align your query results in a table format::

    format_album: [$year] %rpad{$title,40} $artist

* ``%lpad{text,n}``: Left pad the given ``text`` to ``n`` characters.

* ``%rtrimpad{text,n}``: Right pad the given ``text`` to ``n`` characters.
  If the ``text`` exceeds ``n`` characters, trim it so that it only
  occupies ``n`` characters in the results. This is useful in tabular
  formatting of your results, and ensuring that no column exceeds the
  given width. Also, to properly align your ``text``, all ANSI escape
  codes will be ignored for calculating the text width.

  For example, you can align your query results in a table format like
  this (note that if ``$title`` exceeds ``40`` chars, it will be
  truncated in this example)::

    format_album: [$year] %rtrimpad{$title,40} $artist

* ``%ltrimpad{text,n}``: Left pad the given ``text`` to ``n`` characters.
  If the ``text`` exceeds ``n`` charaacters, trim it so that it only
  occupies ``n`` characters in the results.

* ``%sparkbar{count,total}``: Print out unicode histogram for the given
  ``count`` and ``total`` using `spark`_.
  
  For example, with the defaults, calling something like
  ``%sparkbar{$missing,$total}`` will produce a unicode character from the
  following characters ``▇▆▅▄▃▂▁`` as per the ratio between missing and
  total tracks of the album.

Template Fields
---------------

This plugin, also, provides several template fields that you can use for
formatting your query results. For example, you can use ``$duration`` in
your format to display the total duration of that item or album. Available
template fields are:

* ``$duration``: track length (duration) for the corresponding item, or in
  case of albums, the total length of the tracks for the given album in a
  human readable time format. Time format is customizable using the
  ``duration_format`` config option.

  For example, if you want to search for tracks sorted according to their
  track length, you can say::

    beet ls -f '$duration %rpad{$artist,30} $title | sort -nr

  which produces the following for my library::

    06:54 Lana Del Rey                   Summertime Sadness (Cedric Gervais vocal down mix)
    06:34 Elbow                          One Day Like This
    06:31 DJ Khaled                      Hold You Down ft. Chris Brown, August Alsina, Future & Jeremih
    05:58 Romeo Santos                   Yo también ft. Marc Anthony
    05:55 Justin Timberlake              Take Back the Night
    05:51 Muse                           Psycho
    05:47 Florence + the Machine         What Kind of Man
    05:46 Action Bronson                 Baby Blue feat. Chance the Rapper
    05:40 Disclosure                     White Noise ft. AlunaGeorge
    05:38 JAY Z                          Holy Grail ft. Justin Timberlake
    ....

* ``$duration_sort``: track length for a single item or total length of
  tracks for the album as an integer. Useful in sorting and querying the
  collection based on the duration of the items/albums.

  For example, in the above example, we could have simply used
  ``duration_sort-`` to sort the results, like this::

    beet ls -f '$duration %rpad{$artist,30} $title duration_sort-

* ``$lyrics_sort``: floating point value indicating if the lyrics are
  present for a particular item. If lyrics are present, ``$lyrics_sort``
  will be ``1.0``, and if they are absent, it will be ``0.0``. In case of
  albums, if some of the lyrics are present but not all, value will be the
  ratio of tracks with lyrics vs total tracks for that album.

  For example, we can ask the :doc:`lyrics` to only fetch information for
  tracks that are missing the lyrics (thereby, saving time on a large
  collection)::

    beet lyrics lyrics_sort:0

  Or, we can simply query the collection for albums which have more than
  half of the tracks without lyrics::

    beet lyrics lyrics_sort:0..0.5

* ``$avg_duration``: for albums, expands to the average track length of
  the songs in that album that are present in the library. Like
  ``$duration`` field, time format is customizable using the
  ``duration_format`` config option.

* ``$avg_duration_sort``: expands to average track length of the album as
  an integer. Useful in sorting and querying the collection based on the
  average duration of albums.

* ``$missing``: expands to the number of missing tracks in the album.
  Same as the ``$missing`` field provided by the :doc:`missing`.
  Note that, this plugin does not provide the functionality to query the
  missing tracks via musicbrainz.

* ``$available``: expands to the number of tracks in the album, that are
  available in the library.

* ``$total``: expands to the total number of tracks in the album, as
  reported by musicbrainz (requires :doc:`missing`), or from the
  ``tracktotal`` field of the individual tracks in that album.

**Note that template fields and functions can, also, be used inside custom
path formats, and inside your beet configuration. Also, all template
fields can also be used to query the library, and for sorting thanks to
the new query feature of ``beets``**

.. _icon-template-fields:

Icon Template Fields
--------------------

:doc:`betterlisting` provides some customizable template fields that print
icons to your console when used in path format strings. For example, you
can display a red ``L`` in front of tracks that don't have any lyrics
associated with them, when listing your collection.

* ``$icons``: When used in path format strings, expands to all the icons
  provided by this plugin. This field is customizable via the
  ``format_item`` and ``format_album`` configuration options of this
  plugin.

* ``$missing_icon``: Icon/string to display when an album has some or no
  tracks missing. This field is customizable via the ``icon_missing_some``
  and ``icon_missing_none`` configuration options for this plugin.

* ``$lyrics_icon``: Icon/string  to display when an album has lyrics
  present for all, none or some of the tracks. For an item, it displays
  icons according to whether it has lyrics associated with it.
  Customizable via the configuration options.

.. _sparkbar-fields:

SparkBar Fields
---------------

* ``$duration_bar``: track length of the item (and, average track length
  in case of albums) as a spark bar plotted against a customizable
  duration (via the ``track_length`` configuration option).

* ``$missing_bar``: number of missing tracks for the album plotted, as a
  spark bar, against the total number of tracks in that album according to
  the musicbrainz database (requires :doc:`missing`), or according to the
  ``tracktotal`` field of individual tracks in that album.

* ``$available_bar``: number of available tracks in your library plotted,
  as a spark bar, against the total number of tracks in that album.

Configuration
-------------

The plugin provides several configuration options that you can define in
the ``betterlisting:`` section of the config file. The defaults look like
this::

    betterlisting:
        sparks:             '▇▆▅▄▃▂▁ '
        track_length:       360
        duration_format:    '{mins:02d}:{secs:02d}',
        format_item:        $lyrics_icon %colorize{$duration_bar,blue}
        format_album:       $lyrics_icon %colorize{$duration_bar,blue} $missing_icon
        icon_missing_none:  ''
        icon_missing_some:  %colorize{◎,red}
        icon_lyrics_all:    128215
        icon_lyrics_some:   128217
        icon_lyrics_none:   128213

Yeah, that's a lot of configuration options, but this plugin allows you to
customize everything to suite your needs. Here is a description of all
these configuration options:

- **sparks**: defines that characters to use for generating the spark bars
  for fields like ``$duration_bar``, ``$missing_bar``, etc. You can add
  more characters or remove from the default to customize the spark bar.
  Allows unicode characters. See :ref:`sparkbar-fields`
- **track_length**: Base track length (in seconds) to use for generating
  the ``$duration_bar``. The spark bar will be full when track length of
  the individual items (or average track length in case of albums) will be
  above this duration.
- **duration_format**: python string formatting tempalte to use for
  formatting the track length of the items before displaying it on the
  terminal. By default, duration will be listed as: ``MM::SS``.
- **format_item**: path format string to use when generating ``$icons``
  for the individual items in your library. You can use any template field
  or functions here, and simply, add ``$icons`` in your path format string
  for items. See :ref:`icon-template-fields`
- **format_album**: same as above, but for albums.
- **icon_missing_none**: icon to use for ``$missing_icon`` when no track
  is missing from the album. You can use template functions and fields
  here, or simply provide an integer which will be converted to special
  unicode characters. See: :ref:`unicode-special-characters`
- **icon_missing_some**: icon to use for ``$missing_icon`` when some of
  the tracks are missing from the album. You can use template functions
  and fields here, or simply provide an integer which will be converted to
  special unicode characters. See: :ref:`unicode-special-characters`
- **icon_lyrics_all**: icon to use for ``$lyrics_icon`` when the track has
  lyrics, or in case of albums when all tracks have lyrics. You can use
  template functions and fields here, or simply provide an integer which
  will be converted to special unicode characters. See:
  :ref:`unicode-special-characters`
- **icon_lyrics_none**: icon to use for ``$lyrics_icon`` when the track
  does not have lyrics, or in case of albums when no tracks have lyrics.
  You can use template functions and fields here, or simply provide an
  integer which will be converted to special unicode characters. See:
  :ref:`unicode-special-characters`
- **icon_lyrics_somee**: icon to use for ``$lyrics_icon`` in case of
  albums when some of the tracks have lyrics missing. You can use template
  functions and fields here, or simply provide an integer which will be
  converted to special unicode characters. See:
  :ref:`unicode-special-characters`

.. _unicode-special-characters:

Unicode Special Characters
--------------------------

Though, most unicode characters are supported by the beet configuration,
yet, it does not allow special characters (eg. certain emojis etc.), which
are sometimes a perfect fit as an icon. For example, a ``:greenbook:``
unicode character can be used as a means to denote tracks that have lyrics
with them, while a ``:redbook:`` unicode character can denote tracks that
don't have lyrics with them.

In order to add these icons/unicode characters, you can use the integer
representation of these unicode characters. For example, we can find the
integer representation of ``:greenbook:`` `on this page`_. Under the
``UTF-32 (decimal)`` field, we can find that this unicode character is
represented by the number ``128215``, which we can use in our
configuration.

Please, note that you can not use any template field or functions when
using integers for these fields.

Easier Querying
---------------

This plugin provides several fields that can be used for sorting or
querying the database. You can use :doc:`types` and specify the following
configuration for easiery querying::

    types:
      lyrics_sort: float
      duration_sort: int
      avg_duration_sort: int
      missing: int
      available: int
      total: int

.. _spark: https://github.com/holman/spark
.. _on this page: http://www.fileformat.info/info/unicode/char/1f4d7/index.htm
