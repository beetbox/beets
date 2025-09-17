# This file is part of beets.
# Copyright 2016, Thomas Scholtes.
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

from __future__ import annotations

import importlib
import logging
import os
import pkgutil
import sys
from typing import Any
from unittest.mock import ANY, patch

import pytest
from mediafile import MediaFile

from beets import config, plugins, ui
from beets.dbcore import types
from beets.importer import Action
from beets.library import Album, Item
from beets.test import helper
from beets.test.helper import (
    AutotagStub,
    ImportHelper,
    PluginMixin,
    PluginTestCase,
    PluginTestCasePytest,
    TerminalImportMixin,
)
from beets.util import PromptChoice, syspath


class TestPluginRegistration(PluginTestCasePytest):
    """Ensure that we can dynamically add a plugin without creating
    actual files on disk.

    This is a meta test that ensures that our dynamic registration
    mechanism works as intended.

    TODO: Add a test for template functions, template fields and album template fields
    """

    class DummyPlugin(plugins.BeetsPlugin):
        item_types = {
            "foo": types.Float(),
            "bar": types.MULTI_VALUE_DSV,
        }
        album_types = {
            "baz": types.INTEGER,
        }

    plugin = "dummy"
    plugin_type = DummyPlugin

    def test_get_plugin(self):
        """Test that get_plugin returns the correct plugin class."""
        plugin = plugins._get_plugin(self.plugin)
        assert plugin is not None
        assert isinstance(plugin, self.DummyPlugin)

    def test_field_type_registered(self):
        """Test that the field types are registered on the Item class."""
        assert isinstance(Item._types.get("foo"), types.Float)
        assert Item._types.get("bar") is types.MULTI_VALUE_DSV
        assert Album._types.get("baz") is types.INTEGER

    def test_multi_value_flex_field_type(self):
        item = Item(path="apath", artist="aaa")
        item.bar = ["one", "two", "three"]
        item.add(self.lib)

        out = self.run_with_output("ls", "-f", "$bar")
        delimiter = types.MULTI_VALUE_DSV.delimiter
        assert out == f"one{delimiter}two{delimiter}three\n"

    def test_duplicate_field_typ(self):
        """Test that if another plugin tries to register the same type,
        a PluginConflictError is raised.
        """

        class DuplicateDummyPlugin(plugins.BeetsPlugin):
            album_types = {"baz": types.Float()}

        with (
            self.plugins(
                ("dummy", self.DummyPlugin), ("duplicate", DuplicateDummyPlugin)
            ),
            pytest.raises(
                plugins.PluginConflictError, match="already been defined"
            ),
        ):
            Album._types


class TestPluginListeners(PluginTestCasePytest, ImportHelper):
    """Test that plugin listeners are registered and called correctly."""

    class DummyPlugin(plugins.BeetsPlugin):
        records: list[Any]

        def __init__(self):
            super().__init__()
            self.records = []
            self.register_listener("cli_exit", self.on_cli_exit)
            self.register_listener("write", self.on_write)
            self.register_listener(
                "import_task_created", self.on_import_task_created
            )

        def on_cli_exit(self, **kwargs):
            self.records.append(("cli_exit", kwargs))

        def on_write(
            self, item=None, path=None, tags: dict[Any, Any] | None = None
        ):
            self.records.append(("write", item, path, tags))
            if tags and tags["artist"] == "XXX":
                tags["artist"] = "YYY"

        def on_import_task_created(self, **kwargs):
            self.records.append(("import_task_created", kwargs))

    plugin_type = DummyPlugin
    plugin = "dummy"

    @pytest.fixture(autouse=True)
    def clear_records(self):
        plug = self.get_plugin_instance()
        assert isinstance(plug, self.DummyPlugin)
        plug.records.clear()

    def get_records(self):
        plug = self.get_plugin_instance()
        assert isinstance(plug, self.DummyPlugin)
        return plug.records

    @pytest.mark.parametrize(
        "event",
        [
            "cli_exit",
            "write",
            "import_task_created",
        ],
    )
    def test_listener_events(self, event):
        """Generic test for all events triggered via `plugins.send`."""
        plugins.send(event)
        records = self.get_records()
        assert len(records) == 1
        assert records[0][0] == event

    def test_on_write(self):
        # Additionally test that tags are modified correctly.
        item = self.add_item_fixture(artist="XXX")
        item.write()
        assert MediaFile(syspath(item.path)).artist == "YYY"

    def test_on_import_task_created(self, caplog):
        """Test that the import_task_created event is triggered
        when an import task is created."""

        # Fixme: unittest ImportHelper in pytest setup
        self.import_media = []
        self.prepare_album_for_import(2)

        self.importer = self.setup_importer(pretend=True)
        self.importer.run()

        assert self.get_records()[0][0] == "import_task_created"


class TestPluginListenersParams(PluginMixin):
    """Test that plugin listeners are called with correct parameters.

    Also check that invalid parameters raise TypeErrors.
    """

    def dummy1(self, foo):
        assert foo == 5

    def dummy2(self, foo=None):
        assert foo == 5

    def dummy3(self):
        # argument cut off
        pass

    def dummy4(self, bar=None):
        # argument cut off
        pass

    def dummy5(self, bar):
        assert not True

    # more complex examples

    def dummy6(self, foo, bar=None):
        assert foo == 5
        assert bar is None

    def dummy7(self, foo, **kwargs):
        assert foo == 5
        assert kwargs == {}

    def dummy8(self, foo, bar, **kwargs):
        assert not True

    def dummy9(self, **kwargs):
        assert kwargs == {"foo": 5}

    @pytest.mark.parametrize(
        "func, raises",
        [
            ("dummy1", False),
            ("dummy2", False),
            ("dummy3", False),
            ("dummy4", False),
            ("dummy5", True),
            ("dummy6", False),
            ("dummy7", False),
            ("dummy8", True),
            ("dummy9", False),
        ],
    )
    def test_listener_params(self, func, raises):
        func_obj = getattr(self, func)

        class DummyPlugin(plugins.BeetsPlugin):
            def __init__(self):
                super().__init__()
                self.register_listener("exit_cli", func_obj)

        with self.plugins(("dummy", DummyPlugin)):
            if raises:
                with pytest.raises(TypeError):
                    plugins.send("exit_cli", foo=5)
            else:
                plugins.send("exit_cli", foo=5)


class PromptChoicesTest(TerminalImportMixin, ImportHelper, PluginMixin):
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        # FIXME: Run old unittest setup/teardown methods
        self.setUp()
        yield
        self.tearDown()

    def setUp(self):
        super().setUp()
        self.prepare_album_for_import(2)

        self.setup_importer()
        self.matcher = AutotagStub(AutotagStub.IDENT).install()
        self.addCleanup(self.matcher.restore)
        # keep track of ui.input_option() calls
        self.input_options_patcher = patch(
            "beets.ui.input_options", side_effect=ui.input_options
        )
        self.mock_input_options = self.input_options_patcher.start()

    def tearDown(self):
        super().tearDown()
        self.input_options_patcher.stop()

    def test_plugin_choices_in_ui_input_options_album(self):
        """Test the presence of plugin choices on the prompt (album)."""

        class DummyPlugin(plugins.BeetsPlugin):
            def __init__(self):
                super().__init__()
                self.register_listener(
                    "before_choose_candidate", self.return_choices
                )

            def return_choices(self, session, task):
                return [
                    PromptChoice("f", "Foo", None),
                    PromptChoice("r", "baR", None),
                ]

        with self.plugins(("dummy", DummyPlugin)):
            # Default options + extra choices by the plugin ('Foo', 'Bar')
            opts = (
                "Apply",
                "More candidates",
                "Skip",
                "Use as-is",
                "as Tracks",
                "Group albums",
                "Enter search",
                "enter Id",
                "aBort",
            ) + ("Foo", "baR")

            self.importer.add_choice(Action.SKIP)
            self.importer.run()
            self.mock_input_options.assert_called_once_with(
                opts, default="a", require=ANY
            )

    def test_plugin_choices_in_ui_input_options_singleton(self):
        """Test the presence of plugin choices on the prompt (singleton)."""

        class DummyPlugin(plugins.BeetsPlugin):
            def __init__(self):
                super().__init__()
                self.register_listener(
                    "before_choose_candidate", self.return_choices
                )

            def return_choices(self, session, task):
                return [
                    PromptChoice("f", "Foo", None),
                    PromptChoice("r", "baR", None),
                ]

        with self.plugins(("dummy", DummyPlugin)):
            # Default options + extra choices by the plugin ('Foo', 'Bar')
            opts = (
                "Apply",
                "More candidates",
                "Skip",
                "Use as-is",
                "Enter search",
                "enter Id",
                "aBort",
            ) + ("Foo", "baR")

            config["import"]["singletons"] = True
            self.importer.add_choice(Action.SKIP)
            self.importer.run()
            self.mock_input_options.assert_called_with(
                opts, default="a", require=ANY
            )

    def test_choices_conflicts(self):
        """Test the short letter conflict solving."""

        class DummyPlugin(plugins.BeetsPlugin):
            def __init__(self):
                super().__init__()
                self.register_listener(
                    "before_choose_candidate", self.return_choices
                )

            def return_choices(self, session, task):
                return [
                    PromptChoice("a", "A foo", None),  # dupe
                    PromptChoice("z", "baZ", None),  # ok
                    PromptChoice("z", "Zupe", None),  # dupe
                    PromptChoice("z", "Zoo", None),
                ]  # dupe

        with self.plugins(("dummy", DummyPlugin)):
            # Default options + not dupe extra choices by the plugin ('baZ')
            opts = (
                "Apply",
                "More candidates",
                "Skip",
                "Use as-is",
                "as Tracks",
                "Group albums",
                "Enter search",
                "enter Id",
                "aBort",
            ) + ("baZ",)
            self.importer.add_choice(Action.SKIP)
            self.importer.run()
            self.mock_input_options.assert_called_once_with(
                opts, default="a", require=ANY
            )

    def test_plugin_callback(self):
        """Test that plugin callbacks are being called upon user choice."""

        class DummyPlugin(plugins.BeetsPlugin):
            def __init__(self):
                super().__init__()
                self.register_listener(
                    "before_choose_candidate", self.return_choices
                )

            def return_choices(self, session, task):
                return [PromptChoice("f", "Foo", self.foo)]

            def foo(self, session, task):
                pass

        with self.plugins(("dummy", DummyPlugin)):
            # Default options + extra choices by the plugin ('Foo', 'Bar')
            opts = (
                "Apply",
                "More candidates",
                "Skip",
                "Use as-is",
                "as Tracks",
                "Group albums",
                "Enter search",
                "enter Id",
                "aBort",
            ) + ("Foo",)

            # DummyPlugin.foo() should be called once
            with patch.object(DummyPlugin, "foo", autospec=True) as mock_foo:
                with helper.control_stdin("\n".join(["f", "s"])):
                    self.importer.run()
                assert mock_foo.call_count == 1

            # input_options should be called twice, as foo() returns None
            assert self.mock_input_options.call_count == 2
            self.mock_input_options.assert_called_with(
                opts, default="a", require=ANY
            )

    def test_plugin_callback_return(self):
        """Test that plugin callbacks that return a value exit the loop."""

        class DummyPlugin(plugins.BeetsPlugin):
            def __init__(self):
                super().__init__()
                self.register_listener(
                    "before_choose_candidate", self.return_choices
                )

            def return_choices(self, session, task):
                return [PromptChoice("f", "Foo", self.foo)]

            def foo(self, session, task):
                return Action.SKIP

        with self.plugins(("dummy", DummyPlugin)):
            # Default options + extra choices by the plugin ('Foo', 'Bar')
            opts = (
                "Apply",
                "More candidates",
                "Skip",
                "Use as-is",
                "as Tracks",
                "Group albums",
                "Enter search",
                "enter Id",
                "aBort",
            ) + ("Foo",)

            # DummyPlugin.foo() should be called once
            with helper.control_stdin("f\n"):
                self.importer.run()

            # input_options should be called once, as foo() returns SKIP
            self.mock_input_options.assert_called_once_with(
                opts, default="a", require=ANY
            )


def get_available_plugins():
    """Get all available plugins in the beetsplug namespace."""
    namespace_pkg = importlib.import_module("beetsplug")

    return [
        m.name
        for m in pkgutil.iter_modules(namespace_pkg.__path__)
        if not m.name.startswith("_")
    ]


class TestImportPlugin(PluginMixin):
    """Test that all available plugins can be imported without error."""

    @pytest.fixture(params=get_available_plugins())
    def plugin_name(self, request):
        """Fixture to provide the name of each available plugin."""
        name = request.param

        # skip gstreamer plugins on windows
        gstreamer_plugins = {"bpd", "replaygain"}
        if sys.platform == "win32" and name in gstreamer_plugins:
            pytest.skip(f"GStreamer is not available on Windows: {name}")

        return name

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Ensure plugins are unimported before and after each test."""
        self.unload_plugins()
        yield
        self.unload_plugins()

    @pytest.mark.skipif(
        os.environ.get("GITHUB_ACTIONS") != "true",
        reason=(
            "Requires all dependencies to be installed, which we can't"
            " guarantee in the local environment."
        ),
    )
    def test_import_plugin(self, caplog, plugin_name):
        """Test that a plugin is importable without an error."""
        caplog.set_level(logging.WARNING)
        self.load_plugins(plugin_name)

        assert "PluginImportError" not in caplog.text, (
            f"Plugin '{plugin_name}' has issues during import."
        )

    def test_import_error(self, caplog):
        """Test that an invalid plugin raises PluginImportError."""
        self.load_plugins("this_does_not_exist")
        assert "PluginImportError" in caplog.text


class TestDeprecationCopy:
    # TODO: remove this test in Beets 3.0.0
    def test_legacy_metadata_plugin_deprecation(self):
        """Test that a MetadataSourcePlugin with 'legacy' data_source
        raises a deprecation warning and all function and properties are
        copied from the base class.
        """
        with pytest.warns(DeprecationWarning, match="LegacyMetadataPlugin"):

            class LegacyMetadataPlugin(plugins.BeetsPlugin):
                data_source = "legacy"

        # Assert all methods are present
        assert hasattr(LegacyMetadataPlugin, "albums_for_ids")
        assert hasattr(LegacyMetadataPlugin, "tracks_for_ids")
        assert hasattr(LegacyMetadataPlugin, "data_source_mismatch_penalty")
        assert hasattr(LegacyMetadataPlugin, "_extract_id")
        assert hasattr(LegacyMetadataPlugin, "get_artist")


class TestMusicBrainzPluginLoading:
    @pytest.fixture(autouse=True)
    def config(self):
        _config = config
        _config.sources = []
        _config.read(user=False, defaults=True)
        return _config

    def test_default(self):
        assert "musicbrainz" in plugins.get_plugin_names()

    def test_other_plugin_enabled(self, config):
        config["plugins"] = ["anything"]

        assert "musicbrainz" not in plugins.get_plugin_names()

    def test_deprecated_enabled(self, config, caplog):
        config["plugins"] = ["anything"]
        config["musicbrainz"]["enabled"] = True

        assert "musicbrainz" in plugins.get_plugin_names()
        assert (
            "musicbrainz.enabled' configuration option is deprecated"
            in caplog.text
        )

    def test_deprecated_disabled(self, config, caplog):
        config["musicbrainz"]["enabled"] = False

        assert "musicbrainz" not in plugins.get_plugin_names()
        assert (
            "musicbrainz.enabled' configuration option is deprecated"
            in caplog.text
        )
