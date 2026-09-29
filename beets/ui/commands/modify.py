"""The `modify` command: change metadata fields."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, Protocol, TypedDict

from typing_extensions import Unpack

from beets import ui
from beets.dbcore import types
from beets.exceptions import UserError
from beets.library import Album, Item
from beets.util.deprecation import maybe_replace_legacy_field

if TYPE_CHECKING:
    from collections.abc import Sequence

    from beets.library import AlbumOrItem, LibModel, Library


class ModifyCLIOpts(Protocol):
    album: bool
    inherit: bool
    move: bool | None
    write: bool | None
    yes: bool | None


class ModifyOperation(NamedTuple):
    operator: str | None
    value: str

    def apply(
        self, obj: LibModel, field: str, new_values: list[str]
    ) -> list[str]:
        if self.operator is None:
            return new_values

        current = list(obj[field])

        if self.operator == "+":
            return current + [
                item for item in new_values if item not in current
            ]

        return [item for item in current if item not in new_values]


class ModifyParams(TypedDict):
    mods: dict[str, ModifyOperation]
    dels: Sequence[str]
    write: bool
    move: bool
    confirm: bool
    inherit: bool


def _is_multi_value_field(model_cls: type[LibModel], field: str) -> bool:
    return isinstance(model_cls._type(field), types.DelimitedString)


def _check_modify_operations(
    model_cls: type[LibModel], mods: dict[str, ModifyOperation]
) -> None:
    for field, mod in mods.items():
        if mod.operator and not _is_multi_value_field(model_cls, field):
            raise UserError(
                f"field {field!r} does not support the {mod.operator}= operator"
            )


def modify_objects(
    model_cls: type[AlbumOrItem],
    objs: Sequence[AlbumOrItem],
    lib: Library,
    *,
    mods: dict[str, ModifyOperation],
    dels: Sequence[str],
    write: bool,
    move: bool,
    confirm: bool,
    inherit: bool,
) -> None:
    """Modifies albums or items according to user-specified assignments and
    deletions.

    `mods` is a dictionary of field and value pairs indicating
    assignments. `dels` is a list of fields to be deleted.
    """
    # Parse key=value specifications into a dictionary.
    _check_modify_operations(model_cls, mods)

    if not objs:
        raise UserError("No matching objects to modify.")

    # Apply changes *temporarily*, preview them, and collect modified
    # objects.
    ui.print_(f"Modifying {len(objs)} {model_cls.__name__.lower()}s.")
    changed = []
    for obj in objs:
        obj_mods = {
            key: mod.apply(
                obj,
                key,
                model_cls._parse(key, obj.evaluate_template(mod.value)),
            )
            for key, mod in mods.items()
        }
        if print_and_modify(obj, obj_mods, dels) and obj not in changed:
            changed.append(obj)

    # Still something to do?
    if not changed:
        ui.print_("No changes to make.")
        return

    # Confirm action.
    selected_changes: Sequence[AlbumOrItem]
    if confirm:
        if write and move:
            extra = ", move and write tags"
        elif write:
            extra = " and write tags"
        elif move:
            extra = " and move"
        else:
            extra = ""

        selected_changes = ui.input_select_objects(
            f"Really modify{extra}", changed, ui.show_model_changes
        )
    else:
        selected_changes = changed

    # Apply changes to database and files
    with lib.transaction():
        for obj in selected_changes:
            obj.try_sync(write, move, inherit)


def modify_items(
    lib: Library, query: Sequence[str], **kwargs: Unpack[ModifyParams]
) -> None:
    modify_objects(Item, list(lib.items(query)), lib, **kwargs)


def modify_albums(
    lib: Library, query: Sequence[str], **kwargs: Unpack[ModifyParams]
) -> None:
    modify_objects(Album, list(lib.albums(query)), lib, **kwargs)


def print_and_modify(
    obj: LibModel, mods: dict[str, list[str]], dels: Sequence[str]
) -> bool:
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


def modify_parse_args(
    args: Sequence[str], is_album: bool
) -> tuple[list[str], dict[str, ModifyOperation], list[str]]:
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
            mods[key] = ModifyOperation(operator, val)
        else:
            query.append(arg)
    return query, mods, dels


def modify_func(lib: Library, opts: ModifyCLIOpts, args: list[str]) -> None:
    query, mods, dels = modify_parse_args(args, is_album=opts.album)
    if not mods and not dels:
        raise UserError("no modifications specified")
    method = modify_albums if opts.album else modify_items
    method(
        lib,
        query,
        mods=mods,
        dels=dels,
        write=ui.should_write(opts.write),
        move=ui.should_move(opts.move),
        confirm=not opts.yes,
        inherit=opts.inherit,
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
