"""The 'list' command: query and show library contents."""

from beets.ui.core import Subcommand, print_


def list_items(lib, query, album, fmt=""):
    """Print out items in lib matching query. If album, then search for
    albums instead of single items.
    """
    if album:
        for album in lib.albums(query):
            print_(format(album, fmt))
    else:
        for item in lib.items(query):
            print_(format(item, fmt))


def list_func(lib, opts, args):
    list_items(lib, args, opts.album)


list_cmd = Subcommand("list", help="query the library", aliases=("ls",))
list_cmd.parser.usage += "\nExample: %prog -f '$album: $title' artist:beatles"
list_cmd.parser.add_all_common_options()
list_cmd.func = list_func
