# This file is part of beets.
# Copyright 2017, Dorian Soergel.
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

"""Gets parent work, its disambiguation and id, composer, composer sort name
and work composition date
"""

from __future__ import annotations

from typing import Any

import musicbrainzngs

from beets import __version__, ui
from beets.plugins import BeetsPlugin

musicbrainzngs.set_useragent("beets", __version__, "https://beets.io/")


def find_parentwork_info(mb_workid: str) -> tuple[dict[str, Any], str | None]:
    """Get the MusicBrainz information dict about a parent work, including
    the artist relations, and the composition date for a work's parent work.
    """
    work_date = None

    parent_id: str | None = mb_workid

    while parent_id:
        current_id = parent_id
        work_info = musicbrainzngs.get_work_by_id(
            current_id, includes=["work-rels", "artist-rels"]
        )["work"]
        work_date = work_date or next(
            (
                end
                for a in work_info.get("artist-relation-list", [])
                if a["type"] == "composer" and (end := a.get("end"))
            ),
            None,
        )
        parent_id = next(
            (
                w["work"]["id"]
                for w in work_info.get("work-relation-list", [])
                if w["type"] == "parts" and w["direction"] == "backward"
            ),
            None,
        )

    return musicbrainzngs.get_work_by_id(
        current_id, includes=["artist-rels"]
    ), work_date


class ParentWorkPlugin(BeetsPlugin):
    def __init__(self):
        super().__init__()

        self.config.add(
            {
                "auto": False,
                "force": False,
            }
        )

        if self.config["auto"]:
            self.import_stages = [self.imported]

    def commands(self):
        def func(lib, opts, args):
            self.config.set_args(opts)
            force_parent = self.config["force"].get(bool)
            write = ui.should_write()

            for item in lib.items(args):
                changed = self.find_work(item, force_parent, verbose=True)
                if changed:
                    item.store()
                    if write:
                        item.try_write()

        command = ui.Subcommand(
            "parentwork", help="fetch parent works, composers and dates"
        )

        command.parser.add_option(
            "-f",
            "--force",
            dest="force",
            action="store_true",
            default=None,
            help="re-fetch when parent work is already present",
        )

        command.func = func
        return [command]

    def imported(self, session, task):
        """Import hook for fetching parent works automatically."""
        force_parent = self.config["force"].get(bool)

        for item in task.imported_items():
            self.find_work(item, force_parent, verbose=False)
            item.store()

    def get_info(self, item, work_info):
        """Given the parent work info dict, fetch parent_composer,
        parent_composer_sort, parentwork, parentwork_disambig, mb_workid and
        composer_ids.
        """

        parent_composer = []
        parent_composer_sort = []
        parentwork_info = {}

        composer_exists = False
        if "artist-relation-list" in work_info["work"]:
            for artist in work_info["work"]["artist-relation-list"]:
                if artist["type"] == "composer":
                    composer_exists = True
                    parent_composer.append(artist["artist"]["name"])
                    parent_composer_sort.append(artist["artist"]["sort-name"])
                    if "end" in artist.keys():
                        parentwork_info["parentwork_date"] = artist["end"]

            parentwork_info["parent_composer"] = ", ".join(parent_composer)
            parentwork_info["parent_composer_sort"] = ", ".join(
                parent_composer_sort
            )

        if not composer_exists:
            self._log.debug(
                "no composer for {}; add one at "
                "https://musicbrainz.org/work/{}",
                item,
                work_info["work"]["id"],
            )

        parentwork_info["parentwork"] = work_info["work"]["title"]
        parentwork_info["mb_parentworkid"] = work_info["work"]["id"]

        if "disambiguation" in work_info["work"]:
            parentwork_info["parentwork_disambig"] = work_info["work"][
                "disambiguation"
            ]

        else:
            parentwork_info["parentwork_disambig"] = None

        return parentwork_info

    def find_work(self, item, force, verbose):
        """Finds the parent work of a recording and populates the tags
        accordingly.

        The parent work is found recursively, by finding the direct parent
        repeatedly until there are no more links in the chain. We return the
        final, topmost work in the chain.

        Namely, the tags parentwork, parentwork_disambig, mb_parentworkid,
        parent_composer, parent_composer_sort and work_date are populated.
        """

        if not item.mb_workid:
            self._log.info(
                "No work for {0}, add one at https://musicbrainz.org/recording/{0.mb_trackid}",
                item,
            )
            return

        hasparent = hasattr(item, "parentwork")
        work_changed = True
        if hasattr(item, "parentwork_workid_current"):
            work_changed = item.parentwork_workid_current != item.mb_workid
        if force or not hasparent or work_changed:
            try:
                work_info, work_date = find_parentwork_info(item.mb_workid)
            except musicbrainzngs.musicbrainz.WebServiceError as e:
                self._log.debug("error fetching work: {}", e)
                return
            parent_info = self.get_info(item, work_info)
            parent_info["parentwork_workid_current"] = item.mb_workid
            if "parent_composer" in parent_info:
                self._log.debug(
                    "Work fetched: {} - {}",
                    parent_info["parentwork"],
                    parent_info["parent_composer"],
                )
            else:
                self._log.debug(
                    "Work fetched: {} - no parent composer",
                    parent_info["parentwork"],
                )

        elif hasparent:
            self._log.debug("{}: Work present, skipping", item)
            return

        # apply all non-null values to the item
        for key, value in parent_info.items():
            if value:
                item[key] = value

        if work_date:
            item["work_date"] = work_date
        if verbose:
            return ui.show_model_changes(
                item,
                fields=[
                    "parentwork",
                    "parentwork_disambig",
                    "mb_parentworkid",
                    "parent_composer",
                    "parent_composer_sort",
                    "work_date",
                    "parentwork_workid_current",
                    "parentwork_date",
                ],
            )
