# This file is part of beets.
# Copyright 2013, Adrian Sampson.
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
import os
import shutil
import textwrap
import logging
import re
import yaml

import _common
from _common import unittest
from beets import library
from beets import ui
from beets.ui import commands
from beets import autotag
from beets.autotag.match import distance
from beets import importer
from beets.mediafile import MediaFile
from beets import config
from beets.util import confit

class ListTest(_common.TestCase):
    def setUp(self):
        super(ListTest, self).setUp()
        self.io.install()

        self.lib = library.Library(':memory:')
        i = _common.item()
        i.path = 'xxx/yyy'
        self.lib.add(i)
        self.lib.add_album([i])
        self.item = i

    def _run_list(self, query='', album=False, path=False, fmt=None):
        commands.list_items(self.lib, query, album, fmt)

    def test_list_outputs_item(self):
        self._run_list()
        out = self.io.getoutput()
        self.assertTrue(u'the title' in out)

    def test_list_unicode_query(self):
        self.item.title = u'na\xefve'
        self.lib.store(self.item)
        self.lib._connection().commit()

        self._run_list([u'na\xefve'])
        out = self.io.getoutput()
        self.assertTrue(u'na\xefve' in out.decode(self.io.stdout.encoding))

    def test_list_item_path(self):
        self._run_list(fmt='$path')
        out = self.io.getoutput()
        self.assertEqual(out.strip(), u'xxx/yyy')

    def test_list_album_outputs_something(self):
        self._run_list(album=True)
        out = self.io.getoutput()
        self.assertGreater(len(out), 0)

    def test_list_album_path(self):
        self._run_list(album=True, fmt='$path')
        out = self.io.getoutput()
        self.assertEqual(out.strip(), u'xxx')

    def test_list_album_omits_title(self):
        self._run_list(album=True)
        out = self.io.getoutput()
        self.assertTrue(u'the title' not in out)

    def test_list_uses_track_artist(self):
        self._run_list()
        out = self.io.getoutput()
        self.assertTrue(u'the artist' in out)
        self.assertTrue(u'the album artist' not in out)

    def test_list_album_uses_album_artist(self):
        self._run_list(album=True)
        out = self.io.getoutput()
        self.assertTrue(u'the artist' not in out)
        self.assertTrue(u'the album artist' in out)

    def test_list_item_format_artist(self):
        self._run_list(fmt='$artist')
        out = self.io.getoutput()
        self.assertTrue(u'the artist' in out)

    def test_list_item_format_multiple(self):
        self._run_list(fmt='$artist - $album - $year')
        out = self.io.getoutput()
        self.assertTrue(u'1' in out)
        self.assertTrue(u'the album' in out)
        self.assertTrue(u'the artist' in out)
        self.assertEqual(u'the artist - the album - 1', out.strip())

    def test_list_album_format(self):
        self._run_list(album=True, fmt='$genre')
        out = self.io.getoutput()
        self.assertTrue(u'the genre' in out)
        self.assertTrue(u'the album' not in out)

class RemoveTest(_common.TestCase):
    def setUp(self):
        super(RemoveTest, self).setUp()

        self.io.install()

        self.libdir = os.path.join(self.temp_dir, 'testlibdir')
        os.mkdir(self.libdir)

        # Copy a file into the library.
        self.lib = library.Library(':memory:', self.libdir)
        self.i = library.Item.from_path(os.path.join(_common.RSRC, 'full.mp3'))
        self.lib.add(self.i, True)

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

class ModifyTest(_common.TestCase):
    def setUp(self):
        super(ModifyTest, self).setUp()

        self.io.install()

        self.libdir = os.path.join(self.temp_dir, 'testlibdir')

        # Copy a file into the library.
        self.lib = library.Library(':memory:', self.libdir)
        self.i = library.Item.from_path(os.path.join(_common.RSRC, 'full.mp3'))
        self.lib.add(self.i, True)
        self.album = self.lib.add_album([self.i])

    def _modify(self, mods, query=(), write=False, move=False, album=False):
        self.io.addinput('y')
        commands.modify_items(self.lib, mods, query,
                              write, move, album, True)

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

class MoveTest(_common.TestCase):
    def setUp(self):
        super(MoveTest, self).setUp()

        self.io.install()

        self.libdir = os.path.join(self.temp_dir, 'testlibdir')
        os.mkdir(self.libdir)

        self.itempath = os.path.join(self.libdir, 'srcfile')
        shutil.copy(os.path.join(_common.RSRC, 'full.mp3'), self.itempath)

        # Add a file to the library but don't copy it in yet.
        self.lib = library.Library(':memory:', self.libdir)
        self.i = library.Item.from_path(self.itempath)
        self.lib.add(self.i, False)
        self.album = self.lib.add_album([self.i])

        # Alternate destination directory.
        self.otherdir = os.path.join(self.temp_dir, 'testotherdir')

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

class UpdateTest(_common.TestCase):
    def setUp(self):
        super(UpdateTest, self).setUp()

        self.io.install()

        self.libdir = os.path.join(self.temp_dir, 'testlibdir')

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

    def _update(self, query=(), album=False, move=False, reset_mtime=True):
        self.io.addinput('y')
        if reset_mtime:
            self.i.mtime = 0
            self.lib.store(self.i)
        commands.update_items(self.lib, query, album, move, False)

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

class PrintTest(_common.TestCase):
    def setUp(self):
        super(PrintTest, self).setUp()
        self.io.install()

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

class AutotagTest(_common.TestCase):
    def setUp(self):
        super(AutotagTest, self).setUp()
        self.io.install()

    def _no_candidates_test(self, result):
        task = importer.ImportTask(
            'toppath',
            'path',
            [_common.item()],
        )
        task.set_candidates('artist', 'album', [], autotag.recommendation.none)
        session = _common.import_session(cli=True)
        res = session.choose_match(task)
        self.assertEqual(res, result)
        self.assertTrue('No match' in self.io.getoutput())

    def test_choose_match_with_no_candidates_skip(self):
        self.io.addinput('s')
        self._no_candidates_test(importer.action.SKIP)

    def test_choose_match_with_no_candidates_asis(self):
        self.io.addinput('u')
        self._no_candidates_test(importer.action.ASIS)

class ImportTest(_common.TestCase):
    def test_quiet_timid_disallowed(self):
        config['import']['quiet'] = True
        config['import']['timid'] = True
        self.assertRaises(ui.UserError, commands.import_files, None, [],
                          None)

class InputTest(_common.TestCase):
    def setUp(self):
        super(InputTest, self).setUp()
        self.io.install()

    def test_manual_search_gets_unicode(self):
        self.io.addinput('\xc3\x82me')
        self.io.addinput('\xc3\x82me')
        artist, album = commands.manual_search(False)
        self.assertEqual(artist, u'\xc2me')
        self.assertEqual(album, u'\xc2me')

class ConfigTest(_common.TestCase):
    def setUp(self):
        super(ConfigTest, self).setUp()
        self.io.install()
        self.test_cmd = ui.Subcommand('test', help='test')
        commands.default_commands.append(self.test_cmd)
    def tearDown(self):
        super(ConfigTest, self).tearDown()
        commands.default_commands.pop()
    def _run_main(self, args, config_yaml, func):
        self.test_cmd.func = func
        config_yaml = textwrap.dedent(config_yaml).strip()
        if config_yaml:
            config_data = yaml.load(config_yaml, Loader=confit.Loader)
            config.set(config_data)
        ui._raw_main(args + ['test'])

    def test_paths_section_respected(self):
        def func(lib, opts, args):
            key, template = lib.path_formats[0]
            self.assertEqual(key, 'x')
            self.assertEqual(template.original, 'y')
        self._run_main([], """
            paths:
                x: y
        """, func)

    def test_default_paths_preserved(self):
        default_formats = ui.get_path_formats()
        def func(lib, opts, args):
            self.assertEqual(lib.path_formats[1:],
                             default_formats)
        self._run_main([], """
            paths:
                x: y
        """, func)

    def test_nonexistant_config_file(self):
        os.environ['BEETSCONFIG'] = '/xxxxx'
        ui.main(['version'])

    def test_nonexistant_db(self):
        def func(lib, opts, args):
            pass
        with self.assertRaises(ui.UserError):
            self._run_main([], """
                library: /xxx/yyy/not/a/real/path
            """, func)

    def test_replacements_parsed(self):
        def func(lib, opts, args):
            replacements = lib.replacements
            self.assertEqual(replacements, [(re.compile(ur'[xy]'), u'z')])
        self._run_main([], """
            replace:
                '[xy]': z
        """, func)

    def test_multiple_replacements_parsed(self):
        def func(lib, opts, args):
            replacements = lib.replacements
            self.assertEqual(replacements, [
                (re.compile(ur'[xy]'), u'z'),
                (re.compile(ur'foo'), u'bar'),
            ])
        self._run_main([], """
            replace:
                '[xy]': z
                foo: bar
        """, func)

class ShowdiffTest(_common.TestCase):
    def setUp(self):
        super(ShowdiffTest, self).setUp()
        self.io.install()

    def test_showdiff_strings(self):
        commands._showdiff('field', 'old', 'new')
        out = self.io.getoutput()
        self.assertTrue('field' in out)

    def test_showdiff_identical(self):
        commands._showdiff('field', 'old', 'old')
        out = self.io.getoutput()
        self.assertFalse('field' in out)

    def test_showdiff_ints(self):
        commands._showdiff('field', 2, 3)
        out = self.io.getoutput()
        self.assertTrue('field' in out)

    def test_showdiff_ints_no_color(self):
        config['color'] = False
        commands._showdiff('field', 2, 3)
        out = self.io.getoutput()
        self.assertTrue('field' in out)

    def test_showdiff_shows_both(self):
        commands._showdiff('field', 'old', 'new')
        out = self.io.getoutput()
        self.assertTrue('old' in out)
        self.assertTrue('new' in out)

    def test_showdiff_floats_close_to_identical(self):
        commands._showdiff('field', 1.999, 2.001)
        out = self.io.getoutput()
        self.assertFalse('field' in out)

    def test_showdiff_floats_differenct(self):
        commands._showdiff('field', 1.999, 4.001)
        out = self.io.getoutput()
        self.assertTrue('field' in out)

    def test_showdiff_ints_colorizing_is_not_stringwise(self):
        commands._showdiff('field', 222, 333)
        complete_diff = self.io.getoutput().split()[1]

        commands._showdiff('field', 222, 232)
        partial_diff = self.io.getoutput().split()[1]

        self.assertEqual(complete_diff, partial_diff)

class ShowChangeTest(_common.TestCase):
    def setUp(self):
        super(ShowChangeTest, self).setUp()
        self.io.install()

        self.items = [_common.item()]
        self.items[0].track = 1
        self.items[0].path = '/path/to/file.mp3'
        self.info = autotag.AlbumInfo(
            u'the album', u'album id', u'the artist', u'artist id', [
                autotag.TrackInfo(u'the title', u'track id', index=1)
        ])

    def _show_change(self, items=None, info=None,
                     cur_artist=u'the artist', cur_album=u'the album',
                     dist=0.1):
        items = items or self.items
        info = info or self.info
        mapping = dict(zip(items, info.tracks))
        config['color'] = False
        album_dist = distance(items, info, mapping)
        album_dist.penalties = {'album': [dist]}
        commands.show_change(
            cur_artist,
            cur_album,
            autotag.AlbumMatch(album_dist, info, mapping, set(), set()),
        )
        return self.io.getoutput().lower()

    def test_null_change(self):
        msg = self._show_change()
        self.assertTrue('similarity: 90' in msg)
        self.assertTrue('tagging:' in msg)

    def test_album_data_change(self):
        msg = self._show_change(cur_artist='another artist',
                                cur_album='another album')
        self.assertTrue('correcting tags from:' in msg)

    def test_item_data_change(self):
        self.items[0].title = u'different'
        msg = self._show_change()
        self.assertTrue('different -> the title' in msg)

    def test_item_data_change_with_unicode(self):
        self.items[0].title = u'caf\xe9'
        msg = self._show_change()
        self.assertTrue(u'caf\xe9 -> the title' in msg.decode('utf8'))

    def test_album_data_change_with_unicode(self):
        msg = self._show_change(cur_artist=u'caf\xe9',
                                cur_album=u'another album')
        self.assertTrue('correcting tags from:' in msg)

    def test_item_data_change_title_missing(self):
        self.items[0].title = u''
        msg = re.sub(r'  +', ' ', self._show_change())
        self.assertTrue('file.mp3 -> the title' in msg)

    def test_item_data_change_title_missing_with_unicode_filename(self):
        self.items[0].title = u''
        self.items[0].path = u'/path/to/caf\xe9.mp3'.encode('utf8')
        msg = re.sub(r'  +', ' ', self._show_change().decode('utf8'))
        self.assertTrue(u'caf\xe9.mp3 -> the title' in msg
                        or u'caf.mp3 ->' in msg)

class PathFormatTest(_common.TestCase):
    def test_custom_paths_prepend(self):
        default_formats = ui.get_path_formats()

        config['paths'] = {u'foo': u'bar'}
        pf = ui.get_path_formats()
        key, tmpl = pf[0]
        self.assertEqual(key, 'foo')
        self.assertEqual(tmpl.original, 'bar')
        self.assertEqual(pf[1:], default_formats)

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
