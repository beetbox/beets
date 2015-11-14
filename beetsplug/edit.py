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
from beets.ui import Subcommand, decargs, library, print_
from beets.ui.commands import _do_query
import subprocess
import yaml
import collections
from sys import exit
from beets import config
from beets import ui
from tempfile import NamedTemporaryFile
import os
import sys


class EditPlugin(plugins.BeetsPlugin):

    def __init__(self):
        super(EditPlugin, self).__init__()

        self.config.add({
            'editor': '',
            'albumfields': 'album albumartist',
            'itemfields': 'track title artist album',
            'not_fields': 'id path',
        })

        # The editor field in the config lets you specify your editor.
        self.editor = self.config['editor'].as_str_seq()

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

        self.ed = None
        self.ed_args = None

    def commands(self):
        edit_command = Subcommand(
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
        if self.editor:
            self.ed_args = self.editor[1:] if len(self.editor) > 1 else None
            self.ed = self.editor[0] if self.editor else None

        # main program flow
        # Get the objects to edit.
        query = decargs(args)
        items, albums = _do_query(lib, query, opts.album, False)
        objs = albums if opts.album else items
        if not objs:
            print_('Nothing to edit.')
            return
        # Confirmation from user about the queryresult
        for obj in objs:
            print_(format(obj))
        if not ui.input_yn(ui.colorize('action_default', "Edit? (y/n)"), True):
            return

        # get the fields from the objects
        if opts.all:
            data = self.get_all_fields(objs)
        else:
            fields = self.get_fields_from(objs, opts)
            data = self.get_selected_fields(fields, objs, opts)

        # present the yaml to the user and let her change it
        newyaml, oldyaml = self.change_objs(data)
        changed_objs = self.check_diff(newyaml, oldyaml, opts)
        if not changed_objs:
            print_("nothing to change")
            return
        self.save_items(changed_objs, lib, opts)

    def print_to_yaml(self, arg):
        # from object to yaml
        return yaml.safe_dump_all(
            arg,
            allow_unicode=True,
            default_flow_style=False)

    def yaml_to_dict(self, yam):
        # from yaml to object
        return yaml.load_all(yam)

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
            print_(ui.colorize('text_warning', "edit all fields from:"))
        else:
            for it in fields:
                if opts.album:
                    # check if it is really an albumfield
                    if it not in library.Album.all_keys():
                        print_(
                            "{} not in albumfields.Removed it.".format(
                                ui.colorize(
                                    'text_warning', it)))
                        fields.remove(it)
                else:
                    # if it is not an itemfield remove it
                    if it not in library.Item.all_keys():
                        print_(
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
        # construct a yaml from the original object-fields
        # and make a yaml that we can change in the text-editor
        oldyaml = self.print_to_yaml(dict_items)  # our backup
        newyaml = self.print_to_yaml(dict_items)  # goes to user
        new = NamedTemporaryFile(suffix='.yaml', delete=False)
        new.write(newyaml)
        new.close()
        self.get_editor(new.name)
        # wait for user to edit yaml and continue
        if ui.input_yn(ui.colorize('action_default', "done?(y)"), True):
            while True:
                try:
                    # reading the yaml back in
                    with open(new.name) as f:
                        newyaml = f.read()
                        list(yaml.load_all(newyaml))
                        os.remove(new.name)
                        break
                except yaml.YAMLError as e:
                    # some error-correcting mainly for empty-values
                    # not being well-formated
                    print_(ui.colorize('text_warning',
                           "change this fault: {}".format(e)))
                    print_("correct format for empty = - '' :")
                    if ui.input_yn(
                            ui.colorize('action_default', "fix?(y)"), True):
                        self.get_editor(new.name)
                        if ui.input_yn(ui.colorize(
                           'action_default', "ok.fixed.(y)"), True):
                            pass
            # only continue when all the mistakes are corrected
            return newyaml, oldyaml
        else:
            os.remove(new.name)
            exit()

    def open_file(self, startcmd):
        # opens a file in the standard program on all systems
        subprocess.call(('cmd /c start "" "' + startcmd + '"')
                        if os.name is 'nt' else (
                        'open' if sys.platform.startswith('darwin') else
                        'xdg-open', startcmd))

    def get_editor(self, name):
        if not self.ed:
            # if not specified in config use $EDITOR from system
            editor = os.getenv('EDITOR')
            if editor:
                os.system(editor + " " + name)
            else:
                # let the system handle the file
                self.open_file(name)
        else:
            # use the editor specified in config
            callmethod = [self.ed]
            if self.ed_args:
                callmethod.extend(self.ed_args)
            callmethod.append(name)
            subprocess.check_call(callmethod)

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
        newSetTitled = []
        oldSetTitled = []
        changedObjs = []
        for o, n in niceCombiSet:
            if opts.album:
                ob = lib.get_album(int(n[0]))
            else:
                ob = lib.get_item(n[0])
            # change id to item-string
            oldSetTitled.append((format(ob),) + o[1:])
            ob.update(n[1])  # update the object
            newSetTitled.append((format(ob),) + n[1:])
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
            if config['import']['write'].get(bool):
                ob.try_sync()
            else:
                ob.store()
            print("changed: {0}".format(ob))

        return

    def check_diff(self, newyaml, oldyaml, opts):
        # make python objs from yamlstrings
        nl = self.yaml_to_dict(newyaml)
        ol = self.yaml_to_dict(oldyaml)
        return filter(None, map(self.reduce_it, ol, nl))

    def reduce_it(self, ol, nl):
        # if there is a forbidden field it resets them
        if ol != nl:
            for x in range(0, len(nl)):
                if ol[x] != nl[x] and ol[x].keys()[0]in self.not_fields:
                    nl[x] = ol[x]
                    print_("reset forbidden field.")
        if ol != nl:  # only keep objects that have changed
            return ol, nl
