# This file is part of beets.
# Copyright 2014, Adrian Sampson.
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
import re
import subprocess
import platform

import _common
from _common import unittest
from helper import capture_stdout, has_program, TestHelper

from beets import library
from beets import ui
from beets.ui import commands
from beets import autotag
from beets.autotag.match import distance
from beets.mediafile import MediaFile
from beets import config
from beets import plugins
from beets.util.confit import ConfigError


class ListTest(unittest.TestCase):
    def setUp(self):
        self.lib = library.Library(':memory:')
        self.item = _common.item()
        self.item.path = 'xxx/yyy'
        self.lib.add(self.item)
        self.lib.add_album([self.item])

    def _run_list(self, query='', album=False, path=False, fmt=None):
        commands.list_items(self.lib, query, album, fmt)

    def test_list_outputs_item(self):
        with capture_stdout() as stdout:
            self._run_list()
        self.assertIn(u'the title', stdout.getvalue())

    def test_list_unicode_query(self):
        self.item.title = u'na\xefve'
        self.item.store()
        self.lib._connection().commit()

        with capture_stdout() as stdout:
            self._run_list([u'na\xefve'])
        out = stdout.getvalue()
        self.assertTrue(u'na\xefve' in out.decode(stdout.encoding))

    def test_list_item_path(self):
        with capture_stdout() as stdout:
            self._run_list(fmt='$path')
        self.assertEqual(stdout.getvalue().strip(), u'xxx/yyy')

    def test_list_album_outputs_something(self):
        with capture_stdout() as stdout:
            self._run_list(album=True)
        self.assertGreater(len(stdout.getvalue()), 0)

    def test_list_album_path(self):
        with capture_stdout() as stdout:
            self._run_list(album=True, fmt='$path')
        self.assertEqual(stdout.getvalue().strip(), u'xxx')

    def test_list_album_omits_title(self):
        with capture_stdout() as stdout:
            self._run_list(album=True)
        self.assertNotIn(u'the title', stdout.getvalue())

    def test_list_uses_track_artist(self):
        with capture_stdout() as stdout:
            self._run_list()
        self.assertIn(u'the artist', stdout.getvalue())
        self.assertNotIn(u'the album artist', stdout.getvalue())

    def test_list_album_uses_album_artist(self):
        with capture_stdout() as stdout:
            self._run_list(album=True)
        self.assertNotIn(u'the artist', stdout.getvalue())
        self.assertIn(u'the album artist', stdout.getvalue())

    def test_list_item_format_artist(self):
        with capture_stdout() as stdout:
            self._run_list(fmt='$artist')
        self.assertIn(u'the artist', stdout.getvalue())

    def test_list_item_format_multiple(self):
        with capture_stdout() as stdout:
            self._run_list(fmt='$artist - $album - $year')
        self.assertEqual(u'the artist - the album - 0001',
                         stdout.getvalue().strip())

    def test_list_album_format(self):
        with capture_stdout() as stdout:
            self._run_list(album=True, fmt='$genre')
        self.assertIn(u'the genre', stdout.getvalue())
        self.assertNotIn(u'the album', stdout.getvalue())


class RemoveTest(_common.TestCase):
    def setUp(self):
        super(RemoveTest, self).setUp()

        self.io.install()

        self.libdir = os.path.join(self.temp_dir, 'testlibdir')
        os.mkdir(self.libdir)

        # Copy a file into the library.
        self.lib = library.Library(':memory:', self.libdir)
        self.i = library.Item.from_path(os.path.join(_common.RSRC, 'full.mp3'))
        self.lib.add(self.i)
        self.i.move(True)

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
        self.lib.add(self.i)
        self.i.move(copy=True)
        self.album = self.lib.add_album([self.i])

    def _modify(self, mods=(), dels=(), query=(), write=False, move=False,
                album=False):
        self.io.addinput('y')
        commands.modify_items(self.lib, mods, dels, query,
                              write, move, album, True)

    def test_modify_item_dbdata(self):
        self._modify(["title=newTitle"])
        item = self.lib.items().get()
        self.assertEqual(item.title, 'newTitle')

    def test_modify_album_dbdata(self):
        self._modify(["album=newAlbum"], album=True)
        album = self.lib.albums()[0]
        self.assertEqual(album.album, 'newAlbum')

    def test_modify_item_tag_unmodified(self):
        self._modify(["title=newTitle"], write=False)
        item = self.lib.items().get()
        item.read()
        self.assertEqual(item.title, 'full')

    def test_modify_album_tag_unmodified(self):
        self._modify(["album=newAlbum"], write=False, album=True)
        item = self.lib.items().get()
        item.read()
        self.assertEqual(item.album, 'the album')

    def test_modify_item_tag(self):
        self._modify(["title=newTitle"], write=True)
        item = self.lib.items().get()
        item.read()
        self.assertEqual(item.title, 'newTitle')

    def test_modify_album_tag(self):
        self._modify(["album=newAlbum"], write=True, album=True)
        item = self.lib.items().get()
        item.read()
        self.assertEqual(item.album, 'newAlbum')

    def test_item_move(self):
        self._modify(["title=newTitle"], move=True)
        item = self.lib.items().get()
        self.assertTrue('newTitle' in item.path)

    def test_album_move(self):
        self._modify(["album=newAlbum"], move=True, album=True)
        item = self.lib.items().get()
        item.read()
        self.assertTrue('newAlbum' in item.path)

    def test_item_not_move(self):
        self._modify(["title=newTitle"], move=False)
        item = self.lib.items().get()
        self.assertFalse('newTitle' in item.path)

    def test_album_not_move(self):
        self._modify(["album=newAlbum"], move=False, album=True)
        item = self.lib.items().get()
        item.read()
        self.assertFalse('newAlbum' in item.path)

    def test_write_initial_key_tag(self):
        self._modify(["initial_key=C#m"], write=True)
        item = self.lib.items().get()
        mediafile = MediaFile(item.path)
        self.assertEqual(mediafile.initial_key, 'C#m')

    def test_remove_flexattr(self):
        self._modify(["flexattr=testAttr"], write=True)
        item = self.lib.items().get()
        self.assertEqual(item.flexattr, 'testAttr')
        self._modify(dels=["flexattr"], write=True)
        item = self.lib.items().get()
        self.assertTrue("flexattr" not in item)

    @unittest.skip('not yet implemented')
    def test_delete_initial_key_tag(self):
        item = self.i
        item.initial_key = 'C#m'
        item.write()
        item.store()

        mediafile = MediaFile(item.path)
        self.assertEqual(mediafile.initial_key, 'C#m')

        self._modify(dels=["initial_key!"], write=True)
        mediafile = MediaFile(item.path)
        self.assertIsNone(mediafile.initial_key)

    def test_arg_parsing_colon_query(self):
        (query, mods, dels) = commands.modify_parse_args(["title:oldTitle",
                                                          "title=newTitle"])
        self.assertEqual(query, ["title:oldTitle"])
        self.assertEqual(mods, ["title=newTitle"])

    def test_arg_parsing_delete(self):
        (query, mods, dels) = commands.modify_parse_args(["title:oldTitle",
                                                          "title!"])
        self.assertEqual(query, ["title:oldTitle"])
        self.assertEqual(dels, ["title"])

    def test_arg_parsing_query_with_exclaimation(self):
        (query, mods, dels) = commands.modify_parse_args(["title:oldTitle!",
                                                          "title=newTitle!"])
        self.assertEqual(query, ["title:oldTitle!"])
        self.assertEqual(mods, ["title=newTitle!"])

    def test_arg_parsing_equals_in_value(self):
        (query, mods, dels) = commands.modify_parse_args(["title:foo=bar",
                                                          "title=newTitle"])
        self.assertEqual(query, ["title:foo=bar"])
        self.assertEqual(mods, ["title=newTitle"])


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
        self.lib.add(self.i)
        self.album = self.lib.add_album([self.i])

        # Alternate destination directory.
        self.otherdir = os.path.join(self.temp_dir, 'testotherdir')

    def _move(self, query=(), dest=None, copy=False, album=False):
        commands.move_items(self.lib, dest, query, copy, album)

    def test_move_item(self):
        self._move()
        self.i.load()
        self.assertTrue('testlibdir' in self.i.path)
        self.assertExists(self.i.path)
        self.assertNotExists(self.itempath)

    def test_copy_item(self):
        self._move(copy=True)
        self.i.load()
        self.assertTrue('testlibdir' in self.i.path)
        self.assertExists(self.i.path)
        self.assertExists(self.itempath)

    def test_move_album(self):
        self._move(album=True)
        self.i.load()
        self.assertTrue('testlibdir' in self.i.path)
        self.assertExists(self.i.path)
        self.assertNotExists(self.itempath)

    def test_copy_album(self):
        self._move(copy=True, album=True)
        self.i.load()
        self.assertTrue('testlibdir' in self.i.path)
        self.assertExists(self.i.path)
        self.assertExists(self.itempath)

    def test_move_item_custom_dir(self):
        self._move(dest=self.otherdir)
        self.i.load()
        self.assertTrue('testotherdir' in self.i.path)
        self.assertExists(self.i.path)
        self.assertNotExists(self.itempath)

    def test_move_album_custom_dir(self):
        self._move(dest=self.otherdir, album=True)
        self.i.load()
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
        self.lib.add(self.i)
        self.i.move(True)
        self.album = self.lib.add_album([self.i])

        # Album art.
        artfile = os.path.join(self.temp_dir, 'testart.jpg')
        _common.touch(artfile)
        self.album.set_art(artfile)
        self.album.store()
        os.remove(artfile)

    def _update(self, query=(), album=False, move=False, reset_mtime=True):
        self.io.addinput('y')
        if reset_mtime:
            self.i.mtime = 0
            self.i.store()
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
        item = self.lib.items().get()
        self.assertEqual(item.title, 'differentTitle')

    def test_modified_metadata_moved(self):
        mf = MediaFile(self.i.path)
        mf.title = 'differentTitle'
        mf.save()
        self._update(move=True)
        item = self.lib.items().get()
        self.assertTrue('differentTitle' in item.path)

    def test_modified_metadata_not_moved(self):
        mf = MediaFile(self.i.path)
        mf.title = 'differentTitle'
        mf.save()
        self._update(move=False)
        item = self.lib.items().get()
        self.assertTrue('differentTitle' not in item.path)

    def test_modified_album_metadata_moved(self):
        mf = MediaFile(self.i.path)
        mf.album = 'differentAlbum'
        mf.save()
        self._update(move=True)
        item = self.lib.items().get()
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
        self.i.store()

        self._update(reset_mtime=False)
        item = self.lib.items().get()
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


class ConfigTest(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_beets()

        # Don't use the BEETSDIR from `helper`. Instead, we point the home
        # directory there. Some tests will set `BEETSDIR` themselves.
        del os.environ['BEETSDIR']
        self._old_home = os.environ.get('HOME')
        os.environ['HOME'] = self.temp_dir

        self._orig_cwd = os.getcwd()
        self.test_cmd = self._make_test_cmd()
        commands.default_commands.append(self.test_cmd)

        # Default user configuration
        if platform.system() == 'Windows':
            self.user_config_dir = os.path.join(
                self.temp_dir, 'AppData', 'Roaming', 'beets'
            )
        else:
            self.user_config_dir = os.path.join(
                self.temp_dir, '.config', 'beets'
            )
        os.makedirs(self.user_config_dir)
        self.user_config_path = os.path.join(self.user_config_dir,
                                             'config.yaml')

        # Custom BEETSDIR
        self.beetsdir = os.path.join(self.temp_dir, 'beetsdir')
        os.makedirs(self.beetsdir)

        self._reset_config()

    def tearDown(self):
        commands.default_commands.pop()
        os.chdir(self._orig_cwd)
        os.environ['HOME'] = self._old_home
        self.teardown_beets()

    def _make_test_cmd(self):
        test_cmd = ui.Subcommand('test', help='test')

        def run(lib, options, args):
            test_cmd.lib = lib
            test_cmd.options = options
            test_cmd.args = args

        test_cmd.func = run
        return test_cmd

    def _reset_config(self):
        # Config should read files again on demand
        config.clear()
        config._materialized = False

    def write_config_file(self):
        return open(self.user_config_path, 'w')

    def test_paths_section_respected(self):
        with self.write_config_file() as config:
            config.write('paths: {x: y}')

        ui._raw_main(['test'])
        key, template = self.test_cmd.lib.path_formats[0]
        self.assertEqual(key, 'x')
        self.assertEqual(template.original, 'y')

    def test_default_paths_preserved(self):
        default_formats = ui.get_path_formats()

        self._reset_config()
        with self.write_config_file() as config:
            config.write('paths: {x: y}')

        ui._raw_main(['test'])
        key, template = self.test_cmd.lib.path_formats[0]
        self.assertEqual(key, 'x')
        self.assertEqual(template.original, 'y')
        self.assertEqual(self.test_cmd.lib.path_formats[1:],
                         default_formats)

    def test_nonexistant_db(self):
        with self.write_config_file() as config:
            config.write('library: /xxx/yyy/not/a/real/path')

        with self.assertRaises(ui.UserError):
            ui._raw_main(['test'])

    def test_user_config_file(self):
        with self.write_config_file() as file:
            file.write('anoption: value')

        ui._raw_main(['test'])
        self.assertEqual(config['anoption'].get(), 'value')

    def test_replacements_parsed(self):
        with self.write_config_file() as config:
            config.write("replace: {'[xy]': z}")

        ui._raw_main(['test'])
        replacements = self.test_cmd.lib.replacements
        self.assertEqual(replacements, [(re.compile(ur'[xy]'), u'z')])

    def test_multiple_replacements_parsed(self):
        with self.write_config_file() as config:
            config.write("replace: {'[xy]': z, foo: bar}")

        ui._raw_main(['test'])
        replacements = self.test_cmd.lib.replacements
        self.assertEqual(replacements, [
            (re.compile(ur'[xy]'), u'z'),
            (re.compile(ur'foo'), u'bar'),
        ])

    def test_cli_config_option(self):
        config_path = os.path.join(self.temp_dir, 'config.yaml')
        with open(config_path, 'w') as file:
            file.write('anoption: value')

        ui._raw_main(['--config', config_path, 'test'])
        self.assertEqual(config['anoption'].get(), 'value')

    def test_cli_config_file_overwrites_user_defaults(self):
        with open(self.user_config_path, 'w') as file:
            file.write('anoption: value')

        cli_config_path = os.path.join(self.temp_dir, 'config.yaml')
        with open(cli_config_path, 'w') as file:
            file.write('anoption: cli overwrite')

        ui._raw_main(['--config', cli_config_path, 'test'])
        self.assertEqual(config['anoption'].get(), 'cli overwrite')

    def test_cli_config_file_overwrites_beetsdir_defaults(self):
        os.environ['BEETSDIR'] = self.beetsdir
        env_config_path = os.path.join(self.beetsdir, 'config.yaml')
        with open(env_config_path, 'w') as file:
            file.write('anoption: value')

        cli_config_path = os.path.join(self.temp_dir, 'config.yaml')
        with open(cli_config_path, 'w') as file:
            file.write('anoption: cli overwrite')

        ui._raw_main(['--config', cli_config_path, 'test'])
        self.assertEqual(config['anoption'].get(), 'cli overwrite')

#    @unittest.skip('Difficult to implement with optparse')
#    def test_multiple_cli_config_files(self):
#        cli_config_path_1 = os.path.join(self.temp_dir, 'config.yaml')
#        cli_config_path_2 = os.path.join(self.temp_dir, 'config_2.yaml')
#
#        with open(cli_config_path_1, 'w') as file:
#            file.write('first: value')
#
#        with open(cli_config_path_2, 'w') as file:
#            file.write('second: value')
#
#        ui._raw_main(['--config', cli_config_path_1,
#                      '--config', cli_config_path_2, 'test'])
#        self.assertEqual(config['first'].get(), 'value')
#        self.assertEqual(config['second'].get(), 'value')
#
#    @unittest.skip('Difficult to implement with optparse')
#    def test_multiple_cli_config_overwrite(self):
#        cli_config_path = os.path.join(self.temp_dir, 'config.yaml')
#        cli_overwrite_config_path = os.path.join(self.temp_dir,
#                                                 'overwrite_config.yaml')
#
#        with open(cli_config_path, 'w') as file:
#            file.write('anoption: value')
#
#        with open(cli_overwrite_config_path, 'w') as file:
#            file.write('anoption: overwrite')
#
#        ui._raw_main(['--config', cli_config_path,
#                      '--config', cli_overwrite_config_path, 'test'])
#        self.assertEqual(config['anoption'].get(), 'cli overwrite')

    def test_cli_config_paths_resolve_relative_to_user_dir(self):
        cli_config_path = os.path.join(self.temp_dir, 'config.yaml')
        with open(cli_config_path, 'w') as file:
            file.write('library: beets.db\n')
            file.write('statefile: state')

        ui._raw_main(['--config', cli_config_path, 'test'])
        self.assertEqual(config['library'].as_filename(),
                         os.path.join(self.user_config_dir, 'beets.db'))
        self.assertEqual(config['statefile'].as_filename(),
                         os.path.join(self.user_config_dir, 'state'))

    def test_cli_config_paths_resolve_relative_to_beetsdir(self):
        os.environ['BEETSDIR'] = self.beetsdir

        cli_config_path = os.path.join(self.temp_dir, 'config.yaml')
        with open(cli_config_path, 'w') as file:
            file.write('library: beets.db\n')
            file.write('statefile: state')

        ui._raw_main(['--config', cli_config_path, 'test'])
        self.assertEqual(config['library'].as_filename(),
                         os.path.join(self.beetsdir, 'beets.db'))
        self.assertEqual(config['statefile'].as_filename(),
                         os.path.join(self.beetsdir, 'state'))

    def test_command_line_option_relative_to_working_dir(self):
        os.chdir(self.temp_dir)
        ui._raw_main(['--library', 'foo.db', 'test'])
        self.assertEqual(config['library'].as_filename(),
                         os.path.join(os.getcwd(), 'foo.db'))

    def test_cli_config_file_loads_plugin_commands(self):
        plugin_path = os.path.join(_common.RSRC, 'beetsplug')

        cli_config_path = os.path.join(self.temp_dir, 'config.yaml')
        with open(cli_config_path, 'w') as file:
            file.write('pluginpath: %s\n' % plugin_path)
            file.write('plugins: test')

        ui._raw_main(['--config', cli_config_path, 'plugin'])
        self.assertTrue(plugins.find_plugins()[0].is_test_plugin)

    def test_beetsdir_config(self):
        os.environ['BEETSDIR'] = self.beetsdir

        env_config_path = os.path.join(self.beetsdir, 'config.yaml')
        with open(env_config_path, 'w') as file:
            file.write('anoption: overwrite')

        config.read()
        self.assertEqual(config['anoption'].get(), 'overwrite')

    def test_beetsdir_points_to_file_error(self):
        beetsdir = os.path.join(self.temp_dir, 'beetsfile')
        open(beetsdir, 'a').close()
        os.environ['BEETSDIR'] = beetsdir
        self.assertRaises(ConfigError, ui._raw_main, 'test')

    def test_beetsdir_config_does_not_load_default_user_config(self):
        os.environ['BEETSDIR'] = self.beetsdir

        with open(self.user_config_path, 'w') as file:
            file.write('anoption: value')

        config.read()
        self.assertFalse(config['anoption'].exists())

    def test_default_config_paths_resolve_relative_to_beetsdir(self):
        os.environ['BEETSDIR'] = self.beetsdir

        config.read()
        self.assertEqual(config['library'].as_filename(),
                         os.path.join(self.beetsdir, 'library.db'))
        self.assertEqual(config['statefile'].as_filename(),
                         os.path.join(self.beetsdir, 'state.pickle'))

    def test_beetsdir_config_paths_resolve_relative_to_beetsdir(self):
        os.environ['BEETSDIR'] = self.beetsdir

        env_config_path = os.path.join(self.beetsdir, 'config.yaml')
        with open(env_config_path, 'w') as file:
            file.write('library: beets.db\n')
            file.write('statefile: state')

        config.read()
        self.assertEqual(config['library'].as_filename(),
                         os.path.join(self.beetsdir, 'beets.db'))
        self.assertEqual(config['statefile'].as_filename(),
                         os.path.join(self.beetsdir, 'state'))


class ShowModelChangeTest(_common.TestCase):
    def setUp(self):
        super(ShowModelChangeTest, self).setUp()
        self.io.install()
        self.a = _common.item()
        self.b = _common.item()
        self.a.path = self.b.path

    def _show(self, **kwargs):
        change = ui.show_model_changes(self.a, self.b, **kwargs)
        out = self.io.getoutput()
        return change, out

    def test_identical(self):
        change, out = self._show()
        self.assertFalse(change)
        self.assertEqual(out, '')

    def test_string_fixed_field_change(self):
        self.b.title = 'x'
        change, out = self._show()
        self.assertTrue(change)
        self.assertTrue('title' in out)

    def test_int_fixed_field_change(self):
        self.b.track = 9
        change, out = self._show()
        self.assertTrue(change)
        self.assertTrue('track' in out)

    def test_floats_close_to_identical(self):
        self.a.length = 1.00001
        self.b.length = 1.00005
        change, out = self._show()
        self.assertFalse(change)
        self.assertEqual(out, '')

    def test_floats_different(self):
        self.a.length = 1.00001
        self.b.length = 2.00001
        change, out = self._show()
        self.assertTrue(change)
        self.assertTrue('length' in out)

    def test_both_values_shown(self):
        self.a.title = 'foo'
        self.b.title = 'bar'
        change, out = self._show()
        self.assertTrue('foo' in out)
        self.assertTrue('bar' in out)


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
            ]
        )

    def _show_change(self, items=None, info=None,
                     cur_artist=u'the artist', cur_album=u'the album',
                     dist=0.1):
        items = items or self.items
        info = info or self.info
        mapping = dict(zip(items, info.tracks))
        config['color'] = False
        album_dist = distance(items, info, mapping)
        album_dist._penalties = {'album': [dist]}
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


class PluginTest(_common.TestCase):
    def test_plugin_command_from_pluginpath(self):
        config['pluginpath'] = [os.path.join(_common.RSRC, 'beetsplug')]
        config['plugins'] = ['test']
        ui._raw_main(['test'])


class CompletionTest(_common.TestCase):
    def test_completion(self):
        # Load plugin commands
        config['pluginpath'] = [os.path.join(_common.RSRC, 'beetsplug')]
        config['plugins'] = ['test']

        test_script = os.path.join(
            os.path.dirname(__file__), 'test_completion.sh'
        )
        bash_completion = os.path.abspath(os.environ.get(
            'BASH_COMPLETION_SCRIPT', '/etc/bash_completion'))

        # Tests run in bash
        cmd = os.environ.get('BEETS_TEST_SHELL', '/bin/bash --norc').split()
        if not has_program(cmd[0]):
            self.skipTest('bash not available')
        tester = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE)

        # Load bash_completion
        try:
            with open(bash_completion, 'r') as bash_completion:
                tester.stdin.writelines(bash_completion)
        except IOError:
            self.skipTest('bash-completion script not found')

        # Load complection script
        self.io.install()
        ui._raw_main(['completion'])
        completion_script = self.io.getoutput()
        self.io.restore()
        tester.stdin.writelines(completion_script)

        # Load testsuite
        with open(test_script, 'r') as test_script:
            tester.stdin.writelines(test_script)
        (out, err) = tester.communicate()
        if tester.returncode != 0 or out != "completion tests passed\n":
            print(out)
            self.fail('test/test_completion.sh did not execute properly')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
