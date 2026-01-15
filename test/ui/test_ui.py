# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

"""Tests for the command-line interface."""

import os
import platform
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest
from confuse import ConfigError

from beets import config, plugins, ui
from beets.test import _common
from beets.test.helper import BeetsTestCase, IOMixin, PluginTestCase
from beets.ui import commands
from beets.util import syspath


class PrintTest(IOMixin, unittest.TestCase):
    def test_print_without_locale(self):
        lang = os.environ.get("LANG")
        if lang:
            del os.environ["LANG"]

        try:
            ui.print_("something")
        except TypeError:
            self.fail("TypeError during print")
        finally:
            if lang:
                os.environ["LANG"] = lang

    def test_print_with_invalid_locale(self):
        old_lang = os.environ.get("LANG")
        os.environ["LANG"] = ""
        old_ctype = os.environ.get("LC_CTYPE")
        os.environ["LC_CTYPE"] = "UTF-8"

        try:
            ui.print_("something")
        except ValueError:
            self.fail("ValueError during print")
        finally:
            if old_lang:
                os.environ["LANG"] = old_lang
            else:
                del os.environ["LANG"]
            if old_ctype:
                os.environ["LC_CTYPE"] = old_ctype
            else:
                del os.environ["LC_CTYPE"]


@_common.slow_test()
class TestPluginTestCase(PluginTestCase):
    plugin = "test"

    def setUp(self):
        self.config["pluginpath"] = [_common.PLUGINPATH]
        super().setUp()


class ConfigTest(IOMixin, TestPluginTestCase):
    def setUp(self):
        super().setUp()

        # Don't use the BEETSDIR from `helper`. Instead, we point the home
        # directory there. Some tests will set `BEETSDIR` themselves.
        del os.environ["BEETSDIR"]

        # Also set APPDATA, the Windows equivalent of setting $HOME.
        appdata_dir = self.temp_dir_path / "AppData" / "Roaming"

        self._orig_cwd = os.getcwd()
        self.test_cmd = self._make_test_cmd()
        commands.default_commands.append(self.test_cmd)

        # Default user configuration
        if platform.system() == "Windows":
            self.user_config_dir = appdata_dir / "beets"
        else:
            self.user_config_dir = self.temp_dir_path / ".config" / "beets"
        self.user_config_dir.mkdir(parents=True, exist_ok=True)
        self.user_config_path = self.user_config_dir / "config.yaml"

        # Custom BEETSDIR
        self.beetsdir = self.temp_dir_path / "beetsdir"
        self.beetsdir.mkdir(parents=True, exist_ok=True)

        self.env_config_path = str(self.beetsdir / "config.yaml")
        self.cli_config_path = str(self.temp_dir_path / "config.yaml")
        self.env_patcher = patch(
            "os.environ",
            {"HOME": str(self.temp_dir_path), "APPDATA": str(appdata_dir)},
        )
        self.env_patcher.start()

        self._reset_config()

    def tearDown(self):
        self.env_patcher.stop()
        commands.default_commands.pop()
        os.chdir(syspath(self._orig_cwd))
        super().tearDown()

    def _make_test_cmd(self):
        test_cmd = ui.Subcommand("test", help="test")

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
        return open(self.user_config_path, "w")

    def test_paths_section_respected(self):
        with self.write_config_file() as config:
            config.write("paths: {x: y}")

        self.run_command("test", lib=None)
        key, template = self.test_cmd.lib.path_formats[0]
        assert key == "x"
        assert template.original == "y"

    def test_default_paths_preserved(self):
        default_formats = ui.get_path_formats()

        self._reset_config()
        with self.write_config_file() as config:
            config.write("paths: {x: y}")
        self.run_command("test", lib=None)
        key, template = self.test_cmd.lib.path_formats[0]
        assert key == "x"
        assert template.original == "y"
        assert self.test_cmd.lib.path_formats[1:] == default_formats

    def test_nonexistant_db(self):
        with self.write_config_file() as config:
            config.write("library: /xxx/yyy/not/a/real/path")

        self.io.addinput("n")
        with pytest.raises(ui.UserError):
            self.run_command("test", lib=None)

    def test_user_config_file(self):
        with self.write_config_file() as file:
            file.write("anoption: value")

        self.run_command("test", lib=None)
        assert config["anoption"].get() == "value"

    def test_replacements_parsed(self):
        with self.write_config_file() as config:
            config.write("replace: {'[xy]': z}")

        self.run_command("test", lib=None)
        replacements = self.test_cmd.lib.replacements
        repls = [(p.pattern, s) for p, s in replacements]  # Compare patterns.
        assert repls == [("[xy]", "z")]

    def test_multiple_replacements_parsed(self):
        with self.write_config_file() as config:
            config.write("replace: {'[xy]': z, foo: bar}")
        self.run_command("test", lib=None)
        replacements = self.test_cmd.lib.replacements
        repls = [(p.pattern, s) for p, s in replacements]
        assert repls == [("[xy]", "z"), ("foo", "bar")]

    def test_cli_config_option(self):
        with open(self.cli_config_path, "w") as file:
            file.write("anoption: value")
        self.run_command("--config", self.cli_config_path, "test", lib=None)
        assert config["anoption"].get() == "value"

    def test_cli_config_file_overwrites_user_defaults(self):
        with open(self.user_config_path, "w") as file:
            file.write("anoption: value")

        with open(self.cli_config_path, "w") as file:
            file.write("anoption: cli overwrite")
        self.run_command("--config", self.cli_config_path, "test", lib=None)
        assert config["anoption"].get() == "cli overwrite"

    def test_cli_config_file_overwrites_beetsdir_defaults(self):
        os.environ["BEETSDIR"] = str(self.beetsdir)
        with open(self.env_config_path, "w") as file:
            file.write("anoption: value")

        with open(self.cli_config_path, "w") as file:
            file.write("anoption: cli overwrite")
        self.run_command("--config", self.cli_config_path, "test", lib=None)
        assert config["anoption"].get() == "cli overwrite"

    #    @unittest.skip('Difficult to implement with optparse')
    #    def test_multiple_cli_config_files(self):
    #        cli_config_path_1 = os.path.join(self.temp_dir, b'config.yaml')
    #        cli_config_path_2 = os.path.join(self.temp_dir, b'config_2.yaml')
    #
    #        with open(cli_config_path_1, 'w') as file:
    #            file.write('first: value')
    #
    #        with open(cli_config_path_2, 'w') as file:
    #            file.write('second: value')
    #
    #        self.run_command('--config', cli_config_path_1,
    #                      '--config', cli_config_path_2, 'test', lib=None)
    #        assert config['first'].get() == 'value'
    #        assert config['second'].get() == 'value'
    #
    #    @unittest.skip('Difficult to implement with optparse')
    #    def test_multiple_cli_config_overwrite(self):
    #        cli_overwrite_config_path = os.path.join(self.temp_dir,
    #                                                 b'overwrite_config.yaml')
    #
    #        with open(self.cli_config_path, 'w') as file:
    #            file.write('anoption: value')
    #
    #        with open(cli_overwrite_config_path, 'w') as file:
    #            file.write('anoption: overwrite')
    #
    #        self.run_command('--config', self.cli_config_path,
    #                      '--config', cli_overwrite_config_path, 'test')
    #        assert config['anoption'].get() == 'cli overwrite'

    # FIXME: fails on windows
    @unittest.skipIf(sys.platform == "win32", "win32")
    def test_cli_config_paths_resolve_relative_to_user_dir(self):
        with open(self.cli_config_path, "w") as file:
            file.write("library: beets.db\n")
            file.write("statefile: state")

        self.run_command("--config", self.cli_config_path, "test", lib=None)
        assert config["library"].as_path() == self.user_config_dir / "beets.db"
        assert config["statefile"].as_path() == self.user_config_dir / "state"

    def test_cli_config_paths_resolve_relative_to_beetsdir(self):
        os.environ["BEETSDIR"] = str(self.beetsdir)

        with open(self.cli_config_path, "w") as file:
            file.write("library: beets.db\n")
            file.write("statefile: state")

        self.run_command("--config", self.cli_config_path, "test", lib=None)
        assert config["library"].as_path() == self.beetsdir / "beets.db"
        assert config["statefile"].as_path() == self.beetsdir / "state"

    def test_command_line_option_relative_to_working_dir(self):
        config.read()
        os.chdir(syspath(self.temp_dir))
        self.run_command("--library", "foo.db", "test", lib=None)
        assert config["library"].as_path() == Path.cwd() / "foo.db"

    def test_cli_config_file_loads_plugin_commands(self):
        with open(self.cli_config_path, "w") as file:
            file.write(f"pluginpath: {_common.PLUGINPATH}\n")
            file.write("plugins: test")

        self.run_command("--config", self.cli_config_path, "plugin", lib=None)
        plugs = plugins.find_plugins()
        assert len(plugs) == 1
        assert plugs[0].is_test_plugin
        self.unload_plugins()

    def test_beetsdir_config(self):
        os.environ["BEETSDIR"] = str(self.beetsdir)

        with open(self.env_config_path, "w") as file:
            file.write("anoption: overwrite")

        config.read()
        assert config["anoption"].get() == "overwrite"

    def test_beetsdir_points_to_file_error(self):
        beetsdir = str(self.temp_dir_path / "beetsfile")
        open(beetsdir, "a").close()
        os.environ["BEETSDIR"] = beetsdir
        with pytest.raises(ConfigError):
            self.run_command("test")

    def test_beetsdir_config_does_not_load_default_user_config(self):
        os.environ["BEETSDIR"] = str(self.beetsdir)

        with open(self.user_config_path, "w") as file:
            file.write("anoption: value")

        config.read()
        assert not config["anoption"].exists()

    def test_default_config_paths_resolve_relative_to_beetsdir(self):
        os.environ["BEETSDIR"] = str(self.beetsdir)

        config.read()
        assert config["library"].as_path() == self.beetsdir / "library.db"
        assert config["statefile"].as_path() == self.beetsdir / "state.pickle"

    def test_beetsdir_config_paths_resolve_relative_to_beetsdir(self):
        os.environ["BEETSDIR"] = str(self.beetsdir)

        with open(self.env_config_path, "w") as file:
            file.write("library: beets.db\n")
            file.write("statefile: state")

        config.read()
        assert config["library"].as_path() == self.beetsdir / "beets.db"
        assert config["statefile"].as_path() == self.beetsdir / "state"


class ShowModelChangeTest(IOMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.a = _common.item()
        self.b = _common.item()
        self.a.path = self.b.path

    def _show(self, **kwargs):
        change = ui.show_model_changes(self.a, self.b, **kwargs)
        out = self.io.getoutput()
        return change, out

    def test_identical(self):
        change, out = self._show()
        assert not change
        assert out == ""

    def test_string_fixed_field_change(self):
        self.b.title = "x"
        change, out = self._show()
        assert change
        assert "title" in out

    def test_int_fixed_field_change(self):
        self.b.track = 9
        change, out = self._show()
        assert change
        assert "track" in out

    def test_floats_close_to_identical(self):
        self.a.length = 1.00001
        self.b.length = 1.00005
        change, out = self._show()
        assert not change
        assert out == ""

    def test_floats_different(self):
        self.a.length = 1.00001
        self.b.length = 2.00001
        change, out = self._show()
        assert change
        assert "length" in out

    def test_both_values_shown(self):
        self.a.title = "foo"
        self.b.title = "bar"
        _, out = self._show()
        assert "foo" in out
        assert "bar" in out


class PathFormatTest(unittest.TestCase):
    def test_custom_paths_prepend(self):
        default_formats = ui.get_path_formats()

        config["paths"] = {"foo": "bar"}
        pf = ui.get_path_formats()
        key, tmpl = pf[0]
        assert key == "foo"
        assert tmpl.original == "bar"
        assert pf[1:] == default_formats


@_common.slow_test()
class PluginTest(TestPluginTestCase):
    def test_plugin_command_from_pluginpath(self):
        self.run_command("test", lib=None)


class CommonOptionsParserCliTest(BeetsTestCase):
    """Test CommonOptionsParser and formatting LibModel formatting on 'list'
    command.
    """

    def setUp(self):
        super().setUp()
        self.item = _common.item()
        self.item.path = b"xxx/yyy"
        self.lib.add(self.item)
        self.lib.add_album([self.item])

    def test_base(self):
        output = self.run_with_output("ls")
        assert output == "the artist - the album - the title\n"

        output = self.run_with_output("ls", "-a")
        assert output == "the album artist - the album\n"

    def test_path_option(self):
        output = self.run_with_output("ls", "-p")
        assert output == "xxx/yyy\n"

        output = self.run_with_output("ls", "-a", "-p")
        assert output == "xxx\n"

    def test_format_option(self):
        output = self.run_with_output("ls", "-f", "$artist")
        assert output == "the artist\n"

        output = self.run_with_output("ls", "-a", "-f", "$albumartist")
        assert output == "the album artist\n"

    def test_format_option_unicode(self):
        output = self.run_with_output("ls", "-f", "caf\xe9")
        assert output == "caf\xe9\n"

    def test_root_format_option(self):
        output = self.run_with_output(
            "--format-item", "$artist", "--format-album", "foo", "ls"
        )
        assert output == "the artist\n"

        output = self.run_with_output(
            "--format-item", "foo", "--format-album", "$albumartist", "ls", "-a"
        )
        assert output == "the album artist\n"

    def test_help(self):
        output = self.run_with_output("help")
        assert "Usage:" in output

        output = self.run_with_output("help", "list")
        assert "Usage:" in output

        with pytest.raises(ui.UserError):
            self.run_command("help", "this.is.not.a.real.command")

    def test_stats(self):
        output = self.run_with_output("stats")
        assert "Approximate total size:" in output

        # # Need to have more realistic library setup for this to work
        # output = self.run_with_output('stats', '-e')
        # assert 'Total size:' in output

    def test_version(self):
        output = self.run_with_output("version")
        assert "Python version" in output
        assert "no plugins loaded" in output

        # # Need to have plugin loaded
        # output = self.run_with_output('version')
        # assert 'plugins: ' in output


class CommonOptionsParserTest(unittest.TestCase):
    def test_album_option(self):
        parser = ui.CommonOptionsParser()
        assert not parser._album_flags
        parser.add_album_option()
        assert bool(parser._album_flags)

        assert parser.parse_args([]) == ({"album": None}, [])
        assert parser.parse_args(["-a"]) == ({"album": True}, [])
        assert parser.parse_args(["--album"]) == ({"album": True}, [])

    def test_path_option(self):
        parser = ui.CommonOptionsParser()
        parser.add_path_option()
        assert not parser._album_flags

        config["format_item"].set("$foo")
        assert parser.parse_args([]) == ({"path": None}, [])
        assert config["format_item"].as_str() == "$foo"

        assert parser.parse_args(["-p"]) == (
            {"path": True, "format": "$path"},
            [],
        )
        assert parser.parse_args(["--path"]) == (
            {"path": True, "format": "$path"},
            [],
        )

        assert config["format_item"].as_str() == "$path"
        assert config["format_album"].as_str() == "$path"

    def test_format_option(self):
        parser = ui.CommonOptionsParser()
        parser.add_format_option()
        assert not parser._album_flags

        config["format_item"].set("$foo")
        assert parser.parse_args([]) == ({"format": None}, [])
        assert config["format_item"].as_str() == "$foo"

        assert parser.parse_args(["-f", "$bar"]) == ({"format": "$bar"}, [])
        assert parser.parse_args(["--format", "$baz"]) == (
            {"format": "$baz"},
            [],
        )

        assert config["format_item"].as_str() == "$baz"
        assert config["format_album"].as_str() == "$baz"

    def test_format_option_with_target(self):
        with pytest.raises(KeyError):
            ui.CommonOptionsParser().add_format_option(target="thingy")

        parser = ui.CommonOptionsParser()
        parser.add_format_option(target="item")

        config["format_item"].set("$item")
        config["format_album"].set("$album")

        assert parser.parse_args(["-f", "$bar"]) == ({"format": "$bar"}, [])

        assert config["format_item"].as_str() == "$bar"
        assert config["format_album"].as_str() == "$album"

    def test_format_option_with_album(self):
        parser = ui.CommonOptionsParser()
        parser.add_album_option()
        parser.add_format_option()

        config["format_item"].set("$item")
        config["format_album"].set("$album")

        parser.parse_args(["-f", "$bar"])
        assert config["format_item"].as_str() == "$bar"
        assert config["format_album"].as_str() == "$album"

        parser.parse_args(["-a", "-f", "$foo"])
        assert config["format_item"].as_str() == "$bar"
        assert config["format_album"].as_str() == "$foo"

        parser.parse_args(["-f", "$foo2", "-a"])
        assert config["format_album"].as_str() == "$foo2"

    def test_add_all_common_options(self):
        parser = ui.CommonOptionsParser()
        parser.add_all_common_options()
        assert parser.parse_args([]) == (
            {"album": None, "path": None, "format": None},
            [],
        )


class EncodingTest(unittest.TestCase):
    """Tests for the `terminal_encoding` config option and our
    `_in_encoding` and `_out_encoding` utility functions.
    """

    def out_encoding_overridden(self):
        config["terminal_encoding"] = "fake_encoding"
        assert ui._out_encoding() == "fake_encoding"

    def in_encoding_overridden(self):
        config["terminal_encoding"] = "fake_encoding"
        assert ui._in_encoding() == "fake_encoding"

    def out_encoding_default_utf8(self):
        with patch("sys.stdout") as stdout:
            stdout.encoding = None
            assert ui._out_encoding() == "utf-8"

    def in_encoding_default_utf8(self):
        with patch("sys.stdin") as stdin:
            stdin.encoding = None
            assert ui._in_encoding() == "utf-8"
