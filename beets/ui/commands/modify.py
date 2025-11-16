"""The `modify` command: change metadata fields."""

from beets import library, ui
from beets.util import functemplate

from .utils import do_query


def modify_items(lib, mods, dels, query, write, move, album, confirm, inherit):
    """Modifies matching items according to user-specified assignments and
    deletions.

    `mods` is a dictionary of field and value pairse indicating
    assignments. `dels` is a list of fields to be deleted.
    """
    # Parse key=value specifications into a dictionary.
    model_cls = library.Album if album else library.Item

    # Get the items to modify.
    items, albums = do_query(lib, query, album, False)
    objs = albums if album else items

    # Apply changes *temporarily*, preview them, and collect modified
    # objects.
    ui.print_(f"Modifying {len(objs)} {'album' if album else 'item'}s.")
    changed = []
    templates = {
        key: functemplate.template(value) for key, value in mods.items()
    }
    for obj in objs:
        obj_mods = {
            key: model_cls._parse(key, obj.evaluate_template(templates[key]))
            for key in mods.keys()
        }
        if print_and_modify(obj, obj_mods, dels) and obj not in changed:
            changed.append(obj)

    # Still something to do?
    if not changed:
        ui.print_("No changes to make.")
        return

    # Confirm action.
    if confirm:
        if write and move:
            extra = ", move and write tags"
        elif write:
            extra = " and write tags"
        elif move:
            extra = " and move"
        else:
            extra = ""

        changed = ui.input_select_objects(
            f"Really modify{extra}",
            changed,
            lambda o: print_and_modify(o, mods, dels),
        )

    # Apply changes to database and files
    with lib.transaction():
        for obj in changed:
            obj.try_sync(write, move, inherit)


def print_and_modify(obj, mods, dels):
    """Print the modifications to an item and return a bool indicating
    whether any changes were made.

    `mods` is a dictionary of fields and values to update on the object;
    `dels` is a sequence of fields to delete.
    """
    obj.update(mods)
    for field in dels:
        try:
            del obj[field]
        except KeyError:
            pass
    return ui.show_model_changes(obj)


def modify_parse_args(args):
    """Split the arguments for the modify subcommand into query parts,
    assignments (field=value), and deletions (field!).  Returns the result as
    a three-tuple in that order.
    """
    mods = {}
    dels = []
    query = []
    for arg in args:
        if arg.endswith("!") and "=" not in arg and ":" not in arg:
            dels.append(arg[:-1])  # Strip trailing !.
        elif "=" in arg and ":" not in arg.split("=", 1)[0]:
            key, val = arg.split("=", 1)
            mods[key] = val
        else:
            query.append(arg)
    return query, mods, dels


def modify_func(lib, opts, args):
    query, mods, dels = modify_parse_args(args)
    if not mods and not dels:
        raise ui.UserError("no modifications specified")
    modify_items(
        lib,
        mods,
        dels,
        query,
        ui.should_write(opts.write),
        ui.should_move(opts.move),
        opts.album,
        not opts.yes,
        opts.inherit,
    )


modify_cmd = ui.Subcommand(
    "modify", help="change metadata fields", aliases=("mod",)
)
modify_cmd.parser.add_option(
    "-m",
    "--move",
    action="store_true",
    dest="move",
    help="move files in the library directory",
)
modify_cmd.parser.add_option(
    "-M",
    "--nomove",
    action="store_false",
    dest="move",
    help="don't move files in library",
)
modify_cmd.parser.add_option(
    "-w",
    "--write",
    action="store_true",
    default=None,
    help="write new metadata to files' tags (default)",
)
modify_cmd.parser.add_option(
    "-W",
    "--nowrite",
    action="store_false",
    dest="write",
    help="don't write metadata (opposite of -w)",
)
modify_cmd.parser.add_album_option()
modify_cmd.parser.add_format_option(target="item")
modify_cmd.parser.add_option(
    "-y", "--yes", action="store_true", help="skip confirmation"
)
modify_cmd.parser.add_option(
    "-I",
    "--noinherit",
    action="store_false",
    dest="inherit",
    default=True,
    help="when modifying albums, don't also change item data",
)
modify_cmd.func = modify_func
