"""The 'stats' command: show library statistics."""

import datetime
import os
from collections import Counter

from beets import logging, ui
from beets.util import syspath
from beets.util.units import human_bytes, human_seconds

# Global logger.
log = logging.getLogger("beets")


def show_stats(lib, query, exact):
    """Shows some statistics about the matched items."""
    items = lib.items(query)

    total_size = 0
    total_time = 0.0
    total_items = 0
    artists = set()
    albums = set()
    album_artists = set()

    for item in items:
        if exact:
            try:
                total_size += os.path.getsize(syspath(item.path))
            except OSError as exc:
                log.info("could not get size of {.path}: {}", item, exc)
        else:
            total_size += int(item.length * item.bitrate / 8)
        total_time += item.length
        total_items += 1
        artists.add(item.artist)
        album_artists.add(item.albumartist)
        if item.album_id:
            albums.add(item.album_id)

    size_str = human_bytes(total_size)
    if exact:
        size_str += f" ({total_size} bytes)"

    ui.print_(f"""Tracks: {total_items}
Total time: {human_seconds(total_time)}
{f" ({total_time:.2f} seconds)" if exact else ""}
{"Total size" if exact else "Approximate total size"}: {size_str}
Artists: {len(artists)}
Albums: {len(albums)}
Album artists: {len(album_artists)}""")


def show_overview_report(lib, query):
    """Show overview-style library report."""
    items = list(lib.items(query))

    if not items:
        ui.print_("Your Beets library is empty.")
        return

    # Collect statistics in a single pass
    artists = Counter()
    albums = set()
    genres = Counter()
    years = Counter()
    formats = Counter()
    lengths = []
    bitrates = []
    items_with_length = []

    for item in items:
        if item.artist:
            artists[item.artist] += 1
        if item.album:
            albums.add(item.album)
        if item.genre:
            genres[item.genre] += 1
        if isinstance(item.year, int) and item.year > 0:
            years[item.year] += 1
        if item.format:
            formats[item.format] += 1
        if item.length:
            lengths.append(item.length)
            items_with_length.append(item)
        if item.bitrate:
            bitrates.append(item.bitrate)

    # Helper functions
    def fmt_time(seconds):
        return str(datetime.timedelta(seconds=int(seconds)))

    def decade_label(d):
        return f"{str(d)[-2:]}s"

    # Calculate averages
    total_length = sum(lengths) if lengths else 0
    avg_length = sum(lengths) / len(lengths) if lengths else 0
    avg_bitrate = sum(bitrates) // len(bitrates) if bitrates else None

    # Determine quality label
    if avg_bitrate:
        if avg_bitrate >= 900:
            quality = "Hi-Fi"
        elif avg_bitrate >= 320:
            quality = "High quality"
        else:
            quality = "Standard quality"
    else:
        quality = None

    # Calculate decades
    current_year = datetime.datetime.now().year
    decades = [
        (y // 10) * 10 for y in years.keys() if 1900 <= y <= current_year
    ]
    decade_counter = Counter(decades)

    # Get top items
    top_artist = artists.most_common(1)
    top_genre = genres.most_common(1)
    top_decade = decade_counter.most_common(1)
    top_year = years.most_common(1)

    # Longest/shortest tracks
    longest_track = (
        max(items_with_length, key=lambda i: i.length)
        if items_with_length
        else None
    )
    shortest_track = (
        min(items_with_length, key=lambda i: i.length)
        if items_with_length
        else None
    )

    # Missing metadata
    missing_genre = sum(1 for i in items if not i.genre)
    missing_year = sum(
        1 for i in items if not isinstance(i.year, int) or i.year <= 0
    )

    # ===================== REPORT =====================
    ui.print_("Beets Library Report")
    ui.print_(f"Generated: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    ui.print_("=" * 60)

    # --- Overview ---
    ui.print_("Overview")
    ui.print_(f"  Tracks:   {len(items)}")
    ui.print_(f"  Albums:   {len(albums)}")
    ui.print_(f"  Artists:  {len(artists)}")
    ui.print_(f"  Genres:   {len(genres)}")
    if years:
        ui.print_(f"  Years:    {min(years)} – {max(years)}")
    else:
        ui.print_("  Years:    n/a")
    ui.print_("-" * 60)

    # --- Duration & quality ---
    ui.print_("Listening time & quality")
    ui.print_(f"  Total playtime:   {fmt_time(total_length)}")
    ui.print_(f"  Avg track length: {fmt_time(avg_length)}")
    if avg_bitrate is not None:
        ui.print_(f"  Avg bitrate:      {avg_bitrate} kbps ({quality})")
        if formats:
            ui.print_(f"  Primary format:   {formats.most_common(1)[0][0]}")
    ui.print_("-" * 60)

    # --- Decade distribution ---
    ui.print_("Favorite musical decades")
    if decade_counter:
        total_decade_tracks = sum(decade_counter.values())
        for d, c in decade_counter.most_common():
            pct = (c / total_decade_tracks) * 100
            ui.print_(
                f"  {decade_label(d):>4} ({d}-{d + 9}): "
                f"{c:>5} tracks ({pct:4.1f}%)"
            )
    else:
        ui.print_("  n/a")
    ui.print_("-" * 60)

    # --- Wrapped summary ---
    ui.print_("Your Music Wrapped")
    if top_artist:
        ui.print_(
            f"  Top artist:   {top_artist[0][0]} ({top_artist[0][1]} tracks)"
        )
    if top_genre:
        ui.print_(
            f"  Top genre:    {top_genre[0][0]} ({top_genre[0][1]} tracks)"
        )
    if top_decade:
        d, c = top_decade[0]
        ui.print_(
            f"  Top decade:   {decade_label(d)} ({d}-{d + 9}, {c} tracks)"
        )
    if top_year:
        y, c = top_year[0]
        ui.print_(f"  Top year:     {y} ({c} tracks)")

    if longest_track:
        ui.print_(
            f"  Longest track:  {longest_track.artist} – "
            f"{longest_track.title} ({fmt_time(longest_track.length)})"
        )
    if shortest_track:
        ui.print_(
            f"  Shortest track: {shortest_track.artist} – "
            f"{shortest_track.title} ({fmt_time(shortest_track.length)})"
        )

    ui.print_(f"  Missing genre tags: {missing_genre}")
    ui.print_(f"  Missing year tags:  {missing_year}")


def stats_func(lib, opts, args):
    if opts.overview:
        show_overview_report(lib, args)
    else:
        show_stats(lib, args, opts.exact)


stats_cmd = ui.Subcommand(
    "stats", help="show statistics about the library or a query"
)
stats_cmd.parser.add_option(
    "-e", "--exact", action="store_true", help="exact size and time"
)
stats_cmd.parser.add_option(
    "-o",
    "--overview",
    action="store_true",
    help="show overview-style comprehensive library report",
)
stats_cmd.func = stats_func
