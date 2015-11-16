# This file is part of beets.
# Copyright 2015
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
from beets import library
from beets import ui
from beets.ui.commands import _do_query
import subprocess
import yaml
import collections
from tempfile import NamedTemporaryFile
import os


def edit(filename):
    """Open `filename` in a text editor.
    """
    cmd = util.shlex_split(util.editor_command())
    cmd.append(filename)
    subprocess.call(cmd)


def dump(arg):
    """Dump an object as YAML for editing.
    """
    return yaml.safe_dump_all(
        arg,
        allow_unicode=True,
        default_flow_style=False,
    )


def load(s):
    """Read a YAML string back to an object.
    """
    return list(yaml.load_all(s))


def flatten(obj, fields):
    """Represent `obj`, a `dbcore.Model` object, as a dictionary for
    serialization. Only include the given `fields` if provided;
    otherwise, include everything.
    """
    d = dict(obj)
    if fields:
        return {k: v for k, v in d.items() if k in fields}
    else:
        return d


def summarize(data, fields):
    """groups fields values by id of object
    """
    fields.remove('id')
    newdata = []
    for fi in fields:
        col = collections.defaultdict(str)
        for dt in data:
            col[dt[fi]] += (str(dt['id']) + " ")
        newdata.append([fi, [{f: i} for f, i in col.items()]])
    return newdata


def desummarize(old_data, new_data):
    """input an object organised by field object-ids and
    return object-by-id and it's changed fields
    """
    datacol = [old_data, new_data]
    newdatacol = []
    for data in datacol:
        newdata = collections.defaultdict(dict)
        for objs in data:
            for field in objs[1]:
                f, v = field.items()[0]
                ids = v.split()
                for id in ids:
                    newdata[id].update({objs[0]: f})
        nl = []
        for nid, v in newdata.items():
            a = {'id': int(nid)}
            a.update(v)
            nl.append(a)
        newdatacol.append(nl)
    return (newdatacol[0], newdatacol[1])


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
            '-e', '--extra',
            action='append',
            type='choice',
            choices=library.Item.all_keys() +
            library.Album.all_keys(),
            help='add additional fields to edit',
        )
        edit_command.parser.add_option(
            '--all',
            action='store_true', dest='all',
            help='edit all fields',
        )
        edit_command.parser.add_option(
            '--group',
            action='store_true', dest='group',
            help='group results by field',
        )
        edit_command.parser.add_all_common_options()
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
            fields = self._get_fields(opts.album, opts.extra)
        self.edit(opts.album, objs, fields, opts.group)

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

    def edit(self, album, objs, fields, group):
        """The core editor logic.

        - `album`: A flag indicating whether we're editing Items or Albums.
        - `objs`: The `Item`s or `Album`s to edit.
        - `fields`: The set of field names to edit (or None to edit
          everything).
        """
        # Get the content to edit as raw data structures.
        data = [flatten(o, fields) for o in objs]
        if group:
            data = summarize(data, fields)
        # Present the YAML to the user and let her change it.
        new_data = self.edit_data(data)
        if new_data is None:
            # Editing failed.
            return

        # Apply the updated metadata to the objects.
        self.apply_data(objs, data, new_data, group)

        # Save the new data.
        self.save_write(objs)

    def edit_data(self, data):
        """Dump a data structure to a file as text, ask the user to edit
        it, and then read back the updated data.

        If something goes wrong during editing, return None to indicate
        the process should abort.
        """
        # Ask the user to edit the data.
        new = NamedTemporaryFile(suffix='.yaml', delete=False)
        old_str = dump(data)
        new.write(old_str)
        new.close()
        edit(new.name)
        if not ui.input_yn('Done editing? (y/n)'):
            return None
        else:
            while True:
                try:
                    # Read the data back after editing
                    # and check whether anything changed.
                    with open(new.name) as f:
                        new_str = f.read()
                        if new_str == old_str:
                            ui.print_("No changes; aborting.")
                            return None
                        a = load(new_str)
                        os.remove(new.name)
                        return a
                except yaml.YAMLError as e:
                    # if malformatted yaml reopen to correct mistakes
                    ui.print_("Invalid YAML: {}".format(e))
                    if ui.input_yn(
                            ui.colorize('action_default', "Fix?(y/n)"), True):
                        edit(new.name)
                        if ui.input_yn(ui.colorize(
                           'action_default', "OK.Fixed.(y)"), True):
                            pass

    def apply_data(self, objs, old_data, new_data, group):
        """Take potentially-updated data and apply it to a set of Model
        objects.

        The objects are not written back to the database, so the changes
        are temporary.
        """
        if len(old_data) != len(new_data):
            self._log.warn('number of objects changed from {} to {}',
                           len(old_data), len(new_data))
        if group:
            old_data, new_data = desummarize(old_data, new_data)
        obj_by_id = {o.id: o for o in objs}
        ignore_fields = self.config['ignore_fields'].as_str_seq()
        for old_dict, new_dict in zip(old_data, new_data):
            # Prohibit any changes to forbidden fields to avoid
            # clobbering `id` and such by mistake.
            forbidden = False
            for key in ignore_fields:
                if old_dict.get(key) != new_dict.get(key):
                    self._log.warn('ignoring object where {} changed', key)
                    forbidden = True
                    break
            if forbidden:
                continue

            obj = obj_by_id[old_dict['id']]
            obj.update(new_dict)

    def save_write(self, objs):
        """Save a list of updated Model objects to the database.
        """
        # Display and confirm the changes.
        changed = False
        for obj in objs:
            changed |= ui.show_model_changes(obj)
        if not changed:
            ui.print_('No changes to apply.')
            return
        if not ui.input_yn('Apply changes? (y/n)'):
            return

        # Save to the database and possibly write tags.
        for ob in objs:
            self._log.debug('saving changes to {}', ob)
            ob.try_sync(ui.should_write())
