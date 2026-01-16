"""The `remove` command: remove items from the library (and optionally delete files)."""

from beets import ui

from .utils import do_query


def remove_items(lib, query, album, delete, force):
    """Remove items matching query from lib. If album, then match and
    remove whole albums. If delete, also remove files from disk.
    """
    # Get the matching items.
    items, albums = do_query(lib, query, album)
    objs = albums if album else items

    # Confirm file removal if not forcing removal.
    if not force:
        # Prepare confirmation with user.
        album_str = (
            f" in {len(albums)} album{'s' if len(albums) > 1 else ''}"
            if album
            else ""
        )

        if delete:
            fmt = "$path - $title"
            prompt = "Really DELETE"
            prompt_all = (
                "Really DELETE"
                f" {len(items)} file{'s' if len(items) > 1 else ''}{album_str}"
            )
        else:
            fmt = ""
            prompt = "Really remove from the library?"
            prompt_all = (
                "Really remove"
                f" {len(items)} item{'s' if len(items) > 1 else ''}{album_str}"
                " from the library?"
            )

        # Helpers for printing affected items
        def fmt_track(t):
            ui.print_(format(t, fmt))

        def fmt_album(a):
            ui.print_()
            for i in a.items():
                fmt_track(i)

        fmt_obj = fmt_album if album else fmt_track

        # Show all the items.
        for o in objs:
            fmt_obj(o)

        # Confirm with user.
        objs = ui.input_select_objects(
            prompt, objs, fmt_obj, prompt_all=prompt_all
        )

    if not objs:
        return

    # Remove (and possibly delete) items.
    with lib.transaction():
        for obj in objs:
            obj.remove(delete)


def remove_func(lib, opts, args):
    remove_items(lib, args, opts.album, opts.delete, opts.force)


remove_cmd = ui.Subcommand(
    "remove", help="remove matching items from the library", aliases=("rm",)
)
remove_cmd.parser.add_option(
    "-d", "--delete", action="store_true", help="also remove files from disk"
)
remove_cmd.parser.add_option(
    "-f", "--force", action="store_true", help="do not ask when removing items"
)
remove_cmd.parser.add_album_option()
remove_cmd.func = remove_func
