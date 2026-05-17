"""The `modify` command: change metadata fields."""

from dataclasses import dataclass

from beets import library, ui
from beets.dbcore import types
from beets.exceptions import UserError
from beets.util import functemplate
from beets.util.deprecation import maybe_replace_legacy_field

from .utils import do_query


@dataclass(frozen=True)
class ModifyOperation:
    operator: str
    value: str


def _is_multi_value_field(model_cls, field):
    return isinstance(model_cls._type(field), types.DelimitedString)


def _check_modify_operations(model_cls, mods):
    for field, mod in mods.items():
        if isinstance(mod, ModifyOperation) and not _is_multi_value_field(
            model_cls, field
        ):
            raise UserError(
                f"field {field!r} does not support the {mod.operator}= operator"
            )


def _apply_modify_operation(obj, field, mod, value):
    current = list(obj[field])

    if mod.operator == "+":
        for item in value:
            if item not in current:
                current.append(item)
        return current

    return [item for item in current if item not in value]


def modify_items(lib, mods, dels, query, write, move, album, confirm, inherit):
    """Modifies matching items according to user-specified assignments and
    deletions.

    `mods` is a dictionary of field and value pairse indicating
    assignments. `dels` is a list of fields to be deleted.
    """
    # Parse key=value specifications into a dictionary.
    model_cls = library.Album if album else library.Item
    _check_modify_operations(model_cls, mods)

    # Get the items to modify.
    items, albums = do_query(lib, query, album, False)
    objs = albums if album else items

    # Apply changes *temporarily*, preview them, and collect modified
    # objects.
    ui.print_(f"Modifying {len(objs)} {'album' if album else 'item'}s.")
    changed = []
    templates = {}
    for key, mod in mods.items():
        value = mod.value if isinstance(mod, ModifyOperation) else mod
        templates[key] = functemplate.template(value)
    for obj in objs:
        obj_mods = {}
        for key, mod in mods.items():
            value = model_cls._parse(key, obj.evaluate_template(templates[key]))
            if isinstance(mod, ModifyOperation):
                value = _apply_modify_operation(obj, key, mod, value)
            obj_mods[key] = value
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


def modify_parse_args(args, is_album: bool):
    """Split the arguments for the modify subcommand into query parts,
    assignments (field=value), and deletions (field!).  Returns the result as
    a three-tuple in that order.

    Replace legacy string fields with list equivalents, and supply deprecation
    warnings for the user.
    """
    mods = {}
    dels = []
    query = []
    for arg in args:
        if arg.endswith("!") and "=" not in arg and ":" not in arg:
            dels.append(arg[:-1])  # Strip trailing !.
        elif "=" in arg and ":" not in arg.split("=", 1)[0]:
            key, val = arg.split("=", 1)
            operator = None
            if key.endswith(("+", "-")):
                key, operator = key[:-1], key[-1]
            key = maybe_replace_legacy_field(key, is_album, modify=True)
            mods[key] = ModifyOperation(operator, val) if operator else val
        else:
            query.append(arg)
    return query, mods, dels


def modify_func(lib, opts, args):
    query, mods, dels = modify_parse_args(args, is_album=opts.album)
    if not mods and not dels:
        raise UserError("no modifications specified")
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
