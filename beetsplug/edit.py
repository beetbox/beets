"""Open metadata information in a text editor to let the user edit it."""

from __future__ import annotations

import codecs
import os
import shlex
import subprocess
from collections import Counter
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Any, cast

import yaml

from beets import plugins, ui, util
from beets.dbcore import types
from beets.exceptions import UserError
from beets.importer import Action
from beets.library import Album, Item
from beets.ui.commands.utils import do_query
from beets.util import PromptChoice

if TYPE_CHECKING:
    from beets.importer import ImportSession, ImportTask

# These "safe" types can avoid the format/parse cycle that most fields go
# through: they are safe to edit with native YAML types.
SAFE_TYPES = (
    types.BaseFloat,
    types.BaseInteger,
    types.Boolean,
    types.DelimitedString,
)

# Fixed fields that only exist on Item, not Album (e.g. title, track, path).
# Flexible attributes are deliberately excluded from this set: they aren't
# part of either model's fixed schema, so they can't be told apart by name
# alone and are left for the user to configure correctly.
ITEM_ONLY_FIELDS = Item._field_names - Album._field_names


class ParseError(Exception):
    """The modified file is unreadable. The user should be offered a chance to
    fix the error.
    """


def edit(filename, log):
    """Open `filename` in a text editor."""
    cmd = shlex.split(util.editor_command())
    cmd.append(filename)
    log.debug("invoking editor command: {!r}", cmd)
    try:
        subprocess.call(cmd)
    except OSError as exc:
        raise UserError(f"could not run editor command {cmd[0]!r}: {exc}")


def dump(arg):
    """Dump a sequence of dictionaries as YAML for editing."""
    return yaml.safe_dump_all(arg, allow_unicode=True, default_flow_style=False)


def load(s):
    """Read a sequence of YAML documents back to a list of dictionaries
    with string keys.

    Can raise a `ParseError`.
    """
    try:
        out = []
        for d in yaml.safe_load_all(s):
            if not isinstance(d, dict):
                raise ParseError(
                    f"each entry must be a dictionary; found {type(d).__name__}"
                )

            # Convert all keys to strings. They started out as strings,
            # but the user may have inadvertently messed this up.
            out.append({str(k): v for k, v in d.items()})

    except yaml.YAMLError as e:
        raise ParseError(f"invalid YAML: {e}")
    return out


def _safe_value(obj, key, value):
    """Check whether the `value` is safe to represent in YAML and trust as
    returned from parsed YAML.

    This ensures that values do not change their type when the user edits their
    YAML representation.
    """
    typ = obj._type(key)
    return isinstance(typ, SAFE_TYPES) and isinstance(value, typ.model_type)


def flatten(obj, fields):
    """Represent `obj`, a `dbcore.Model` object, as a dictionary for
    serialization. Only include the given `fields` if provided;
    otherwise, include everything.

    The resulting dictionary's keys are strings and the values are
    safely YAML-serializable types.
    """
    # Format each value.
    d = {}
    for key in obj.keys():
        value = obj[key]
        if value is None:
            d[key] = None
        elif _safe_value(obj, key, value):
            # A safe value that is faithfully representable in YAML.
            d[key] = value
        else:
            # A value that should be edited as a string.
            d[key] = obj.formatted()[key]

    # Possibly filter field names.
    if fields:
        return {k: v for k, v in d.items() if k in fields}
    return d


def apply_(obj, data):
    """Set the fields of a `dbcore.Model` object according to a
    dictionary.

    This is the opposite of `flatten`. The `data` dictionary should have
    strings as values.
    """
    for key, value in data.items():
        if value is None:
            obj[key] = None
        elif _safe_value(obj, key, value):
            # A safe value *stayed* represented as a safe type. Assign it
            # directly.
            obj[key] = value
        else:
            # Either the field was stringified originally or the user changed
            # it from a safe type to an unsafe one. Parse it as a string.
            obj.set_parse(key, str(value))


class EditPlugin(plugins.BeetsPlugin):
    def __init__(self):
        super().__init__()

        self.config.add(
            {
                # The default fields to edit.
                "albumfields": "album albumartist",
                "itemfields": "track title artist album",
                # Silently ignore any changes to these fields.
                "ignore_fields": "id path",
            }
        )

        self.register_listener(
            "before_choose_candidate", self.before_choose_candidate_listener
        )

    def commands(self):
        edit_command = ui.Subcommand("edit", help="interactively edit metadata")
        edit_command.parser.add_option(
            "-f",
            "--field",
            metavar="FIELD",
            action="append",
            help="edit this field also",
        )
        edit_command.parser.add_option(
            "--all", action="store_true", dest="all", help="edit all fields"
        )
        edit_command.parser.add_album_option()
        edit_command.func = self._edit_command
        return [edit_command]

    def _edit_command(self, lib, opts, args):
        """The CLI command function for the `beet edit` command."""
        # Get the objects to edit.
        items, albums = do_query(lib, args, opts.album, False)
        objs = albums if opts.album else items
        if not objs:
            ui.print_("Nothing to edit.")
            return

        # Get the fields to edit.
        if opts.all:
            fields = None
        else:
            fields = self._get_fields(opts.album, opts.field)
        self.edit(opts.album, objs, fields)

    def _get_fields(self, album, extra):
        """Get the set of fields to edit."""
        # Start with the configured base fields.
        if album:
            fields = self.config["albumfields"].as_str_seq()
        else:
            fields = self.config["itemfields"].as_str_seq()

        # Add the requested extra fields.
        if extra:
            fields += extra

        # Ensure we always have the `id` field for identification.
        fields.append("id")

        return set(fields)

    def edit(self, album, objs, fields):
        """The core editor function.

        - `album`: A flag indicating whether we're editing Items or Albums.
        - `objs`: The `Item`s or `Album`s to edit.
        - `fields`: The set of field names to edit (or None to edit
          everything).
        """
        # Present the YAML to the user and let them change it.
        success = self.edit_objects(objs, fields)

        # Save the new data.
        if success:
            self.save_changes(objs)

    def edit_objects(self, objs, fields):
        """Dump a set of Model objects to a file as text, ask the user
        to edit it, and apply any changes to the objects.

        Return a boolean indicating whether the edit succeeded.
        """
        # Get the content to edit as raw data structures.
        old_data = [flatten(o, fields) for o in objs]
        cur_str = dump(old_data)

        # Loop until we have parseable data and the user confirms.
        while True:
            result = self._edit_yaml(cur_str)
            if result is None:
                return False
            new_data, new_str = result

            # Show the changes.
            # If the objects are not on the DB yet, we need a copy of their
            # original state for show_model_changes.
            objs_old = [obj.copy() if obj.id < 0 else None for obj in objs]
            self.apply_data(objs, old_data, new_data)
            changed = False
            for obj, obj_old in zip(objs, objs_old):
                changed |= ui.show_model_changes(obj, obj_old)
            if not changed:
                ui.print_("No changes to apply.")
                return False

            # For cancel/keep-editing, restore objects to their original
            # in-memory state so temp edits don't leak into the session
            choice = ui.input_options(("continue Editing", "apply", "cancel"))
            if choice == "a":  # Apply.
                return True
            if choice == "c":  # Cancel.
                self.apply_data(objs, new_data, old_data)
                return False
            if choice == "e":  # Keep editing.
                self.apply_data(objs, new_data, old_data)
                cur_str = new_str
                continue

    def apply_data(self, objs, old_data, new_data):
        """Take potentially-updated data and apply it to a set of Model
        objects.

        Documents are matched to objects by their ``id`` field rather than
        by position, so a reordered or otherwise misaligned document list
        cannot cause one object's data to be applied to a different object.

        The objects are not written back to the database, so the changes
        are temporary.
        """
        if len(old_data) != len(new_data):
            self._log.warning(
                "number of objects changed from {} to {}",
                len(old_data),
                len(new_data),
            )

        obj_by_id = {o.id: o for o in objs}
        old_by_id = {d.get("id"): d for d in old_data}
        new_id_counts = Counter(d.get("id") for d in new_data)
        ignore_fields = self.config["ignore_fields"].as_str_seq()
        for new_dict in new_data:
            new_id = new_dict.get("id")
            if new_id_counts[new_id] > 1:
                # Two or more documents claim the same id: either a document's
                # id was edited to collide with another one, or the same
                # document was duplicated. We can't tell which document is
                # the "real" one, so ignore all of them.
                self._log.warning(
                    "ignoring objects with duplicate id {}", new_id
                )
                continue

            old_dict = old_by_id.get(new_id)
            obj = obj_by_id.get(new_id)
            if old_dict is None or obj is None:
                self._log.warning("ignoring object whose id changed")
                continue

            # Prohibit any changes to forbidden fields to avoid
            # clobbering `id` and such by mistake.
            forbidden = False
            for key in ignore_fields:
                if old_dict.get(key) != new_dict.get(key):
                    self._log.warning("ignoring object whose {} changed", key)
                    forbidden = True
                    break
            if forbidden:
                continue

            apply_(obj, new_dict)

    def save_changes(self, objs):
        """Save a list of updated Model objects to the database."""
        # Save to the database and possibly write tags.
        for ob in objs:
            if ob._dirty:
                self._log.debug("saving changes to {}", ob)
                ob.try_sync(ui.should_write(), ui.should_move())

    # Methods for interactive importer execution.

    def before_choose_candidate_listener(self, session, task):
        """Append an "Edit" choice and an "edit Candidates" choice (if
        there are candidates) to the interactive importer prompt.
        """
        choices = [PromptChoice("d", "eDit", self.importer_edit)]
        if task.candidates:
            choices.append(
                PromptChoice(
                    "c", "edit Candidates", self.importer_edit_candidate
                )
            )

        return choices

    def _importer_edit_album_header(
        self, task: ImportTask
    ) -> dict[str, Any] | None:
        """Build the album-header YAML document for import editing.

        Returns a dict of album-level fields, or ``None`` when the current
        task is not an album import.
        """
        if not getattr(task, "is_album", False) or not task.items:
            return None

        album_fields = set(self.config["albumfields"].as_str_seq())
        if not album_fields:
            return None

        # Drop fields that only exist on Item (title, track, path, ...);
        # since the header is built from a single item and then applied to
        # every item, an item-only field here would silently stamp that
        # one item's value onto the whole album. Flexible fields are left
        # alone so they can still be edited at the album level.
        item_only_fields = album_fields & ITEM_ONLY_FIELDS
        if item_only_fields:
            self._log.warning(
                "ignoring item-only fields configured in albumfields: {}",
                ", ".join(sorted(item_only_fields)),
            )
            album_fields -= ITEM_ONLY_FIELDS
        if not album_fields:
            return None

        first_item = task.items[0]
        header = flatten(first_item, album_fields)
        return header if header else None

    def _importer_edit_apply_header(
        self, items: list[Item], header_data: dict[str, Any]
    ) -> None:
        """Apply album-header changes to every item in the list."""
        if not header_data:
            return
        for item in items:
            apply_(item, header_data)

    def _edit_yaml(
        self, old_str: str
    ) -> tuple[list[dict[str, Any]], str] | None:
        """Open a temporary file with `old_str`, let the user edit it, and
        return the parsed list of YAML documents.

        Returns ``(parsed_data, edited_str)`` on success, or ``None`` if the
        user aborted (no changes or unresolvable parse error).
        """
        with NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as new:
            new.write(old_str)

        try:
            while True:
                edit(new.name, self._log)

                with codecs.open(new.name, encoding="utf-8") as f:
                    new_str = f.read()
                if new_str == old_str:
                    ui.print_("No changes; aborting.")
                    return None

                try:
                    return load(new_str), new_str
                except ParseError as e:
                    ui.print_(f"Could not read data: {e}")
                    if not ui.input_yn("Edit again to fix? (Y/n)", True):
                        return None
        finally:
            os.remove(new.name)

    def importer_edit(
        self, session: ImportSession, task: ImportTask
    ) -> Action | None:
        """Callback for invoking the functionality during an interactive
        import session on the *original* item tags.
        """
        # Assign negative temporary ids to Items that are not in the database
        # yet. By using negative values, no clash with items in the database
        # can occur.
        for i, obj in enumerate(task.items, start=1):
            # The importer may set the id to None when re-importing albums.
            if not obj._db or obj.id is None:
                obj.id = -i

        # Decide which fields to show.
        album_fields = set()
        if getattr(task, "is_album", False):
            album_fields = set(self.config["albumfields"].as_str_seq())
        item_fields = set(self.config["itemfields"].as_str_seq())

        # Track-level fields exclude any that are shown in the album header
        # to avoid duplication.
        track_fields = item_fields - album_fields
        track_fields.add("id")

        # Build the YAML document list.
        header_data = self._importer_edit_album_header(task)
        old_track_data = [flatten(o, track_fields) for o in task.items]
        all_old_data = []
        if header_data is not None:
            all_old_data.append(header_data)
        all_old_data.extend(old_track_data)
        has_header = header_data is not None
        num_data_docs = 1 if has_header else 0

        cur_str = dump(all_old_data)

        while True:
            result = self._edit_yaml(cur_str)
            if result is None:
                self._importer_edit_cleanup(task)
                return None
            new_all_data, new_str = result

            expected_total = num_data_docs + len(task.items)
            if len(new_all_data) != expected_total:
                ui.print_(
                    f"Number of documents changed from {expected_total} to "
                    f"{len(new_all_data)}."
                )
                if ui.input_yn("Edit again to fix? (Y/n)", True):
                    continue
                self._importer_edit_cleanup(task)
                return None

            # Split into album header and per-track documents. Every track
            # document always has an `id` field (see `track_fields` above),
            # while the header never does, so identify the header by the
            # absence of `id` rather than by position. This keeps the split
            # correct even if the user moves the header elsewhere in the
            # file, since `apply_data` already matches track documents by
            # id regardless of order.
            if has_header:
                new_header_data = [d for d in new_all_data if "id" not in d]
                new_track_data = [d for d in new_all_data if "id" in d]
                if len(new_header_data) != 1:
                    ui.print_(
                        "Could not identify the album header: exactly one "
                        "document must have no `id` field."
                    )
                    if ui.input_yn("Edit again to fix? (Y/n)", True):
                        continue
                    self._importer_edit_cleanup(task)
                    return None
            else:
                new_header_data = []
                new_track_data = new_all_data

            # Snapshot originals for diff display and restore.
            objs_old = cast("list[Item]", [obj.copy() for obj in task.items])

            # Apply header changes to every item.
            if new_header_data:
                self._importer_edit_apply_header(task.items, new_header_data[0])

            # Apply per-track changes.
            self.apply_data(task.items, old_track_data, new_track_data)

            # Show the diff.
            changed = False
            for item, old_copy in zip(task.items, objs_old):
                changed |= ui.show_model_changes(item, old_copy)

            if not changed:
                ui.print_("No changes to apply.")
                self._importer_edit_cleanup(task)
                return None

            choice = ui.input_options(("continue Editing", "apply", "cancel"))
            if choice == "a":  # Apply.
                self._importer_edit_cleanup(task)
                return Action.RETAG
            if choice == "c":  # Cancel.
                self._importer_edit_restore_from_copies(task, objs_old)
                self._importer_edit_cleanup(task)
                return None
            if choice == "e":  # Keep editing.
                self._importer_edit_restore_from_copies(task, objs_old)
                cur_str = new_str
                continue

    @staticmethod
    def _importer_edit_cleanup(task: ImportTask) -> None:
        """Remove temporary negative ids from task items."""
        for obj in task.items:
            if obj.id is not None and obj.id < 0:
                obj.id = None

    @staticmethod
    def _importer_edit_restore_from_copies(
        task: ImportTask, copies: list[Item]
    ) -> None:
        """Restore items to their state before the last edit cycle.

        ``copies`` must be a list of :class:`Item <beets.library.Item>` copies
        taken *before* the changes were applied.
        """
        for i, item in enumerate(task.items):
            if i < len(copies):
                for key in item._fields:
                    item[key] = copies[i][key]

    def importer_edit_candidate(self, session, task):
        """Callback for invoking the functionality during an interactive
        import session on a *candidate*. The candidate's metadata is
        applied to the original items.
        """
        # Prompt the user for a candidate.
        sel = ui.input_options([], numrange=(1, len(task.candidates)))
        # Force applying the candidate on the items.
        task.match = task.candidates[sel - 1]
        task.apply_metadata()

        return self.importer_edit(session, task)
