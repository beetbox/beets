# This file is part of beets.
# Copyright 2011, Adrian Sampson.
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

"""Tests for the command-line interface.
"""
import unittest
import os
import shutil
import textwrap
from StringIO import StringIO

import _common
from beets import library
from beets import ui
from beets.ui import commands
from beets import autotag
from beets import importer

class ListTest(unittest.TestCase):
    def setUp(self):
        self.io = _common.DummyIO()
        self.io.install()

        self.lib = library.Library(':memory:')
        i = _common.item()
        i.path = 'xxx/yyy'
        self.lib.add(i)
        self.lib.add_album([i])
        self.item = i

    def tearDown(self):
        self.io.restore()
        
    def test_list_outputs_item(self):
        commands.list_items(self.lib, '', False, False)
        out = self.io.getoutput()
        self.assertTrue(u'the title' in out)

    def test_list_unicode_query(self):
        self.item.title = u'na\xefve'
        self.lib.store(self.item)
        self.lib.save()

        commands.list_items(self.lib, [u'na\xefve'], False, False)
        out = self.io.getoutput()
        self.assertTrue(u'na\xefve' in out.decode(self.io.stdout.encoding))

    def test_list_item_path(self):
        commands.list_items(self.lib, '', False, True)
        out = self.io.getoutput()
        self.assertEqual(out.strip(), u'xxx/yyy')

    def test_list_album_outputs_something(self):
        commands.list_items(self.lib, '', True, False)
        out = self.io.getoutput()
        self.assertGreater(len(out), 0)

    def test_list_album_path(self):
        commands.list_items(self.lib, '', True, True)
        out = self.io.getoutput()
        self.assertEqual(out.strip(), u'xxx')
    
    def test_list_album_omits_title(self):
        commands.list_items(self.lib, '', True, False)
        out = self.io.getoutput()
        self.assertTrue(u'the title' not in out)

    def test_list_uses_track_artist(self):
        commands.list_items(self.lib, '', False, False)
        out = self.io.getoutput()
        self.assertTrue(u'the artist' in out)
        self.assertTrue(u'the album artist' not in out)
    
    def test_list_album_uses_album_artist(self):
        commands.list_items(self.lib, '', True, False)
        out = self.io.getoutput()
        self.assertTrue(u'the artist' not in out)
        self.assertTrue(u'the album artist' in out)

class RemoveTest(unittest.TestCase):
    def setUp(self):
        self.io = _common.DummyIO()
        self.io.install()

        self.libdir = os.path.join(_common.RSRC, 'testlibdir')
        os.mkdir(self.libdir)

        # Copy a file into the library.
        self.lib = library.Library(':memory:', self.libdir)
        self.i = library.Item.from_path(os.path.join(_common.RSRC, 'full.mp3'))
        self.lib.add(self.i, True)

    def tearDown(self):
        self.io.restore()
        shutil.rmtree(self.libdir)

    def test_remove_items_no_delete(self):
        self.io.addinput('y')
        commands.remove_items(self.lib, '', False, False)
        items = self.lib.items()
        self.assertEqual(len(list(items)), 0)
        self.assertTrue(os.path.exists(self.i.path))

    def test_remove_items_with_delete(self):
        self.io.addinput('y')
        commands.remove_items(self.lib, '', False, True)
        items = self.lib.items()
        self.assertEqual(len(list(items)), 0)
        self.assertFalse(os.path.exists(self.i.path))

class ModifyTest(unittest.TestCase):
    def setUp(self):
        self.io = _common.DummyIO()
        self.io.install()

        self.libdir = os.path.join(_common.RSRC, 'testlibdir')
        os.mkdir(self.libdir)

        # Copy a file into the library.
        self.lib = library.Library(':memory:', self.libdir)
        self.i = library.Item.from_path(os.path.join(_common.RSRC, 'full.mp3'))
        self.lib.add(self.i, True)
        self.album = self.lib.add_album([self.i])

    def tearDown(self):
        self.io.restore()
        shutil.rmtree(self.libdir)

    def _modify(self, mods, query=(), write=False, move=False, album=False):
        self.io.addinput('y')
        commands.modify_items(self.lib, mods, query,
                              write, move, album, True, True)

    def test_modify_item_dbdata(self):
        self._modify(["title=newTitle"])
        item = self.lib.items().next()
        self.assertEqual(item.title, 'newTitle')

    def test_modify_album_dbdata(self):
        self._modify(["album=newAlbum"], album=True)
        album = self.lib.albums()[0]
        self.assertEqual(album.album, 'newAlbum')

    def test_modify_item_tag_unmodified(self):
        self._modify(["title=newTitle"], write=False)
        item = self.lib.items().next()
        item.read()
        self.assertEqual(item.title, 'full')

    def test_modify_album_tag_unmodified(self):
        self._modify(["album=newAlbum"], write=False, album=True)
        item = self.lib.items().next()
        item.read()
        self.assertEqual(item.album, 'the album')

    def test_modify_item_tag(self):
        self._modify(["title=newTitle"], write=True)
        item = self.lib.items().next()
        item.read()
        self.assertEqual(item.title, 'newTitle')

    def test_modify_album_tag(self):
        self._modify(["album=newAlbum"], write=True, album=True)
        item = self.lib.items().next()
        item.read()
        self.assertEqual(item.album, 'newAlbum')

    def test_item_move(self):
        self._modify(["title=newTitle"], move=True)
        item = self.lib.items().next()
        self.assertTrue('newTitle' in item.path)

    def test_album_move(self):
        self._modify(["album=newAlbum"], move=True, album=True)
        item = self.lib.items().next()
        item.read()
        self.assertTrue('newAlbum' in item.path)

    def test_item_not_move(self):
        self._modify(["title=newTitle"], move=False)
        item = self.lib.items().next()
        self.assertFalse('newTitle' in item.path)

    def test_album_not_move(self):
        self._modify(["album=newAlbum"], move=False, album=True)
        item = self.lib.items().next()
        item.read()
        self.assertFalse('newAlbum' in item.path)

class PrintTest(unittest.TestCase):
    def setUp(self):
        self.io = _common.DummyIO()
        self.io.install()
    def tearDown(self):
        self.io.restore()
    
    def test_print_without_locale(self):
        lang = os.environ.get('LANG')
        if lang:
            del os.environ['LANG']

        try:
            ui.print_(u'something')
        except TypeError:
            self.fail('TypeError during print')
        finally:
            if lang:
                os.environ['LANG'] = lang

    def test_print_with_invalid_locale(self):
        old_lang = os.environ.get('LANG')
        os.environ['LANG'] = ''
        old_ctype = os.environ.get('LC_CTYPE')
        os.environ['LC_CTYPE'] = 'UTF-8'

        try:
            ui.print_(u'something')
        except ValueError:
            self.fail('ValueError during print')
        finally:
            if old_lang:
                os.environ['LANG'] = old_lang
            else:
                del os.environ['LANG']
            if old_ctype:
                os.environ['LC_CTYPE'] = old_ctype
            else:
                del os.environ['LC_CTYPE']

class AutotagTest(unittest.TestCase):
    def setUp(self):
        self.io = _common.DummyIO()
        self.io.install()
    def tearDown(self):
        self.io.restore()

    def _no_candidates_test(self, result):
        task = importer.ImportTask(
            'toppath',
            'path',
            [_common.item()],
        )
        task.set_match('artist', 'album', [], autotag.RECOMMEND_NONE)
        res = commands.choose_match(task, _common.iconfig(None, quiet=False))
        self.assertEqual(res, result)
        self.assertTrue('No match' in self.io.getoutput())

    def test_choose_match_with_no_candidates_skip(self):
        self.io.addinput('s')
        self._no_candidates_test(importer.action.SKIP)

    def test_choose_match_with_no_candidates_asis(self):
        self.io.addinput('u')
        self._no_candidates_test(importer.action.ASIS)

class ImportTest(unittest.TestCase):
    def test_quiet_timid_disallowed(self):
        self.assertRaises(ui.UserError, commands.import_files,
                          None, [], False, False, False, None, False, False,
                          False, False, True, False, None, False, True)

class InputTest(unittest.TestCase):
    def setUp(self):
        self.io = _common.DummyIO()
        self.io.install()
    def tearDown(self):
        self.io.restore()

    def test_manual_search_gets_unicode(self):
        self.io.addinput('\xc3\x82me')
        self.io.addinput('\xc3\x82me')
        artist, album = commands.manual_search(False)
        self.assertEqual(artist, u'\xc2me')
        self.assertEqual(album, u'\xc2me')

class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.io = _common.DummyIO()
        self.io.install()
        self.test_cmd = ui.Subcommand('test', help='test')
        commands.default_commands.append(self.test_cmd)
    def tearDown(self):
        self.io.restore()
        commands.default_commands.pop()
    def _run_main(self, args, config, func):
        self.test_cmd.func = func
        ui.main(args + ['test'], StringIO(config))

    def test_paths_section_respected(self):
        def func(lib, config, opts, args):
            self.assertEqual(lib.path_formats['x'], 'y')
        self._run_main([], textwrap.dedent("""
            [paths]
            x=y"""), func)

    def test_default_paths_preserved(self):
        def func(lib, config, opts, args):
            self.assertEqual(lib.path_formats['default'],
                             ui.DEFAULT_PATH_FORMATS['default'])
        self._run_main([], textwrap.dedent("""
            [paths]
            x=y"""), func)

    def test_default_paths_overriden_by_legacy_path_format(self):
        def func(lib, config, opts, args):
            self.assertEqual(lib.path_formats['default'], 'x')
            self.assertEqual(len(lib.path_formats), 1)
        self._run_main([], textwrap.dedent("""
            [beets]
            path_format=x"""), func)

    def test_paths_section_overriden_by_cli_switch(self):
        def func(lib, config, opts, args):
            self.assertEqual(lib.path_formats['default'], 'z')
            self.assertEqual(len(lib.path_formats), 1)
        self._run_main(['-p', 'z'], textwrap.dedent("""
            [paths]
            x=y"""), func)

    def test_nonexistant_config_file(self):
        os.environ['BEETSCONFIG'] = '/xxxxx'
        ui.main(['version'])

    def test_nonexistant_db(self):
        def func(lib, config, opts, args):
            pass
        with self.assertRaises(ui.UserError):
            self._run_main([], textwrap.dedent("""
                [beets]
                library: /xxx/yyy/not/a/real/path
            """), func)

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
