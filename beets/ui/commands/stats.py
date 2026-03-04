"""The 'stats' command: show library statistics."""

import os

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


def stats_func(lib, opts, args):
    show_stats(lib, args, opts.exact)


stats_cmd = ui.Subcommand(
    "stats", help="show statistics about the library or a query"
)
stats_cmd.parser.add_option(
    "-e", "--exact", action="store_true", help="exact size and time"
)
stats_cmd.func = stats_func
