Report Plugin
=============

The ``report`` plugin provides a command that generates a detailed statistical
summary of your music library. It collects information about tracks, albums,
artists, genres, years, formats, and more, giving you insights similar to a
“Wrapped” summary of your listening habits.

First, enable the plugin named ``report`` (see :ref:`using-plugins`). You'll
then be able to use the ``beet report`` command:

::

    $ beet report
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
      Primary format:   mp3
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
      New music (2015+): 60
      Older music:       64
      Missing genre tags: 3
      Missing year tags:  2

The command takes no additional arguments. It scans your library and prints
statistics such as:

- Total number of tracks, albums, artists, and genres
- Range of years present in the library
- Total listening time and average track length
- Average bitrate and primary file format
- Distribution of tracks by decade
- Most common artist, genre, decade, and year
- Longest and shortest tracks
- Counts of new vs. older music (tracks since 2015)
- Number of tracks missing genre or year tags

This plugin is useful for analyzing your collection, identifying missing
metadata, and discovering trends in your listening habits.
