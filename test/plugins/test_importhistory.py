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

    def setUp(self):
        preserve_plugin_listeners()
        super().setUp()

        # Set up configuration for importfeeds plugin to prevent config errors
        # since PluginMixin loads all plugins including importfeeds
        self.config["importfeeds"] = {
            "formats": [],
            "dir": str(self.temp_dir),
            "m3u_name": "imported.m3u",
            "relative_to": None,
            "absolute_path": False,
        }

        self.prepare_album_for_import(2)
        self.importer = self.setup_importer()
        self.importer.add_choice(importer.Action.APPLY)
        # TODO: Set this
        self.source_dir = os.path.join(self.import_dir, b"album")

    def test_imported_album_has_source_path(self):
        self.importer.run()
        album = self.lib.albums().get()
        for item in album.items():
            assert self.source_dir in item.source_path

    def test_do_nothing(self):
        with self.configure_plugin({"suggest_removal": True}):
            self.importer.run()
            item_to_remove = self.lib.albums().get().items()[0]
            with control_stdin("N"):
                self.run_command(
                    "remove",
                    syspath(item_to_remove.path),
                )
        assert os.path.exists(item_to_remove.source_path)

    def test_remove_single(self):
        with self.configure_plugin({"suggest_removal": True}):
            self.importer.run()
            items_to_remove = self.lib.albums().get().items()
            with control_stdin("y\nD"):
                self.run_command(
                    "remove",
                    syspath(items_to_remove[0].path),
                )
        assert not os.path.exists(items_to_remove[0].source_path)

    def test_remove_all_from_single(self):
        with self.configure_plugin({"suggest_removal": True}):
            self.importer.run()
            items_to_remove = self.lib.albums().get().items()
            with control_stdin("y\nR\ny"):
                self.run_command(
                    "remove",
                    syspath(items_to_remove[0].path),
                )
        for item in items_to_remove:
            assert not os.path.exists(item.source_path)

    def test_stop_suggesting(self):
        with self.configure_plugin({"suggest_removal": True}):
            self.importer.run()
            items_to_remove = self.lib.albums().get().items()
            with control_stdin("y\nS"):
                self.run_command(
                    "remove",
                    os.path.dirname(syspath(items_to_remove[0].path)),
                )
        for item in items_to_remove:
            assert os.path.exists(item.source_path)
