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


class EditPlugin(plugins.BeetsPlugin):

    def __init__(self):
        super(EditPlugin, self).__init__()

        self.config.add({
            'albumfields': 'album albumartist',
            'itemfields': 'track title artist album',
            'not_fields': 'id path',
        })

        # the albumfields field in your config sets the tags that
        # you want to see/change for albums.
        # Defaults to album albumartist.
        # the ID tag will always be listed as it is used to identify the item
        self.albumfields = self.config['albumfields'].as_str_seq()

        # the itemfields field in your config sets the tags that
        # you want to see/change or items.
        # Defaults to track title artist album.
        # the ID tag will always be listed as it is used to identify the item
        self.itemfields = self.config['itemfields'].as_str_seq()

        # the not_fields field in your config sets the tags that
        # will not be changed.
        # If you happen to change them, they will be restored to the original
        # value. The ID of an item will never be changed.
        self.not_fields = self.config['not_fields'].as_str_seq()

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
        edit_command.func = self.editor_music
        return [edit_command]

    def editor_music(self, lib, opts, args):
        # Get the objects to edit.
        query = ui.decargs(args)
        items, albums = _do_query(lib, query, opts.album, False)
        objs = albums if opts.album else items
        if not objs:
            ui.print_('Nothing to edit.')
            return

        # Get the content to edit as raw data structures.
        if opts.all:
            data = self.get_all_fields(objs)
        else:
            fields = self.get_fields_from(objs, opts)
            data = self.get_selected_fields(fields, objs, opts)

        # Present the YAML to the user and let her change it.
        new_data = self.change_objs(data)
        changed_objs = self.check_diff(data, new_data)
        if changed_objs is None:
            # Editing failed.
            return

        # Save the new data.
        self.save_items(changed_objs, lib, opts)

    def get_fields_from(self, objs, opts):
        # construct a list of fields we need
        # see if we need album or item fields
        fields = self.albumfields if opts.album else self.itemfields
        # if opts.extra is given add those
        if opts.extra:
            fields.extend([f for f in opts.extra if f not in fields])
        # make sure we got the id for identification
        if 'id' not in fields:
            fields.insert(0, 'id')
        # we need all the fields
        if opts.all:
            fields = None
            ui.print_(ui.colorize('text_warning', "edit all fields from:"))
        else:
            for it in fields:
                if opts.album:
                    # check if it is really an albumfield
                    if it not in library.Album.all_keys():
                        ui.print_(
                            "{} not in albumfields.Removed it.".format(
                                ui.colorize(
                                    'text_warning', it)))
                        fields.remove(it)
                else:
                    # if it is not an itemfield remove it
                    if it not in library.Item.all_keys():
                        ui.print_(
                            "{} not in itemfields.Removed it.".format(
                                ui.colorize(
                                    'text_warning', it)))
                        fields.remove(it)

        return fields

    def get_selected_fields(self, myfields, objs, opts):
        return [[{field: obj[field]}for field in myfields]for obj in objs]

    def get_all_fields(self, objs):
        return [[{field: obj[field]}for field in sorted(obj._fields)]
                for obj in objs]

    def change_objs(self, dict_items):
        # Ask the user to edit the data.
        new = NamedTemporaryFile(suffix='.yaml', delete=False)
        new.write(dump(dict_items))
        new.close()
        edit(new.name)

        # Parse the updated data.
        with open(new.name) as f:
            new_str = f.read()
        os.remove(new.name)
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

    def save_items(self, oldnewlist, lib, opts):

        oldset, newset = zip(*oldnewlist)
        niceNewSet = self.nice_format(newset)
        niceOldSet = self.nice_format(oldset)
        niceCombiSet = zip(niceOldSet.items(), niceNewSet.items())
        changedObjs = []
        for o, n in niceCombiSet:
            if opts.album:
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

    def check_diff(self, old_data, new_data):
        return filter(None, map(self.reduce_it, old_data, new_data))

    def reduce_it(self, ol, nl):
        # if there is a forbidden field it resets them
        if ol != nl:
            for x in range(0, len(nl)):
                if ol[x] != nl[x] and ol[x].keys()[0]in self.not_fields:
                    nl[x] = ol[x]
                    ui.print_("reset forbidden field.")
        if ol != nl:  # only keep objects that have changed
            return ol, nl
