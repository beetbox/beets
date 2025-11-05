"""Adds a `source_path` attribute to imported albums indicating from what path
the album was imported from. Also suggests removing that source path in case
you've removed the album from the library.

"""

import os
from pathlib import Path
from shutil import rmtree

from beets.dbcore.query import PathQuery
from beets.plugins import BeetsPlugin
from beets.ui import colorize as colorize_text
from beets.ui import input_options


class ImportSourcePlugin(BeetsPlugin):
    """Main plugin class."""

    def __init__(self):
        """Initialize the plugin and read configuration."""
        super().__init__()
        self.config.add(
            {
                "suggest_removal": False,
            }
        )
        self.import_stages = [self.import_stage]
        self.register_listener("item_removed", self.suggest_removal)
        # In order to stop future removal suggestions for an album we keep
        # track of `mb_albumid`s in this set.
        self.stop_suggestions_for_albums = set()
        # During reimports (import --library) both the import_task_choice and
        # the item_removed event are triggered. The item_removed event is
        # triggered first. For the import_task_choice event we prevent removal
        # suggestions using the existing stop_suggestions_for_album mechanism.
        self.register_listener(
            "import_task_choice", self.prevent_suggest_removal
        )

    def prevent_suggest_removal(self, session, task):
        for item in task.imported_items():
            if "mb_albumid" in item:
                self.stop_suggestions_for_albums.add(item.mb_albumid)

    def import_stage(self, _, task):
        """Event handler for albums import finished."""
        for item in task.imported_items():
            # During reimports (import --library), we prevent overwriting the
            # source_path attribute with the path from the music library
            if "source_path" in item:
                self._log.info(
                    "Preserving source_path of reimported item {}", item.id
                )
                continue
            item["source_path"] = item.path
            item.try_sync(write=False, move=False)

    def suggest_removal(self, item):
        """Prompts the user to delete the original path the item was imported from."""
        if (
            not self.config["suggest_removal"]
            or item.mb_albumid in self.stop_suggestions_for_albums
        ):
            return

        if "source_path" not in item:
            self._log.warning(
                "Item without source_path (probably imported before plugin "
                "usage): {}",
                item.filepath,
            )
            return

        srcpath = Path(os.fsdecode(item.source_path))
        if not srcpath.is_file():
            self._log.warning(
                "Original source file no longer exists or is not accessible: {}",
                srcpath,
            )
            return

        if not (
            os.access(srcpath, os.W_OK)
            and os.access(srcpath.parent, os.W_OK | os.X_OK)
        ):
            self._log.warning(
                "Original source file cannot be deleted (insufficient permissions): {}",
                srcpath,
            )
            return

        # We ask the user whether they'd like to delete the item's source
        # directory
        item_path = colorize_text("text_warning", item.filepath)
        source_path = colorize_text("text_warning", srcpath)

        print(
            f"The item:\n{item_path}\nis originated from:\n{source_path}\n"
            "What would you like to do?"
        )

        resp = input_options(
            [
                "Delete the item's source",
                "Recursively delete the source's directory",
                "do Nothing",
                "do nothing and Stop suggesting to delete items from this album",
            ],
            require=True,
        )

        # Handle user response
        if resp == "d":
            self._log.info(
                "Deleting the item's source file: {}",
                srcpath,
            )
            srcpath.unlink()

        elif resp == "r":
            self._log.info(
                "Searching for other items with a source_path attr containing: {}",
                srcpath.parent,
            )

            source_dir_query = PathQuery(
                "source_path",
                srcpath.parent,
                # The "source_path" attribute may not be present in all
                # items of the library, so we avoid errors with this:
                fast=False,
            )

            print("Doing so will delete the following items' sources as well:")
            for searched_item in item._db.items(source_dir_query):
                print(colorize_text("text_warning", searched_item.filepath))

            print("Would you like to continue?")
            continue_resp = input_options(
                ["Yes", "delete None", "delete just the File"],
                require=False,  # Yes is the a default
            )

            if continue_resp == "y":
                self._log.info(
                    "Deleting the item's source directory: {}",
                    srcpath.parent,
                )
                rmtree(srcpath.parent)

            elif continue_resp == "n":
                self._log.info("doing nothing - aborting hook function")
                return

            elif continue_resp == "f":
                self._log.info(
                    "removing just the item's original source: {}",
                    srcpath,
                )
                srcpath.unlink()

        elif resp == "s":
            self.stop_suggestions_for_albums.add(item.mb_albumid)

        else:
            self._log.info("Doing nothing")
