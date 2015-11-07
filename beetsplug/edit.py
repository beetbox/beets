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

"""Open metadata information in a text editor to let the user change
them directly.
"""
from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from beets import plugins
from beets.ui import Subcommand, decargs, library, print_
import subprocess
import difflib
import yaml
import collections
import webbrowser
from sys import exit
from beets import config
from beets import ui
from tempfile import NamedTemporaryFile
import os


class EditPlugin(plugins.BeetsPlugin):

    def __init__(self):
        super(EditPlugin, self).__init__()

        self.config.add({
            'style': 'yaml',
            'editor': '',
            'diff_method': '',
            'browser': '',
            'albumfields': 'album albumartist',
            'itemfields': 'track title artist album',
            'not_fields': 'id path',
            'sep': '-',
        })

        self.style = self.config['style'].get(unicode)

        # The editor field in the config lets you specify your editor.
        # Defaults to open with webrowser module.
        self.editor = self.config['editor'].as_str_seq()

        # the html_viewer field in your config lets you specify
        # your htmlviewer. Defaults to open with webrowser module
        self.browser = self.config['browser'].as_str_seq()

        # the diff_method field in your config picks the way to see your
        # changes. Options are:
        # 'ndiff'(2 files with differences),
        # 'unified'(just the different lines and a few lines of context),
        # 'html'(view in html-format),
        # 'vimdiff'(view in VIM)
        self.diff_method = self.config['diff_method'].get(unicode)

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

        # the separator in your config sets the separator that will be used
        # between fields in your terminal. Defaults to -
        self.sep = self.config['sep'].get(unicode)

        self.ed = None
        self.ed_args = None
        self.brw = None
        self.brw_args = None

    def commands(self):
        edit_command = Subcommand(
            'edit',
            help='interactively edit metadata')
        edit_command.parser.add_option(
            '-e', '--extra',
            action='store',
            help='add additional fields to edit',
        )
        edit_command.parser.add_option(
            '--all',
            action='store_true', dest='all',
            help='edit all fields',
        )
        edit_command.parser.add_option(
            '--sum',
            action='store_true', dest='sum',
            help='list fields with the same value',
        )
        edit_command.parser.add_all_common_options()
        edit_command.func = self.editor_music
        return[edit_command]

    def editor_music(self, lib, opts, args):
        if self.editor:
            self.ed_args = self.editor[1:] if len(self.editor) > 1 else None
            self.ed = self.editor[0] if self.editor else None
        if self.browser:
            self.brw_args = self.browser[1:] if len(self.browser) > 1 else None
            self.brw = self.browser[0] if self.browser else None

        # edit tags in a textfile in yaml-style
        query = decargs(args)
        # makes a string representation of an object
        # for now yaml but we could add html,pprint,toml
        self.print_items = {
            'yaml': self.print_to_yaml}
        # makes an object from a string representation
        # for now yaml but we could add html,pprint,toml
        self.string_to_dict = {
            'yaml': self.yaml_to_dict}
        # 4 ways to view the changes in objects
        self.diffresults = {
            'ndiff': self.ndiff,
            'unified': self.unified,
            'html': self.html,
            'vimdiff': self.vimdiff}
        # make a dictionary from the chosen fields
        # you can do em all or a selection
        self.make_dict = {
            'all': self.get_all_fields,
            "selected": self.get_selected_fields}

        objs = self._get_objs(lib, opts, query)
        if not objs:
            print_('nothing found')
            return
        fmt = self.get_fields_from(objs, opts)
        print_(fmt)
        [print_(format(item, fmt)) for item in objs]
        if not ui.input_yn(ui.colorize('action_default', "Edit?(n/y)"), True):
            return
        dict_from_objs = self.make_dict[self.pick](self.fields, objs, opts)
        newyaml, oldyaml = self.change_objs(dict_from_objs)
        changed_objs = self.check_diff(newyaml, oldyaml, opts)
        if not changed_objs:
            print_("nothing to change")
            return
        self.save_items(changed_objs, lib, fmt, opts)

    def print_to_yaml(self, arg):
        # from object to yaml
        return yaml.safe_dump_all(
            arg,
            allow_unicode=True,
            default_flow_style=False)

    def yaml_to_dict(self, yam):
        # from yaml to object
        return yaml.load_all(yam)

    def _get_objs(self, lib, opts, query):
        # get objects from a query
        if opts.album:
            return list(lib.albums(query))
        else:
            return list(lib.items(query))

    def get_fields_from(self, objs, opts):
        # construct a list of fields we need
        cl = ui.colorize('action', self.sep)
        # see if we need album or item fields
        self.fields = self.albumfields if opts.album else self.itemfields
        # if opts.format is given only use those fields
        if opts.format:
            self.fields = []
            self.fields.extend((opts.format).replace('$', "").split())
        # if opts.extra is given add those
        if opts.extra:
            fi = (opts.extra).replace('$', "").split()
            self.fields.extend([f for f in fi if f not in self.fields])
        # make sure we got the id for identification
        if 'id' not in self.fields:
            self.fields.insert(0, 'id')
        # we need all the fields
        if opts.all:
            self.fields = None
            self.pick = "all"
            print_(ui.colorize('text_warning', "edit all fields from:"))
            if opts.album:
                fmt = cl + cl.join(['$albumartist', '$album'])
            else:
                fmt = cl + cl.join(['$title', '$artist'])
        else:
            for it in self.fields:
                if opts.album:
                    if it not in library.Album.all_keys():
                        print_(
                            "{} not in albumfields.Removed it.".format(
                                ui.colorize(
                                    'text_warning', it)))
                        self.fields.remove(it)
                else:
                    if it not in library.Item.all_keys():
                        print_(
                            "{} not in itemfields.Removed it.".format(
                                ui.colorize(
                                    'text_warning', it)))
                        self.fields.remove(it)
            self.pick = "selected"
            fmtfields = ["$" + it for it in self.fields]
            fmt = cl + cl.join(fmtfields[1:])

        return fmt

    def get_selected_fields(self, myfields, objs, opts):
        a = []
        if opts.sum:
            for field in myfields:
                if field not in self.not_fields:
                    d = collections.defaultdict(str)
                    for obj in objs:
                        d[obj[field]] += (" " + str(obj['id']))
                    a.append([field, [{f: i} for f, i in d.items()]])
            return a
        else:
            for mod in objs:
                a.append([{fi: mod[fi]}for fi in myfields])
            return a

    def get_all_fields(self, myfields, objs, opts):
        a = []
        if opts.sum:
            fields = (library.Album.all_keys() if opts.album
                      else library.Item.all_keys())
            for field in sorted(fields):
                # for every field get a dict
                d = collections.defaultdict(str)
                for obj in objs:
                    # put all the ob-ids in the dict[field] as a string
                    d[obj[field]] += (" " + str(obj['id']))
                # for the field, we get the value and the users
                a.append([field, [{f: i} for f, i in sorted(d.items())]])
            return a
        else:
            for mod in objs:
                a.append([{fi: mod[fi]} for fi in sorted(mod._fields)])
            return a

    def change_objs(self, dict_items):
        # construct a yaml from the original object-fields
        # and make a yaml that we can change in the text-editor
        oldyaml = self.print_items[self.style](dict_items)
        newyaml = self.print_items[self.style](dict_items)
        new = NamedTemporaryFile(suffix='.yaml', delete=False)
        new.write(newyaml)
        new.close()
        self.get_editor(new.name)

        if ui.input_yn(ui.colorize('action_default', "done?(y)"), True):
            while True:
                try:
                    with open(new.name) as f:
                        newyaml = f.read()
                        list(yaml.load_all(newyaml))
                        break
                except yaml.YAMLError as e:
                    print_(ui.colorize('text_warning',
                           "change this fault: {}".format(e)))
                    print_("correct format for empty = - '' :")
                    if ui.input_yn(
                            ui.colorize('action_default', "fix?(y)"), True):
                        self.get_editor(new.name)
                        if ui.input_yn(ui.colorize(
                           'action_default', "ok.fixed.(y)"), True):
                            pass

            return newyaml, oldyaml
        else:
            exit()

    def get_editor(self, name):
        if not self.ed:
            editor = os.getenv('EDITOR')
            if editor:
                os.system(editor + " " + name)
            else:
                webbrowser.open(name, new=2, autoraise=True)
        else:
            callmethod = [self.ed]
            if self.ed_args:
                callmethod.extend(self.ed_args)
            callmethod.append(name)
            subprocess.check_call(callmethod)

    def same_format(self, newset, opts):
        alld = collections.defaultdict(dict)
        if opts.sum:
            for o in newset:
                for so in o:
                    ids = set((so[1].values()[0].split()))
                    for id in ids:
                        alld[id].update(
                            {so[0].items()[0][1]: so[1].items()[0][0]})
        else:
            for o in newset:
                for so in o:
                    alld[o[0].values()[0]].update(so)
        return alld

    def save_items(self, oldnewlist, lib, fmt, opts):

        oldset, newset = zip(*oldnewlist)
        no = self.same_format(newset, opts)
        oo = self.same_format(oldset, opts)
        ono = zip(oo.items(), no.items())
        nl = []
        ol = []
        changedob = []
        for o, n in ono:
            if opts.album:
                ob = lib.get_album(int(n[0]))
            else:
                ob = lib.get_item(n[0])
            # change id to item-string
            ol.append((format(ob),) + o[1:])
            ob.update(n[1])
            nl.append((format(ob),) + n[1:])
            changedob.append(ob)
        # see the changes we made
        if self.diff_method:
            ostr = self.print_items[self.style](ol)
            nwstr = self.print_items[self.style](nl)
            self.diffresults[self.diff_method](ostr, nwstr)
        else:
            for obj in changedob:
                ui.show_model_changes(obj)
        self.save_write(changedob)

    def save_write(self, changedob):
        if not ui.input_yn('really modify? (y/n)'):
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
        nl = self.string_to_dict[self.style](newyaml)
        ol = self.string_to_dict[self.style](oldyaml)
        if opts.sum:
            return filter(None, map(self.reduce_sum, ol, nl))
        else:
            return filter(None, map(self.reduce_it, ol, nl))

    def reduce_sum(self, ol, nl):
        # only get the changed objs
        if ol != nl:
            sol = [i for i in ol[1]]
            snl = [i for i in nl[1]]
            a = filter(None, map(self.reduce_sub, sol, snl))
            header = {"field": ol[0]}
            ol = [[header, b[0]] for b in a]
            nl = [[header, b[1]] for b in a]
            return ol, nl

    def reduce_sub(self, sol, snl):
        # if the keys have changed  resets them
        if sol != snl:
            if snl.values() != sol.values():
                snl[snl.keys()[0]] = sol[sol.keys()[0]]
        if sol != snl:
            return sol, snl

    def reduce_it(self, ol, nl):
        # if there is a forbidden field it resets them
        if ol != nl:
            for x in range(0, len(nl)):
                if ol[x] != nl[x] and ol[x].keys()[0]in self.not_fields:
                    nl[x] = ol[x]
                    print_("reset forbidden field.")
        if ol != nl:
            return ol, nl

    def ndiff(self, newfilestr, oldfilestr):
        newlines = newfilestr.splitlines()
        oldlines = oldfilestr.splitlines()
        diff = difflib.ndiff(newlines, oldlines)
        print_('\n'.join(list(diff)))
        return

    def unified(self, newfilestr, oldfilestr):
        newlines = newfilestr.splitlines()
        oldlines = oldfilestr.splitlines()
        diff = difflib.unified_diff(newlines, oldlines, lineterm='')
        print_('\n'.join(list(diff)))
        return

    def html(self, newfilestr, oldfilestr):
        newlines = newfilestr.splitlines()
        oldlines = oldfilestr.splitlines()
        diff = difflib.HtmlDiff()
        df = diff.make_file(newlines, oldlines)
        ht = NamedTemporaryFile('w', suffix='.html', delete=False)
        ht.write(df)
        ht.flush()
        hdn = ht.name
        if not self.brw:
            browser = os.getenv('BROWSER')
            if browser:
                os.system(browser + " " + hdn)
            else:
                webbrowser.open(hdn, new=2, autoraise=True)
        else:
            callmethod = [self.brw]
            if self.brw_args:
                callmethod.extend(self.brw_args)
            callmethod.append(hdn)
            subprocess.call(callmethod)
        return

    def vimdiff(self, newstringstr, oldstringstr):

        newdiff = NamedTemporaryFile(suffix='.old.yaml', delete=False)
        newdiff.write(newstringstr)
        newdiff.close()
        olddiff = NamedTemporaryFile(suffix='.new.yaml', delete=False)
        olddiff.write(oldstringstr)
        olddiff.close()
        subprocess.call(['vimdiff', newdiff.name, olddiff.name])
