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
    """Open `filename` in a test editor.
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
    return yaml.load_all(s)


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
        self.edit(lib, opts.album, objs, fields)

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

    def edit(self, lib, album, objs, fields):
        """The core editor logic.

        - `lib`: The `Library` object.
        - `album`: A flag indicating whether we're editing Items or Albums.
        - `objs`: The `Item`s or `Album`s to edit.
        - `fields`: The set of field names to edit (or None to edit
          everything).
        """
        # Get the content to edit as raw data structures.
        data = [flatten(o, fields) for o in objs]

        # Present the YAML to the user and let her change it.
        new_data = self.edit_data(data)
        if new_data is None:
            # Editing failed.
            return

        # Filter out any forbidden fields so we can avoid clobbering
        # `id` and such by mistake.
        ignore_fields = self.config['ignore_fields'].as_str_seq()
        for d in data:
            for key in list(d):
                if key in ignore_fields:
                    del d[key]

        # Save the new data.
        self.save_items(data, lib, album)

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

        # Read the data back after editing and check whether anything
        # changed.
        with open(new.name) as f:
            new_str = f.read()
        os.remove(new.name)
        if new_str == old_str:
            ui.print_("No changes; aborting.")
            return None

        # Parse the updated data.
        try:
            return load(new_str)
        except yaml.YAMLError as e:
            ui.print_("Invalid YAML: {}".format(e))
            return None

    def nice_format(self, newset):
        # format the results so that we have an ID at the top
        # that we can change to a userfrienly title/artist format
        # when we present our results
        wellformed = collections.defaultdict(dict)
        for item in newset:
            for field in item:
                wellformed[item[0].values()[0]].update(field)
        return wellformed

    def save_items(self, oldnewlist, lib, album):

        oldset, newset = zip(*oldnewlist)
        niceNewSet = self.nice_format(newset)
        niceOldSet = self.nice_format(oldset)
        niceCombiSet = zip(niceOldSet.items(), niceNewSet.items())
        changedObjs = []
        for o, n in niceCombiSet:
            if album:
                ob = lib.get_album(int(n[0]))
            else:
                ob = lib.get_item(n[0])
            # change id to item-string
            ob.update(n[1])  # update the object
            changedObjs.append(ob)

        # see the changes we made
        for obj in changedObjs:
            ui.show_model_changes(obj)

        self.save_write(changedObjs)

    def save_write(self, changedob):
        if not ui.input_yn(
                ui.colorize('action_default', 'really modify? (y/n)')):
            return

        for ob in changedob:
            self._log.debug('saving changes to {}', ob)
            ob.try_sync(ui.should_write())

        return
