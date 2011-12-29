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
import logging
import re
from StringIO import StringIO
import ConfigParser

import _common
from beets import library
from beets import ui
from beets.ui import commands
from beets import autotag
from beets import importer
from beets.mediafile import MediaFile

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

class MoveTest(unittest.TestCase, _common.ExtraAsserts):
    def setUp(self):
        self.io = _common.DummyIO()
        self.io.install()

        self.libdir = os.path.join(_common.RSRC, 'testlibdir')
        os.mkdir(self.libdir)

        self.itempath = os.path.join(self.libdir, 'srcfile')
        shutil.copy(os.path.join(_common.RSRC, 'full.mp3'), self.itempath)

        # Add a file to the library but don't copy it in yet.
        self.lib = library.Library(':memory:', self.libdir)
        self.i = library.Item.from_path(self.itempath)
        self.lib.add(self.i, False)
        self.album = self.lib.add_album([self.i])

        # Alternate destination directory.
        self.otherdir = os.path.join(_common.RSRC, 'testotherdir')

    def tearDown(self):
        self.io.restore()
        shutil.rmtree(self.libdir)
        if os.path.exists(self.otherdir):
            shutil.rmtree(self.otherdir)

    def _move(self, query=(), dest=None, copy=False, album=False):
        commands.move_items(self.lib, dest, query, copy, album)

    def test_move_item(self):
        self._move()
        self.lib.load(self.i)
        self.assertTrue('testlibdir' in self.i.path)
        self.assertExists(self.i.path)
        self.assertNotExists(self.itempath)

    def test_copy_item(self):
        self._move(copy=True)
        self.lib.load(self.i)
        self.assertTrue('testlibdir' in self.i.path)
        self.assertExists(self.i.path)
        self.assertExists(self.itempath)

    def test_move_album(self):
        self._move(album=True)
        self.lib.load(self.i)
        self.assertTrue('testlibdir' in self.i.path)
        self.assertExists(self.i.path)
        self.assertNotExists(self.itempath)

    def test_copy_album(self):
        self._move(copy=True, album=True)
        self.lib.load(self.i)
        self.assertTrue('testlibdir' in self.i.path)
        self.assertExists(self.i.path)
        self.assertExists(self.itempath)

    def test_move_item_custom_dir(self):
        self._move(dest=self.otherdir)
        self.lib.load(self.i)
        self.assertTrue('testotherdir' in self.i.path)
        self.assertExists(self.i.path)
        self.assertNotExists(self.itempath)

    def test_move_album_custom_dir(self):
        self._move(dest=self.otherdir, album=True)
        self.lib.load(self.i)
        self.assertTrue('testotherdir' in self.i.path)
        self.assertExists(self.i.path)
        self.assertNotExists(self.itempath)

class UpdateTest(unittest.TestCase, _common.ExtraAsserts):
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

        # Album art.
        artfile = os.path.join(_common.RSRC, 'testart.jpg')
        _common.touch(artfile)
        self.album.set_art(artfile)
        os.remove(artfile)

    def tearDown(self):
        self.io.restore()
        shutil.rmtree(self.libdir)

    def _update(self, query=(), album=False, move=False, reset_mtime=True):
        self.io.addinput('y')
        if reset_mtime:
            self.i.mtime = 0
            self.lib.store(self.i)
        commands.update_items(self.lib, query, album, move, True, False)

    def test_delete_removes_item(self):
        self.assertTrue(list(self.lib.items()))
        os.remove(self.i.path)
        self._update()
        self.assertFalse(list(self.lib.items()))

    def test_delete_removes_album(self):
        self.assertTrue(self.lib.albums())
        os.remove(self.i.path)
        self._update()
        self.assertFalse(self.lib.albums())

    def test_delete_removes_album_art(self):
        artpath = self.album.artpath
        self.assertExists(artpath)
        os.remove(self.i.path)
        self._update()
        self.assertNotExists(artpath)

    def test_modified_metadata_detected(self):
        mf = MediaFile(self.i.path)
        mf.title = 'differentTitle'
        mf.save()
        self._update()
        item = self.lib.items().next()
        self.assertEqual(item.title, 'differentTitle')

    def test_modified_metadata_moved(self):
        mf = MediaFile(self.i.path)
        mf.title = 'differentTitle'
        mf.save()
        self._update(move=True)
        item = self.lib.items().next()
        self.assertTrue('differentTitle' in item.path)

    def test_modified_metadata_not_moved(self):
        mf = MediaFile(self.i.path)
        mf.title = 'differentTitle'
        mf.save()
        self._update(move=False)
        item = self.lib.items().next()
        self.assertTrue('differentTitle' not in item.path)

    def test_modified_album_metadata_moved(self):
        mf = MediaFile(self.i.path)
        mf.album = 'differentAlbum'
        mf.save()
        self._update(move=True)
        item = self.lib.items().next()
        self.assertTrue('differentAlbum' in item.path)

    def test_modified_album_metadata_art_moved(self):
        artpath = self.album.artpath
        mf = MediaFile(self.i.path)
        mf.album = 'differentAlbum'
        mf.save()
        self._update(move=True)
        album = self.lib.albums()[0]
        self.assertNotEqual(artpath, album.artpath)

    def test_mtime_match_skips_update(self):
        mf = MediaFile(self.i.path)
        mf.title = 'differentTitle'
        mf.save()

        # Make in-memory mtime match on-disk mtime.
        self.i.mtime = os.path.getmtime(self.i.path)
        self.lib.store(self.i)

        self._update(reset_mtime=False)
        item = self.lib.items().next()
        self.assertEqual(item.title, 'full')

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
                          False, False, True, False, None, False, True, None,
                          False, [])

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
            self.assertEqual(lib.path_formats[0], ('x', 'y'))
        self._run_main([], textwrap.dedent("""
            [paths]
            x=y"""), func)

    def test_default_paths_preserved(self):
        def func(lib, config, opts, args):
            self.assertEqual(lib.path_formats[1:],
                             ui.DEFAULT_PATH_FORMATS)
        self._run_main([], textwrap.dedent("""
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

    def test_replacements_parsed(self):
        def func(lib, config, opts, args):
            replacements = lib.replacements
            self.assertEqual(replacements, [(re.compile(r'[xy]'), 'z')])
        self._run_main([], textwrap.dedent("""
            [beets]
            replace=[xy] z"""), func)

    def test_empty_replacements_produce_none(self):
        def func(lib, config, opts, args):
            replacements = lib.replacements
            self.assertFalse(replacements)
        self._run_main([], textwrap.dedent("""
            [beets]
            """), func)

    def test_multiple_replacements_parsed(self):
        def func(lib, config, opts, args):
            replacements = lib.replacements
            self.assertEqual(replacements, [
                (re.compile(r'[xy]'), 'z'),
                (re.compile(r'foo'), 'bar'),
            ])
        self._run_main([], textwrap.dedent("""
            [beets]
            replace=[xy] z
                foo bar"""), func)

class ShowdiffTest(unittest.TestCase):
    def setUp(self):
        self.io = _common.DummyIO()
        self.io.install()
    def tearDown(self):
        self.io.restore()

    def test_showdiff_strings(self):
        commands._showdiff('field', 'old', 'new', True)
        out = self.io.getoutput()
        self.assertTrue('field' in out)

    def test_showdiff_identical(self):
        commands._showdiff('field', 'old', 'old', True)
        out = self.io.getoutput()
        self.assertFalse('field' in out)

    def test_showdiff_ints(self):
        commands._showdiff('field', 2, 3, True)
        out = self.io.getoutput()
        self.assertTrue('field' in out)

    def test_showdiff_ints_no_color(self):
        commands._showdiff('field', 2, 3, False)
        out = self.io.getoutput()
        self.assertTrue('field' in out)

    def test_showdiff_shows_both(self):
        commands._showdiff('field', 'old', 'new', True)
        out = self.io.getoutput()
        self.assertTrue('old' in out)
        self.assertTrue('new' in out)

    def test_showdiff_floats_close_to_identical(self):
        commands._showdiff('field', 1.999, 2.001, True)
        out = self.io.getoutput()
        self.assertFalse('field' in out)

    def test_showdiff_floats_differenct(self):
        commands._showdiff('field', 1.999, 4.001, True)
        out = self.io.getoutput()
        self.assertTrue('field' in out)

    def test_showdiff_ints_colorizing_is_not_stringwise(self):
        commands._showdiff('field', 222, 333, True)
        complete_diff = self.io.getoutput().split()[1]

        commands._showdiff('field', 222, 232, True)
        partial_diff = self.io.getoutput().split()[1]

        self.assertEqual(complete_diff, partial_diff)

AN_ID = "28e32c71-1450-463e-92bf-e0a46446fc11"
class ManualIDTest(unittest.TestCase):
    def setUp(self):
        _common.log.setLevel(logging.CRITICAL)
        self.io = _common.DummyIO()
        self.io.install()
    def tearDown(self):
        self.io.restore()

    def test_id_accepted(self):
        self.io.addinput(AN_ID)
        out = commands.manual_id(False)
        self.assertEqual(out, AN_ID)

    def test_non_id_returns_none(self):
        self.io.addinput("blah blah")
        out = commands.manual_id(False)
        self.assertEqual(out, None)

    def test_url_finds_id(self):
        self.io.addinput("http://musicbrainz.org/entity/%s?something" % AN_ID)
        out = commands.manual_id(False)
        self.assertEqual(out, AN_ID)

class ShowChangeTest(unittest.TestCase):
    def setUp(self):
        self.io = _common.DummyIO()
        self.io.install()
    def tearDown(self):
        self.io.restore()

    def _items_and_info(self):
        items = [_common.item()]
        items[0].track = 1
        items[0].path = '/path/to/file.mp3'
        info = autotag.AlbumInfo(
            'the album', 'album id', 'the artist', 'artist id', [
                autotag.TrackInfo('the title', 'track id')
        ])
        return items, info

    def test_null_change(self):
        items, info = self._items_and_info()
        commands.show_change('the artist', 'the album',
                             items, info, 0.1, color=False)
        msg = self.io.getoutput().lower()
        self.assertTrue('similarity: 90' in msg)
        self.assertTrue('tagging:' in msg)

    def test_album_data_change(self):
        items, info = self._items_and_info()
        commands.show_change('another artist', 'another album',
                             items, info, 0.1, color=False)
        msg = self.io.getoutput().lower()
        self.assertTrue('correcting tags from:' in msg)

    def test_item_data_change(self):
        items, info = self._items_and_info()
        items[0].title = 'different'
        commands.show_change('the artist', 'the album',
                             items, info, 0.1, color=False)
        msg = self.io.getoutput().lower()
        self.assertTrue('different -> the title' in msg)

    def test_item_data_change_with_unicode(self):
        items, info = self._items_and_info()
        items[0].title = u'caf\xe9'
        commands.show_change('the artist', 'the album',
                             items, info, 0.1, color=False)
        msg = self.io.getoutput().lower()
        self.assertTrue(u'caf\xe9 -> the title' in msg.decode('utf8'))

    def test_album_data_change_with_unicode(self):
        items, info = self._items_and_info()
        commands.show_change(u'caf\xe9', u'another album',
                             items, info, 0.1, color=False)
        msg = self.io.getoutput().lower()
        self.assertTrue('correcting tags from:' in msg)

    def test_item_data_change_title_missing(self):
        items, info = self._items_and_info()
        items[0].title = ''
        commands.show_change('the artist', 'the album',
                             items, info, 0.1, color=False)
        msg = self.io.getoutput().lower()
        self.assertTrue('file.mp3 -> the title' in msg)

    def test_item_data_change_title_missing_with_unicode_filename(self):
        items, info = self._items_and_info()
        items[0].title = ''
        items[0].path = u'/path/to/caf\xe9.mp3'.encode('utf8')
        commands.show_change('the artist', 'the album',
                             items, info, 0.1, color=False)
        msg = self.io.getoutput().lower()
        self.assertTrue(u'caf\xe9.mp3 -> the title' in msg.decode('utf8'))

class DefaultPathTest(unittest.TestCase):
    def setUp(self):
        self.old_home = os.environ.get('HOME')
        self.old_appdata = os.environ.get('APPDATA')
        os.environ['HOME'] = 'xhome'
        os.environ['APPDATA'] = 'xappdata'
    def tearDown(self):
        if self.old_home is None:
            del os.environ['HOME']
        else:
            os.environ['HOME'] = self.old_home
        if self.old_appdata is None:
            del os.environ['APPDATA']
        else:
            os.environ['APPDATA'] = self.old_appdata

    def test_unix_paths_in_home(self):
        import posixpath
        config, lib, libdir = ui.default_paths(posixpath)
        self.assertEqual(config, 'xhome/.beetsconfig')
        self.assertEqual(lib, 'xhome/.beetsmusic.blb')
        self.assertEqual(libdir, 'xhome/Music')

    def test_windows_paths_in_home_and_appdata(self):
        import ntpath
        config, lib, libdir = ui.default_paths(ntpath)
        self.assertEqual(config, 'xappdata\\beetsconfig.ini')
        self.assertEqual(lib, 'xappdata\\beetsmusic.blb')
        self.assertEqual(libdir, 'xhome\\Music')

class PathFormatTest(unittest.TestCase):
    def _config(self, text):
        cp = ConfigParser.SafeConfigParser()
        cp.readfp(StringIO(text))
        return cp

    def _paths_for(self, text):
        return ui._get_path_formats(self._config("[paths]\n%s" %
                                                 textwrap.dedent(text)))

    def test_default_paths(self):
        pf = self._paths_for("")
        self.assertEqual(pf, ui.DEFAULT_PATH_FORMATS)

    def test_custom_paths_prepend(self):
        pf = self._paths_for("""
            foo: bar
        """)
        self.assertEqual(pf[0], ('foo', 'bar'))
        self.assertEqual(pf[1:], ui.DEFAULT_PATH_FORMATS)

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
