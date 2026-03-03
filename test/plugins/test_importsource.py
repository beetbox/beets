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


"""Tests for the `importsource` plugin."""

import os
import time

from beets import importer, plugins
from beets.test.helper import AutotagImportTestCase, IOMixin, PluginMixin
from beets.util import syspath
from beetsplug.importsource import ImportSourcePlugin

_listeners = ImportSourcePlugin.listeners


def preserve_plugin_listeners():
    """Preserve the initial plugin listeners as they would otherwise be
    deleted after the first setup / tear down cycle.
    """
    if not ImportSourcePlugin.listeners:
        ImportSourcePlugin.listeners = _listeners


class ImportSourceTest(IOMixin, PluginMixin, AutotagImportTestCase):
    plugin = "importsource"
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

    def interact(self, stdin: list[str]):
        for char in stdin:
            self.io.addinput(char)
        self.run_command("remove", f"path:{syspath(self.item_to_remove.path)}")

    def test_do_nothing(self):
        self.interact(["N"])

        assert os.path.exists(self.item_to_remove.source_path)

    def test_remove_single(self):
        self.interact(["y", "D"])

        assert not os.path.exists(self.item_to_remove.source_path)

    def test_remove_all_from_single(self):
        self.interact(["y", "R", "y"])

        for item in self.all_items:
            assert not os.path.exists(item.source_path)

    def test_stop_suggesting(self):
        self.interact(["y", "S"])

        for item in self.all_items:
            assert os.path.exists(item.source_path)

    def test_source_path_attribute_written(self):
        """Test that source_path attribute is correctly written to imported items.

        The items should already have source_path from the setUp import
        """
        for item in self.all_items:
            assert "source_path" in item
            assert item.source_path  # Should not be empty

    def test_source_files_not_modified_during_import(self):
        """Test that source files timestamps are not changed during import."""
        # Prepare fresh files and record timestamps
        test_album_path = self.import_path / "test_album"
        import_paths = self.prepare_album_for_import(
            2, album_path=test_album_path
        )
        original_mtimes = {
            path: os.stat(path).st_mtime for path in import_paths
        }

        # Small delay to detect timestamp changes
        time.sleep(0.1)

        # Run a fresh import
        importer_session = self.setup_importer()
        importer_session.add_choice(importer.Action.APPLY)
        importer_session.run()

        # Verify timestamps haven't changed
        for path, original_mtime in original_mtimes.items():
            current_mtime = os.stat(path).st_mtime
            assert current_mtime == original_mtime, (
                f"Source file timestamp changed: {path}"
            )

    def test_prevent_suggest_removal_on_reimport(self):
        """Test that removal suggestions are prevented during reimport."""
        album = self.lib.albums().get()
        mb_albumid = album.mb_albumid

        # Reimport from library
        reimporter = self.setup_importer(import_dir=self.libdir)
        reimporter.add_choice(importer.Action.APPLY)
        reimporter.run()

        plugin = plugins._instances[0]
        assert mb_albumid in plugin.stop_suggestions_for_albums

        # Calling suggest_removal should exit early without prompting
        item = self.lib.items().get()
        plugin.suggest_removal(item)
        assert os.path.exists(item.source_path)

    def test_prevent_suggest_removal_handles_skipped_task(self):
        """Test that skipped tasks don't crash prevent_suggest_removal."""

        class MockTask:
            skip = True

            def imported_items(self):
                return "whatever"

        plugin = plugins._instances[0]
        mock_task = MockTask()
        plugin.prevent_suggest_removal(None, mock_task)
