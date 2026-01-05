# This file is part of beets.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""Report plugin for Beets: generate statistical summaries of your music library."""

import datetime
from collections import Counter

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, print_


class ReportPlugin(BeetsPlugin):
    """A Beets plugin that generates a library report with statistics and Wrapped-style insights."""

    def commands(self):
        report_cmd = Subcommand(
            "report",
            help="Generate a statistical report of your music library.",
        )
        report_cmd.func = self._run_report
        return [report_cmd]

    def _run_report(self, lib, opts, args):
        """Collect statistics and print a report about the library."""
        items = list(lib.items())
        total_tracks = len(items)

        if total_tracks == 0:
            print_("Your Beets library is empty.")
            return

        # --- Collect metadata ---
        artists = [i.artist for i in items if i.artist]
        albums = [i.album for i in items if i.album]
        genres = [i.genre for i in items if i.genre]
        years = [
            i.year for i in items if isinstance(i.year, int) and i.year > 0
        ]
        formats = [i.format for i in items if i.format]
        lengths = [i.length for i in items if i.length]
        bitrates = [i.bitrate for i in items if i.bitrate]

        # --- Counters ---
        artist_counter = Counter(artists)
        genre_counter = Counter(genres)
        format_counter = Counter(formats)
        year_counter = Counter(years)

        # --- Time calculations ---
        total_length = sum(lengths) if lengths else 0
        avg_length = total_length / len(lengths) if lengths else 0

        def fmt_time(seconds):
            return str(datetime.timedelta(seconds=int(seconds)))

        # --- Decades ---
        current_year = datetime.datetime.now().year
        decades = [(y // 10) * 10 for y in years if 1900 <= y <= current_year]
        decade_counter = Counter(decades)

        def decade_label(d):
            return f"{str(d)[-2:]}s"

        # --- Wrapped insights ---
        top_artist = artist_counter.most_common(1)
        top_genre = genre_counter.most_common(1)
        top_decade = decade_counter.most_common(1)
        top_year = year_counter.most_common(1)

        longest_track = max(items, key=lambda i: i.length or 0)
        shortest_track = min(
            (i for i in items if i.length), key=lambda i: i.length, default=None
        )

        missing_genre = sum(1 for i in items if not i.genre)
        missing_year = sum(
            1 for i in items if not isinstance(i.year, int) or i.year <= 0
        )

        recent_tracks = sum(1 for y in years if y >= 2015)
        older_tracks = len(years) - recent_tracks

        avg_bitrate = sum(bitrates) // len(bitrates) if bitrates else None
        quality = (
            "Hi-Fi"
            if avg_bitrate and avg_bitrate >= 900
            else "High quality"
            if avg_bitrate and avg_bitrate >= 320
            else "Standard quality"
        )

        # ===================== REPORT =====================
        print_("Beets Library Report")
        print_(f"Generated: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
        print_("=" * 60)

        # --- Overview ---
        print_("Overview")
        print_(f"  Tracks:   {total_tracks}")
        print_(f"  Albums:   {len(set(albums))}")
        print_(f"  Artists:  {len(set(artists))}")
        print_(f"  Genres:   {len(set(genres))}")
        print_(
            f"  Years:    {min(years)} – {max(years)}"
            if years
            else "  Years:    n/a"
        )
        print_("-" * 60)

        # --- Duration & quality ---
        print_("Listening time & quality")
        print_(f"  Total playtime:   {fmt_time(total_length)}")
        print_(f"  Avg track length: {fmt_time(avg_length)}")
        if avg_bitrate:
            print_(f"  Avg bitrate:      {avg_bitrate} kbps ({quality})")
            if format_counter:
                print_(
                    f"  Primary format:   {format_counter.most_common(1)[0][0]}"
                )
        print_("-" * 60)

        # --- Decade distribution ---
        print_("Favorite musical decades")
        if decade_counter:
            total_decade_tracks = sum(decade_counter.values())
            for d, c in decade_counter.most_common():
                pct = (c / total_decade_tracks) * 100
                print_(
                    f"  {decade_label(d):>4} ({d}-{d + 9}): {c:>5} tracks ({pct:4.1f}%)"
                )
        else:
            print_("  n/a")
        print_("-" * 60)

        # --- Wrapped summary ---
        print_("Your Music Wrapped")
        if top_artist:
            print_(
                f"  Top artist:   {top_artist[0][0]} ({top_artist[0][1]} tracks)"
            )
        if top_genre:
            print_(
                f"  Top genre:    {top_genre[0][0]} ({top_genre[0][1]} tracks)"
            )
        if top_decade:
            d, c = top_decade[0]
            print_(
                f"  Top decade:   {decade_label(d)} ({d}-{d + 9}, {c} tracks)"
            )
        if top_year:
            y, c = top_year[0]
            print_(f"  Top year:     {y} ({c} tracks)")

        print_(
            f"  Longest track:  {longest_track.artist} – {longest_track.title} ({fmt_time(longest_track.length)})"
        )
        if shortest_track:
            print_(
                f"  Shortest track: {shortest_track.artist} – {shortest_track.title} ({fmt_time(shortest_track.length)})"
            )

        print_(f"  New music (2015+): {recent_tracks}")
        print_(f"  Older music:       {older_tracks}")

        print_(f"  Missing genre tags: {missing_genre}")
        print_(f"  Missing year tags:  {missing_year}")

        print_("\nReport complete.")
