# This file is part of beets.
# Copyright 2015, Jean-Marie Winters
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

"""open tags of items in texteditor,change them and save back to the items.
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


class yamleditorPlugin(plugins.BeetsPlugin):

    def __init__(self):
        super(yamleditorPlugin, self).__init__()

        self.config.add({
            'style': 'yaml',
            'editor': '',
            'diff_method': '',
            'html_viewer': '',
            'editor_args': '',
            'html_args': '',
            'albumfields': 'album albumartist',
            'itemfields': 'track title artist album ',
            'not_fields': 'path',
            'separator': '-'

        })

    def commands(self):
        yamleditor_command = Subcommand(
            'yamleditor',
            help='send items to yamleditor for editing tags')
        yamleditor_command.parser.add_option(
            '-e', '--extra',
            action='store',
            help='add additional fields to edit',
        )
        yamleditor_command.parser.add_all_common_options()
        yamleditor_command.func = self.editor_music
        return[yamleditor_command]

    def editor_music(self, lib, opts, args):
        """edit tags in a textfile in yaml-style
        """
        self.style = self.config['style'].get()
        """the editor field in the config lets you specify your editor.
        Defaults to open with webrowser module"""
        self.editor = self.config['editor'].get()
        """the editor_args field in your config lets you specify
        additional args for your editor"""
        self.editor_args = self.config['editor_args'].get().split()
        """the html_viewer field in your config lets you specify
        your htmlviewer. Defaults to open with webrowser module"""
        self.html_viewer = self.config['html_viewer'].get()
        """the html_args field in your config lets you specify
        additional args for your viewer"""
        self.html_args = self.config['html_args'].get().split()
        """the diff_method field in your config picks the way to see your
         changes. Options are:
        'ndiff'(2 files with differences),
        'unified'(just the different lines and a few lines of context),
        'html'(view in html-format),
        'vimdiff'(view in VIM)"""
        self.diff_method = self.config['diff_method'].get()
        """the albumfields field in your config sets the tags that
        you want to see/change for albums.
        Defaults to album albumartist.
        the ID tag will always be listed as it is used to identify the item"""
        self.albumfields = self.config['albumfields'].get().split()
        """the itemfields field in your config sets the tags that
        you want to see/change or items.
        Defaults to track title artist album.
        the ID tag will always be listed as it is used to identify the item"""
        self.itemfields = self.config['itemfields'].get().split()
        '''the not_fields field in your config sets the tags that
        will not be changed.
        If you happen to change them, they will be restored to the original
        value. The ID of an item will never be changed.'''
        self.not_fields = self.config['not_fields'].get().split()
        '''the separator in your config sets the separator that will be used
        between fields in your terminal. Defaults to -'''
        self.separator = self.config['separator'].get()

        query = decargs(args)
        self.print_items = {
            'yaml': self.print_to_yaml}
        self.diffresults = {
            'ndiff': self.ndiff,
            'unified': self.unified,
            'html': self.html,
            'vimdiff': self.vimdiff}
        self.make_dict = {
            'all': self.get_all_fields,
            "selected": self.get_selected_fields}
        self.string_to_dict = {
            'yaml': self.yaml_to_dict}

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
        changed_objs = self.check_diff(newyaml, oldyaml)
        if not changed_objs:
            print_("nothing to change")
            return
        self.save_items(changed_objs, lib, fmt, opts)

    '''from object to yaml'''
    def print_to_yaml(self, arg):
        return yaml.safe_dump_all(
            arg,
            allow_unicode=True,
            default_flow_style=False)

    '''from yaml to object'''
    def yaml_to_dict(self, yam):
        return yaml.load_all(yam)

    def _get_objs(self, lib, opts, query):
        if opts.album:
            return list(lib.albums(query))
        else:
            return list(lib.items(query))

    def get_fields_from(self, objs, opts):
        cl = ui.colorize('action', self.separator)
        self.fields = self.albumfields if opts.album else self.itemfields
        if opts.format:
            self.fields = []
            self.fields.extend((opts.format).replace('$', "").split())
        if opts.extra:
            fi = (opts.extra).replace('$', "").split()
            self.fields.extend([f for f in fi if f not in self.fields])
        if 'id' not in self.fields:
            self.fields.insert(0, 'id')
        if "_all" in self.fields:
            self.fields = None
            self.pick = "all"
            print_(ui.colorize('text_warning', "edit all fields from ..."))
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

    '''get the fields we want and make a dic from them'''
    def get_selected_fields(self, myfields, objs, opts):
        a = []
        for mod in objs:
            a.append([{fi: mod[fi]}for fi in myfields])
        return a

    def get_all_fields(self, myfields, objs, opts):
        a = []
        for mod in objs:
            a.append([{fi: mod[fi]} for fi in sorted(mod._fields)])
        return a

    def change_objs(self, dict_items):
        oldyaml = self.print_items[self.style](dict_items)
        newyaml = self.print_items[self.style](dict_items)
        new = NamedTemporaryFile(suffix='.yaml', delete=False)
        new.write(newyaml)
        new.close()
        if not self.editor:
            webbrowser.open(new.name, new=2, autoraise=True)
        if self.editor and not self.editor_args:
            subprocess.check_call([self.editor, new.name])
        elif self.editor and self.editor_args:
            subprocess.check_call(
                [self.editor, new.name, self.editor_args])

        if ui.input_yn(ui.colorize('action_default', "done?(y)"), True):
            with open(new.name) as f:
                newyaml = f.read()
            return newyaml, oldyaml
        else:
            exit()

    def save_items(self, oldnewlist, lib, fmt, opts):
        oldset = []
        newset = []
        for old, new in oldnewlist:
            oldset.append(old)
            newset.append(new)

        no = []
        for newitem in range(0, len(newset)):
            ordict = collections.OrderedDict()
            for each in newset[newitem]:
                ordict.update(each)
            no.append(ordict)

        changedob = []
        for each in no:
            if not opts.album:
                ob = lib.get_item(each['id'])
            else:
                ob = lib.get_album(each['id'])
            ob.update(each)
            changedob.append(ob)

        if self.diff_method:
            ostr = self.print_items[self.style](oldset)
            nwstr = self.print_items[self.style](newset)
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

    def check_diff(self, newyaml, oldyaml):
        nl = self.string_to_dict[self.style](newyaml)
        ol = self.string_to_dict[self.style](oldyaml)
        return filter(None, map(self.reduce_it, ol, nl))

    '''if there is a forbidden field it gathers them here(check_ids)'''
    def reduce_it(self, ol, nl):
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
        hdn = ht.name
        if not self.html_viewer:
            webbrowser.open(hdn, new=2, autoraise=True)
        else:
            callmethod = [self.html_viewer]
            callmethod.extend(self.html_args)
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
