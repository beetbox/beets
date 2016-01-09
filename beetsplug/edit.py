# This file is part of beets.
# Copyright 2016
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

"""Open metadata information in a text editor to let the user edit it.
"""
from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from beets import plugins
from beets import util
from beets import ui
from beets.dbcore import types
from beets.ui.commands import _do_query
import subprocess
import yaml
from tempfile import NamedTemporaryFile
import os


# These "safe" types can avoid the format/parse cycle that most fields go
# through: they are safe to edit with native YAML types.
SAFE_TYPES = (types.Float, types.Integer, types.Boolean)


class ParseError(Exception):
    """The modified file is unreadable. The user should be offered a chance to
    fix the error.
    """


def edit(filename):
    """Open `filename` in a text editor.
    """
    cmd = util.shlex_split(util.editor_command())
    cmd.append(filename)
    subprocess.call(cmd)


def dump(arg):
    """Dump a sequence of dictionaries as YAML for editing.
    """
    return yaml.safe_dump_all(
        arg,
        allow_unicode=True,
        default_flow_style=False,
    )


def load(s):
    """Read a sequence of YAML documents back to a list of dictionaries
    with string keys.

    Can raise a `ParseError`.
    """
    try:
        out = []
        for d in yaml.load_all(s):
            if not isinstance(d, dict):
                raise ParseError(
                    'each entry must be a dictionary; found {}'.format(
                        type(d).__name__
                    )
                )

            # Convert all keys to strings. They started out as strings,
            # but the user may have inadvertently messed this up.
            out.append({unicode(k): v for k, v in d.items()})

    except yaml.YAMLError as e:
        raise ParseError('invalid YAML: {}'.format(e))
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
        if _safe_value(obj, key, value):
            # A safe value that is faithfully representable in YAML.
            d[key] = value
        else:
            # A value that should be edited as a string.
            d[key] = obj.formatted()[key]

    # Possibly filter field names.
    if fields:
        return {k: v for k, v in d.items() if k in fields}
    else:
        return d


def apply(obj, data):
    """Set the fields of a `dbcore.Model` object according to a
    dictionary.

    This is the opposite of `flatten`. The `data` dictionary should have
    strings as values.
    """
    for key, value in data.items():
        if _safe_value(obj, key, value):
            # A safe value *stayed* represented as a safe type. Assign it
            # directly.
            obj[key] = value
        else:
            # Either the field was stringified originally or the user changed
            # it from a safe type to an unsafe one. Parse it as a string.
            obj.set_parse(key, unicode(value))


class EditPlugin(plugins.BeetsPlugin):

    def __init__(self):
        super(EditPlugin, self).__init__()

        self.config.add({
            # The default fields to edit.
            'albumfields': 'album albumartist',
            'itemfields': 'track title artist album',

            # Silently ignore any changes to these fields.
            'ignore_fields': 'id path',
        })

    def commands(self):
        edit_command = ui.Subcommand(
            'edit',
            help='interactively edit metadata'
        )
        edit_command.parser.add_option(
            '-f', '--field',
            metavar='FIELD',
            action='append',
            help='edit this field also',
        )
        edit_command.parser.add_option(
            '--all',
            action='store_true', dest='all',
            help='edit all fields',
        )
        edit_command.parser.add_album_option()
        edit_command.func = self._edit_command
        return [edit_command]

    def _edit_command(self, lib, opts, args):
        """The CLI command function for the `beet edit` command.
        """
        # Get the objects to edit.
        query = ui.decargs(args)
        items, albums = _do_query(lib, query, opts.album, False)
        objs = albums if opts.album else items
        if not objs:
            ui.print_('Nothing to edit.')
            return

        # Get the fields to edit.
        if opts.all:
            fields = None
        else:
            fields = self._get_fields(opts.album, opts.field)
        self.edit(opts.album, objs, fields)

    def _get_fields(self, album, extra):
        """Get the set of fields to edit.
        """
        # Start with the configured base fields.
        if album:
            fields = self.config['albumfields'].as_str_seq()
        else:
            fields = self.config['itemfields'].as_str_seq()

        # Add the requested extra fields.
        if extra:
            fields += extra

        # Ensure we always have the `id` field for identification.
        fields.append('id')

        return set(fields)

    def edit(self, album, objs, fields):
        """The core editor function.

        - `album`: A flag indicating whether we're editing Items or Albums.
        - `objs`: The `Item`s or `Album`s to edit.
        - `fields`: The set of field names to edit (or None to edit
          everything).
        """
        # Present the YAML to the user and let her change it.
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

        # Set up a temporary file with the initial data for editing.
        new = NamedTemporaryFile(suffix='.yaml', delete=False)
        old_str = dump(old_data)
        new.write(old_str)
        new.close()

        # Loop until we have parseable data and the user confirms.
        try:
            while True:
                # Ask the user to edit the data.
                edit(new.name)

                # Read the data back after editing and check whether anything
                # changed.
                with open(new.name) as f:
                    new_str = f.read()
                if new_str == old_str:
                    ui.print_("No changes; aborting.")
                    return False

                # Parse the updated data.
                try:
                    new_data = load(new_str)
                except ParseError as e:
                    ui.print_("Could not read data: {}".format(e))
                    if ui.input_yn("Edit again to fix? (Y/n)", True):
                        continue
                    else:
                        return False

                # Show the changes.
                self.apply_data(objs, old_data, new_data)
                changed = False
                for obj in objs:
                    changed |= ui.show_model_changes(obj)
                if not changed:
                    ui.print_('No changes to apply.')
                    return False

                # Confirm the changes.
                choice = ui.input_options(
                    ('continue Editing', 'apply', 'cancel')
                )
                if choice == 'a':  # Apply.
                    return True
                elif choice == 'c':  # Cancel.
                    return False
                elif choice == 'e':  # Keep editing.
                    # Reset the temporary changes to the objects.
                    for obj in objs:
                        obj.read()
                    continue

        # Remove the temporary file before returning.
        finally:
            os.remove(new.name)

    def apply_data(self, objs, old_data, new_data):
        """Take potentially-updated data and apply it to a set of Model
        objects.

        The objects are not written back to the database, so the changes
        are temporary.
        """
        if len(old_data) != len(new_data):
            self._log.warn('number of objects changed from {} to {}',
                           len(old_data), len(new_data))

        obj_by_id = {o.id: o for o in objs}
        ignore_fields = self.config['ignore_fields'].as_str_seq()
        for old_dict, new_dict in zip(old_data, new_data):
            # Prohibit any changes to forbidden fields to avoid
            # clobbering `id` and such by mistake.
            forbidden = False
            for key in ignore_fields:
                if old_dict.get(key) != new_dict.get(key):
                    self._log.warn('ignoring object whose {} changed', key)
                    forbidden = True
                    break
            if forbidden:
                continue

            id = int(old_dict['id'])
            apply(obj_by_id[id], new_dict)

    def save_changes(self, objs):
        """Save a list of updated Model objects to the database.
        """
        # Save to the database and possibly write tags.
        for ob in objs:
            if ob._dirty:
                self._log.debug('saving changes to {}', ob)
                ob.try_sync(ui.should_write(), ui.should_move())
