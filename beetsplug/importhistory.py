"""Adds a `source_path` attribute to imported albums indicating from what path
the album was imported from. Also suggests removing that source path in case
you've removed the album from the library.

"""

import os
from shutil import rmtree

from beets import library
from beets.plugins import BeetsPlugin
from beets.ui import colorize as colorize_text
from beets.ui import input_options, input_yn
from beets.util import displayable_path, syspath


class ImportHistPlugin(BeetsPlugin):
    """Main plugin class."""

    def __init__(self):
        """Initialize the plugin and read configuration."""
        super(ImportHistPlugin, self).__init__()
        self.config.add(
            {
                "auto": True,
            }
        )
        if self.config["auto"]:
            self.import_stages = [self.import_stage]
            self.register_listener("item_removed", self.suggest_removal)
        # In order to stop suggestions for certain albums in
        # self.suggest_removal, we initialize an empty list of mb_albumids that
        # these will be ignored in future runs
        self.stop_suggestions_for_albums = []

    def import_stage(self, _, task):
        """Event handler for albums import finished."""
        # first, we sort the items using a dictionary and a list of paths for
        # every mbid
        for item in task.imported_items():
            item["source_path"] = item.path
            item.try_sync(write=True, move=False)

    def suggest_removal(self, item):
        """Prompts the user to delete the original path the item was imported from."""
        if "source_path" not in item:
            # TODO: Maybe switch to a less arbitrary choice of item fields?
            try:
                self._log.warn(
                    "Item without a source_path was found: {0.title} by {0.artist}",
                    item,
                )
            except UnicodeDecodeError:
                self._log.warn(
                    "Item without a source_path was found: mb_trackid: {0.mb_trackid}",
                    item,
                )
            return
        if (
            not item.source_path
            or item.mb_albumid in self.stop_suggestions_for_albums
        ):
            return
        if not os.path.isfile(syspath(item.source_path)):
            self._log.warn(
                "Item with a source_path that doesn't exist was found:\n%s",
                item.source_path.decode("utf-8"),
            )
            return
        source_dir = os.path.dirname(syspath(item.source_path))
        if not (
            os.access(syspath(item.source_path), os.W_OK) and
            os.access(source_dir, os.W_OK | os.X_OK)
        ):
            self._log.warn(
                "Item with a source_path isn't deletable:\n%s",
                item.source_path.decode("utf-8"),
            )
            return
        try:
            open(syspath(item.source_path), 'w').close()
        except OSError:
            self._log.warn(
                "Item with a source_path is open in another process, and hence "
                "cannot be deleted:\n%s",
                item.source_path.decode("utf-8"),
            )
            return
        # We ask the user whether they'd like to delete the item's source
        # directory
        print(
            "The item:\n{path}\nis originated from:\n{source}\n"
            "What would you like to do?".format(
                path=colorize_text(
                    "text_warning", item.path.decode("utf-8")
                ),
                source=colorize_text(
                    "text_warning", item.source_path.decode("utf-8")
                ),
            )
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
        if resp == "d":
            self._log.info(
                "Deleting the item's source file: {}", item.source_path
            )
            os.remove(syspath(item.source_path))
        elif resp == "r":
            self._log.info(
                "Searching for other items with a source_path attr containing: {}",
                source_dir,
            )
            source_dir_query = library.PathQuery(
                "source_path",
                source_dir,
                # The "source_path" attribute may not be present in all
                # items of the library, so we avoid errors with this:
                fast=False
            )
            print(
                "Doing so will delete the following items' sources as well:"
            )
            for searched_item in item._db.items(source_dir_query):
                print(
                    colorize_text(
                        "text_warning",
                        searched_item["path"].decode("utf-8"),
                    )
                )
            print("Would you like to continue?")
            continue_resp = input_options(
                ["Yes", "delete None", "delete just the File"],
                require=False,  # Yes is the a default
            )
            if continue_resp == "y":
                self._log.info(
                    "Deleting the item's source directory: %s", source_dir
                )
                rmtree(source_dir)
            elif continue_resp == "n":
                self._log.info("doing nothing - aborting hook function")
                return
            elif continue_resp == "f":
                self._log.info(
                    "removing just the item's original source: %s",
                    item.source_path,
                )
                os.remove(item.source_path)
        elif resp == "s":
            self.stop_suggestions_for_albums.append(item.mb_albumid)
        else:
            self._log.info("Doing nothing")
