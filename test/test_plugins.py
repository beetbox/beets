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


import importlib
import itertools
import logging
import os
import pkgutil
import sys
from unittest.mock import ANY, Mock, patch

import pytest
from mediafile import MediaFile

from beets import config, plugins, ui
from beets.dbcore import types
from beets.importer import (
    Action,
    ArchiveImportTask,
    SentinelImportTask,
    SingletonImportTask,
)
from beets.library import Item
from beets.test import helper
from beets.test.helper import (
    AutotagStub,
    ImportHelper,
    PluginMixin,
    PluginTestCase,
    TerminalImportMixin,
)
from beets.util import displayable_path, syspath


class TestPluginRegistration(PluginTestCase):
    class RatingPlugin(plugins.BeetsPlugin):
        item_types = {"rating": types.Float()}

        def __init__(self):
            super().__init__()
            self.register_listener("write", self.on_write)

        @staticmethod
        def on_write(item=None, path=None, tags=None):
            if tags["artist"] == "XXX":
                tags["artist"] = "YYY"

    def setUp(self):
        super().setUp()

        self.register_plugin(self.RatingPlugin)

    def test_field_type_registered(self):
        assert isinstance(Item._types.get("rating"), types.Float)

    def test_duplicate_type(self):
        class DuplicateTypePlugin(plugins.BeetsPlugin):
            item_types = {"rating": types.INTEGER}

        self.register_plugin(DuplicateTypePlugin)
        with pytest.raises(
            plugins.PluginConflictError, match="already been defined"
        ):
            Item._types

    def test_listener_registered(self):
        self.RatingPlugin()
        item = self.add_item_fixture(artist="XXX")

        item.write()

        assert MediaFile(syspath(item.path)).artist == "YYY"


class PluginImportTestCase(ImportHelper, PluginTestCase):
    def setUp(self):
        super().setUp()
        self.prepare_album_for_import(2)


class EventsTest(PluginImportTestCase):
    def setUp(self):
        super().setUp()

    def test_import_task_created(self):
        self.importer = self.setup_importer(pretend=True)

        with helper.capture_log() as logs:
            self.importer.run()

        # Exactly one event should have been imported (for the album).
        # Sentinels do not get emitted.
        assert logs.count("Sending event: import_task_created") == 1

        logs = [line for line in logs if not line.startswith("Sending event:")]
        assert logs == [
            f"Album: {displayable_path(os.path.join(self.import_dir, b'album'))}",
            f"  {displayable_path(self.import_media[0].path)}",
            f"  {displayable_path(self.import_media[1].path)}",
        ]

    def test_import_task_created_with_plugin(self):
        class ToSingletonPlugin(plugins.BeetsPlugin):
            def __init__(self):
                super().__init__()

                self.register_listener(
                    "import_task_created", self.import_task_created_event
                )

            def import_task_created_event(self, session, task):
                if (
                    isinstance(task, SingletonImportTask)
                    or isinstance(task, SentinelImportTask)
                    or isinstance(task, ArchiveImportTask)
                ):
                    return task

                new_tasks = []
                for item in task.items:
                    new_tasks.append(SingletonImportTask(task.toppath, item))

                return new_tasks

        to_singleton_plugin = ToSingletonPlugin
        self.register_plugin(to_singleton_plugin)

        self.importer = self.setup_importer(pretend=True)

        with helper.capture_log() as logs:
            self.importer.run()

        # Exactly one event should have been imported (for the album).
        # Sentinels do not get emitted.
        assert logs.count("Sending event: import_task_created") == 1

        logs = [line for line in logs if not line.startswith("Sending event:")]
        assert logs == [
            f"Singleton: {displayable_path(self.import_media[0].path)}",
            f"Singleton: {displayable_path(self.import_media[1].path)}",
        ]


class ListenersTest(PluginTestCase):
    def test_register(self):
        class DummyPlugin(plugins.BeetsPlugin):
            def __init__(self):
                super().__init__()
                self.register_listener("cli_exit", self.dummy)
                self.register_listener("cli_exit", self.dummy)

            def dummy(self):
                pass

        d = DummyPlugin()
        assert DummyPlugin._raw_listeners["cli_exit"] == [d.dummy]

        d2 = DummyPlugin()
        assert DummyPlugin._raw_listeners["cli_exit"] == [d.dummy, d2.dummy]

        d.register_listener("cli_exit", d2.dummy)
        assert DummyPlugin._raw_listeners["cli_exit"] == [d.dummy, d2.dummy]

    def test_events_called(self):
        class DummyPlugin(plugins.BeetsPlugin):
            def __init__(self):
                super().__init__()
                self.foo = Mock(__name__="foo")
                self.register_listener("event_foo", self.foo)
                self.bar = Mock(__name__="bar")
                self.register_listener("event_bar", self.bar)

        d = DummyPlugin()

        plugins.send("event")
        d.foo.assert_has_calls([])
        d.bar.assert_has_calls([])

        plugins.send("event_foo", var="tagada")
        d.foo.assert_called_once_with(var="tagada")
        d.bar.assert_has_calls([])

    def test_listener_params(self):
        class DummyPlugin(plugins.BeetsPlugin):
            def __init__(self):
                super().__init__()
                for i in itertools.count(1):
                    try:
                        meth = getattr(self, f"dummy{i}")
                    except AttributeError:
                        break
                    self.register_listener(f"event{i}", meth)

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

        DummyPlugin()

        plugins.send("event1", foo=5)
        plugins.send("event2", foo=5)
        plugins.send("event3", foo=5)
        plugins.send("event4", foo=5)

        with pytest.raises(TypeError):
            plugins.send("event5", foo=5)

        plugins.send("event6", foo=5)
        plugins.send("event7", foo=5)

        with pytest.raises(TypeError):
            plugins.send("event8", foo=5)

        plugins.send("event9", foo=5)


class PromptChoicesTest(TerminalImportMixin, PluginImportTestCase):
    def setUp(self):
        super().setUp()
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
                    ui.commands.PromptChoice("f", "Foo", None),
                    ui.commands.PromptChoice("r", "baR", None),
                ]

        self.register_plugin(DummyPlugin)
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
                    ui.commands.PromptChoice("f", "Foo", None),
                    ui.commands.PromptChoice("r", "baR", None),
                ]

        self.register_plugin(DummyPlugin)
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
                    ui.commands.PromptChoice("a", "A foo", None),  # dupe
                    ui.commands.PromptChoice("z", "baZ", None),  # ok
                    ui.commands.PromptChoice("z", "Zupe", None),  # dupe
                    ui.commands.PromptChoice("z", "Zoo", None),
                ]  # dupe

        self.register_plugin(DummyPlugin)
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
                return [ui.commands.PromptChoice("f", "Foo", self.foo)]

            def foo(self, session, task):
                pass

        self.register_plugin(DummyPlugin)
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
                return [ui.commands.PromptChoice("f", "Foo", self.foo)]

            def foo(self, session, task):
                return Action.SKIP

        self.register_plugin(DummyPlugin)
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


class TestImportAllPlugins(PluginMixin):
    def unimport_plugins(self):
        """Unimport plugins before each test to avoid conflicts."""
        self.unload_plugins()
        for mod in list(sys.modules):
            if mod.startswith("beetsplug."):
                del sys.modules[mod]

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Ensure plugins are unimported before and after each test."""
        self.unimport_plugins()
        yield
        self.unimport_plugins()

    @pytest.mark.skipif(
        os.environ.get("GITHUB_ACTIONS") != "true",
        reason="Requires all dependencies to be installed, "
        + "which we can't guarantee in the local environment.",
    )
    @pytest.mark.parametrize("plugin_name", get_available_plugins())
    def test_import_plugin(self, caplog, plugin_name):  #
        """Test that a plugin is importable without an error using the
        load_plugins function."""

        # skip gstreamer plugins on windows
        gstreamer_plugins = ["bpd", "replaygain"]
        if sys.platform == "win32" and plugin_name in gstreamer_plugins:
            pytest.xfail("GStreamer is not available on Windows: {plugin_name}")

        caplog.set_level(logging.WARNING)
        caplog.clear()
        plugins.load_plugins(include={plugin_name})

        assert "PluginImportError" not in caplog.text, (
            f"Plugin '{plugin_name}' has issues during import."
        )
