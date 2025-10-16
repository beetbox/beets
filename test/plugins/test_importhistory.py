# This file is part of beets.
# Copyright 2025, Stig Inge Lea Bjornsen.
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


"""Tests for the `importhistory` plugin."""

import os

from beets import importer
from beets.test.helper import AutotagImportTestCase, PluginMixin, control_stdin
from beets.util import syspath
from beetsplug.importhistory import ImportHistPlugin

_listeners = ImportHistPlugin.listeners


def preserve_plugin_listeners():
    """Preserve the initial plugin listeners as they would otherwise be
    deleted after the first setup / tear down cycle.
    """
    if not ImportHistPlugin.listeners:
        ImportHistPlugin.listeners = _listeners


class ImportHistTest(PluginMixin, AutotagImportTestCase):
    plugin = "importhistory"
    preload_plugin = False

    def setUp(self):
        preserve_plugin_listeners()
        super().setUp()
        self.config[self.plugin]["suggest_removal"] = True
        self.load_plugins()
        self.prepare_album_for_import(2)
        self.importer = self.setup_importer()
        self.importer.add_choice(importer.Action.APPLY)
        self.importer.run()
        self.all_items = self.lib.albums().get().items()
        self.item_to_remove = self.all_items[0]

    def interact(self, stdin_input: str):
        with control_stdin(stdin_input):
            self.run_command(
                "remove",
                f"path:{syspath(self.item_to_remove.path)}",
            )

    def test_do_nothing(self):
        self.interact("N")

        assert os.path.exists(self.item_to_remove.source_path)

    def test_remove_single(self):
        self.interact("y\nD")

        assert not os.path.exists(self.item_to_remove.source_path)

    def test_remove_all_from_single(self):
        self.interact("y\nR\ny")

        for item in self.all_items:
            assert not os.path.exists(item.source_path)

    def test_stop_suggesting(self):
        self.interact("y\nS")

        for item in self.all_items:
            assert os.path.exists(item.source_path)
