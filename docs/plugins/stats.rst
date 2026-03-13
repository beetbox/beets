Stats Plugin
============

The ``stats`` plugin provides commands for displaying statistics about your
music library, such as the total number of tracks, artists, albums, and the
overall size and duration of your collection.

Basic Statistics
----------------

By default, the ``stats`` command prints a concise summary of the library or a
query result:

::

    $ beet stats

This includes:

- Total number of matched tracks
- Total listening time
- Approximate total size of audio files
- Number of artists, albums, and album artists

Exact Mode
----------

The ``-e`` / ``--exact`` flag enables *exact* size and duration calculations:

::

    $ beet stats --exact

When this flag is used, the command:

- Computes file sizes directly from the filesystem instead of estimating them
  from bitrate and duration
- Prints both human-readable values and raw byte/second counts
- May be slower on large libraries, as it requires accessing every audio file

This mode is useful when precise storage or duration figures are required.

Overview Report
---------------

In addition to the standard output, the ``stats`` command supports an
*overview-style* report that generates a detailed, human-readable summary of
your library.

To generate this report, run:

::

    $ beet stats --overview

This prints a comprehensive report including general library statistics,
listening time, audio quality information, decade distribution, and summary
highlights.

Example output:

::

    Beets Library Report
    Generated: 2026-01-05 12:34:56
    ============================================================
    Overview
      Tracks:   124
      Albums:   30
      Artists:  20
      Genres:   12
      Years:    1998 – 2022
    ------------------------------------------------------------
    Listening time & quality
      Total playtime:   12:34:56
      Avg track length: 00:06:07
      Avg bitrate:      320 kbps (High quality)
      Primary format:   MP3
    ------------------------------------------------------------
    Favorite musical decades
      90s (1990-1999): 35 tracks (28.2%)
      00s (2000-2009): 40 tracks (32.3%)
      10s (2010-2019): 49 tracks (39.5%)
    ------------------------------------------------------------
    Your Music Wrapped
      Top artist:   Radiohead (15 tracks)
      Top genre:    Alternative (28 tracks)
      Top decade:   10s (2010-2019, 49 tracks)
      Top year:     2017 (12 tracks)
      Longest track:  Pink Floyd – Echoes (23:31)
      Shortest track: Daft Punk – Nightvision (01:12)
      Missing genre tags: 3
      Missing year tags:  2

The overview report includes:

- Total number of tracks, albums, artists, and genres
- Range of years present in the library
- Total listening time and average track length
- Average bitrate and primary file format
- Distribution of tracks by decade
- Most common artist, genre, decade, and year
- Longest and shortest tracks
- Counts of tracks missing genre or year metadata

The ``--overview`` flag is mutually exclusive with ``--exact`` and always uses
estimated sizes and durations derived from metadata.
