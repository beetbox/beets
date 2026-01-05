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
    """A Beets plugin that generates a library report with Wrapped-style insights."""

    def commands(self):
        report_cmd = Subcommand(
            "report",
            help="Generate a statistical report of your music library.",
        )
        report_cmd.func = self._run_report
        return [report_cmd]

    def _run_report(self, lib, opts, args):
        """Run the plugin: generate summary and print report."""
        summary = self.generate_summary(lib)
        self.print_report(summary)

    def generate_summary(self, lib):
        """Generate all summary statistics for the library."""
        items = list(lib.items())
        summary = {
            "total_tracks": len(items),
            "artists": Counter(),
            "albums": set(),
            "genres": Counter(),
            "years": Counter(),
            "formats": Counter(),
            "lengths": [],
            "bitrates": [],
            "items": items,
        }

        for i in items:
            if i.artist:
                summary["artists"][i.artist] += 1
            if i.album:
                summary["albums"].add(i.album)
            if i.genre:
                summary["genres"][i.genre] += 1
            if isinstance(i.year, int) and i.year > 0:
                summary["years"][i.year] += 1
            if i.format:
                summary["formats"][i.format] += 1
            if i.length:
                summary["lengths"].append(i.length)
            if i.bitrate:
                summary["bitrates"].append(i.bitrate)

        # Safe longest/shortest track
        tracks_with_length = [i for i in items if i.length]
        summary["longest_track"] = max(
            tracks_with_length, key=lambda i: i.length, default=None
        )
        summary["shortest_track"] = min(
            tracks_with_length, key=lambda i: i.length, default=None
        )

        # Missing metadata
        summary["missing_genre"] = sum(1 for i in items if not i.genre)
        summary["missing_year"] = sum(
            1 for i in items if not isinstance(i.year, int) or i.year <= 0
        )

        # Time and bitrate
        lengths = summary["lengths"]
        summary["total_length"] = sum(lengths) if lengths else 0
        summary["avg_length"] = sum(lengths) / len(lengths) if lengths else 0

        bitrates = summary["bitrates"]
        summary["avg_bitrate"] = (
            sum(bitrates) // len(bitrates) if bitrates else None
        )
        if summary["avg_bitrate"]:
            if summary["avg_bitrate"] >= 900:
                summary["quality"] = "Hi-Fi"
            elif summary["avg_bitrate"] >= 320:
                summary["quality"] = "High quality"
            else:
                summary["quality"] = "Standard quality"
        else:
            summary["quality"] = None

        # Decades
        current_year = datetime.datetime.now().year
        decades = [
            (y // 10) * 10
            for y in summary["years"].keys()
            if 1900 <= y <= current_year
        ]
        summary["decade_counter"] = Counter(decades)

        return summary

    def print_report(self, summary):
        """Print the library report based on precomputed summary statistics."""
        if summary["total_tracks"] == 0:
            print_("Your Beets library is empty.")
            return

        def fmt_time(seconds):
            return str(datetime.timedelta(seconds=int(seconds)))

        def decade_label(d):
            return f"{str(d)[-2:]}s"

        # --- Top items ---
        top_artist = summary["artists"].most_common(1)
        top_genre = summary["genres"].most_common(1)
        top_decade = summary["decade_counter"].most_common(1)
        top_year = summary["years"].most_common(1)

        # ===================== REPORT =====================
        print_("Beets Library Report")
        print_(f"Generated: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
        print_("=" * 60)

        # --- Overview ---
        print_("Overview")
        print_(f"  Tracks:   {summary['total_tracks']}")
        print_(f"  Albums:   {len(summary['albums'])}")
        print_(f"  Artists:  {len(summary['artists'])}")
        print_(f"  Genres:   {len(summary['genres'])}")
        years = list(summary["years"].keys())
        if years:
            print_(f"  Years:    {min(years)} – {max(years)}")
        else:
            print_("  Years:    n/a")
        print_("-" * 60)

        # --- Duration & quality ---
        print_("Listening time & quality")
        print_(f"  Total playtime:   {fmt_time(summary['total_length'])}")
        print_(f"  Avg track length: {fmt_time(summary['avg_length'])}")
        if summary["avg_bitrate"] is not None:
            print_(
                f"  Avg bitrate:      {summary['avg_bitrate']} kbps "
                f"({summary['quality']})"
            )
            if summary["formats"]:
                print_(
                    f"  Primary format:   "
                    f"{summary['formats'].most_common(1)[0][0]}"
                )
        print_("-" * 60)

        # --- Decade distribution ---
        print_("Favorite musical decades")
        if summary["decade_counter"]:
            total_decade_tracks = sum(summary["decade_counter"].values())
            for d, c in summary["decade_counter"].most_common():
                pct = (c / total_decade_tracks) * 100
                print_(
                    f"  {decade_label(d):>4} ({d}-{d + 9}): "
                    f"{c:>5} tracks ({pct:4.1f}%)"
                )
        else:
            print_("  n/a")
        print_("-" * 60)

        # --- Wrapped summary ---
        print_("Your Music Wrapped")
        if top_artist:
            print_(
                f"  Top artist:   {top_artist[0][0]} "
                f"({top_artist[0][1]} tracks)"
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

        if summary["longest_track"]:
            lt = summary["longest_track"]
            print_(
                f"  Longest track:  {lt.artist} – {lt.title} "
                f"({fmt_time(lt.length)})"
            )
        if summary["shortest_track"]:
            st = summary["shortest_track"]
            print_(
                f"  Shortest track: {st.artist} – {st.title} "
                f"({fmt_time(st.length)})"
            )

        recent_tracks = sum(1 for y in summary["years"].keys() if y >= 2015)
        older_tracks = len(summary["years"]) - recent_tracks
        print_(f"  New music (2015+): {recent_tracks}")
        print_(f"  Older music:       {older_tracks}")

        print_(f"  Missing genre tags: {summary['missing_genre']}")
        print_(f"  Missing year tags:  {summary['missing_year']}")
