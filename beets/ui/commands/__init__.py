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

"""This module provides the default commands for beets' command-line
interface.
"""

import os
import re
import textwrap
from collections import Counter
from collections.abc import Sequence
from functools import cached_property
from itertools import chain
from platform import python_version
from typing import Any, NamedTuple

import beets
from beets import autotag, config, importer, library, logging, plugins, ui, util
from beets.autotag import Recommendation, hooks
from beets.ui import (
    input_,
    print_,
    print_column_layout,
    print_newline_layout,
    show_path_changes,
)
from beets.util import (
    MoveOperation,
    ancestry,
    displayable_path,
    functemplate,
    normpath,
    syspath,
)
from beets.util.units import human_bytes, human_seconds, human_seconds_short

from . import _store_dict

VARIOUS_ARTISTS = "Various Artists"

# Global logger.
log = logging.getLogger("beets")

# The list of default subcommands. This is populated with Subcommand
# objects that can be fed to a SubcommandsOptionParser.
default_commands = []


# import: Autotagger and importer.

# Importer utilities and support.


def disambig_string(info):
    """Generate a string for an AlbumInfo or TrackInfo object that
    provides context that helps disambiguate similar-looking albums and
    tracks.
    """
    if isinstance(info, hooks.AlbumInfo):
        disambig = get_album_disambig_fields(info)
    elif isinstance(info, hooks.TrackInfo):
        disambig = get_singleton_disambig_fields(info)
    else:
        return ""

    return ", ".join(disambig)


def get_singleton_disambig_fields(info: hooks.TrackInfo) -> Sequence[str]:
    out = []
    chosen_fields = config["match"]["singleton_disambig_fields"].as_str_seq()
    calculated_values = {
        "index": f"Index {info.index}",
        "track_alt": f"Track {info.track_alt}",
        "album": (
            f"[{info.album}]"
            if (
                config["import"]["singleton_album_disambig"].get()
                and info.get("album")
            )
            else ""
        ),
    }

    for field in chosen_fields:
        if field in calculated_values:
            out.append(str(calculated_values[field]))
        else:
            try:
                out.append(str(info[field]))
            except (AttributeError, KeyError):
                print(f"Disambiguation string key {field} does not exist.")

    return out


def get_album_disambig_fields(info: hooks.AlbumInfo) -> Sequence[str]:
    out = []
    chosen_fields = config["match"]["album_disambig_fields"].as_str_seq()
    calculated_values = {
        "media": (
            f"{info.mediums}x{info.media}"
            if (info.mediums and info.mediums > 1)
            else info.media
        ),
    }

    for field in chosen_fields:
        if field in calculated_values:
            out.append(str(calculated_values[field]))
        else:
            try:
                out.append(str(info[field]))
            except (AttributeError, KeyError):
                print(f"Disambiguation string key {field} does not exist.")

    return out


def dist_colorize(string, dist):
    """Formats a string as a colorized similarity string according to
    a distance.
    """
    if dist <= config["match"]["strong_rec_thresh"].as_number():
        string = ui.colorize("text_success", string)
    elif dist <= config["match"]["medium_rec_thresh"].as_number():
        string = ui.colorize("text_warning", string)
    else:
        string = ui.colorize("text_error", string)
    return string


def dist_string(dist):
    """Formats a distance (a float) as a colorized similarity percentage
    string.
    """
    string = f"{(1 - dist) * 100:.1f}%"
    return dist_colorize(string, dist)


def penalty_string(distance, limit=None):
    """Returns a colorized string that indicates all the penalties
    applied to a distance object.
    """
    penalties = []
    for key in distance.keys():
        key = key.replace("album_", "")
        key = key.replace("track_", "")
        key = key.replace("_", " ")
        penalties.append(key)
    if penalties:
        if limit and len(penalties) > limit:
            penalties = penalties[:limit] + ["..."]
        # Prefix penalty string with U+2260: Not Equal To
        penalty_string = f"\u2260 {', '.join(penalties)}"
        return ui.colorize("changed", penalty_string)


class ChangeRepresentation:
    """Keeps track of all information needed to generate a (colored) text
    representation of the changes that will be made if an album or singleton's
    tags are changed according to `match`, which must be an AlbumMatch or
    TrackMatch object, accordingly.
    """

    @cached_property
    def changed_prefix(self) -> str:
        return ui.colorize("changed", "\u2260")

    cur_artist = None
    # cur_album set if album, cur_title set if singleton
    cur_album = None
    cur_title = None
    match = None
    indent_header = ""
    indent_detail = ""

    def __init__(self):
        # Read match header indentation width from config.
        match_header_indent_width = config["ui"]["import"]["indentation"][
            "match_header"
        ].as_number()
        self.indent_header = ui.indent(match_header_indent_width)

        # Read match detail indentation width from config.
        match_detail_indent_width = config["ui"]["import"]["indentation"][
            "match_details"
        ].as_number()
        self.indent_detail = ui.indent(match_detail_indent_width)

        # Read match tracklist indentation width from config
        match_tracklist_indent_width = config["ui"]["import"]["indentation"][
            "match_tracklist"
        ].as_number()
        self.indent_tracklist = ui.indent(match_tracklist_indent_width)
        self.layout = config["ui"]["import"]["layout"].as_choice(
            {
                "column": 0,
                "newline": 1,
            }
        )

    def print_layout(
        self, indent, left, right, separator=" -> ", max_width=None
    ):
        if not max_width:
            # If no max_width provided, use terminal width
            max_width = ui.term_width()
        if self.layout == 0:
            print_column_layout(indent, left, right, separator, max_width)
        else:
            print_newline_layout(indent, left, right, separator, max_width)

    def show_match_header(self):
        """Print out a 'header' identifying the suggested match (album name,
        artist name,...) and summarizing the changes that would be made should
        the user accept the match.
        """
        # Print newline at beginning of change block.
        print_("")

        # 'Match' line and similarity.
        print_(
            f"{self.indent_header}Match ({dist_string(self.match.distance)}):"
        )

        if isinstance(self.match.info, autotag.hooks.AlbumInfo):
            # Matching an album - print that
            artist_album_str = (
                f"{self.match.info.artist} - {self.match.info.album}"
            )
        else:
            # Matching a single track
            artist_album_str = (
                f"{self.match.info.artist} - {self.match.info.title}"
            )
        print_(
            self.indent_header
            + dist_colorize(artist_album_str, self.match.distance)
        )

        # Penalties.
        penalties = penalty_string(self.match.distance)
        if penalties:
            print_(f"{self.indent_header}{penalties}")

        # Disambiguation.
        disambig = disambig_string(self.match.info)
        if disambig:
            print_(f"{self.indent_header}{disambig}")

        # Data URL.
        if self.match.info.data_url:
            url = ui.colorize("text_faint", f"{self.match.info.data_url}")
            print_(f"{self.indent_header}{url}")

    def show_match_details(self):
        """Print out the details of the match, including changes in album name
        and artist name.
        """
        # Artist.
        artist_l, artist_r = self.cur_artist or "", self.match.info.artist
        if artist_r == VARIOUS_ARTISTS:
            # Hide artists for VA releases.
            artist_l, artist_r = "", ""
        if artist_l != artist_r:
            artist_l, artist_r = ui.colordiff(artist_l, artist_r)
            left = {
                "prefix": f"{self.changed_prefix} Artist: ",
                "contents": artist_l,
                "suffix": "",
            }
            right = {"prefix": "", "contents": artist_r, "suffix": ""}
            self.print_layout(self.indent_detail, left, right)

        else:
            print_(f"{self.indent_detail}*", "Artist:", artist_r)

        if self.cur_album:
            # Album
            album_l, album_r = self.cur_album or "", self.match.info.album
            if (
                self.cur_album != self.match.info.album
                and self.match.info.album != VARIOUS_ARTISTS
            ):
                album_l, album_r = ui.colordiff(album_l, album_r)
                left = {
                    "prefix": f"{self.changed_prefix} Album: ",
                    "contents": album_l,
                    "suffix": "",
                }
                right = {"prefix": "", "contents": album_r, "suffix": ""}
                self.print_layout(self.indent_detail, left, right)
            else:
                print_(f"{self.indent_detail}*", "Album:", album_r)
        elif self.cur_title:
            # Title - for singletons
            title_l, title_r = self.cur_title or "", self.match.info.title
            if self.cur_title != self.match.info.title:
                title_l, title_r = ui.colordiff(title_l, title_r)
                left = {
                    "prefix": f"{self.changed_prefix} Title: ",
                    "contents": title_l,
                    "suffix": "",
                }
                right = {"prefix": "", "contents": title_r, "suffix": ""}
                self.print_layout(self.indent_detail, left, right)
            else:
                print_(f"{self.indent_detail}*", "Title:", title_r)

    def make_medium_info_line(self, track_info):
        """Construct a line with the current medium's info."""
        track_media = track_info.get("media", "Media")
        # Build output string.
        if self.match.info.mediums > 1 and track_info.disctitle:
            return (
                f"* {track_media} {track_info.medium}: {track_info.disctitle}"
            )
        elif self.match.info.mediums > 1:
            return f"* {track_media} {track_info.medium}"
        elif track_info.disctitle:
            return f"* {track_media}: {track_info.disctitle}"
        else:
            return ""

    def format_index(self, track_info):
        """Return a string representing the track index of the given
        TrackInfo or Item object.
        """
        if isinstance(track_info, hooks.TrackInfo):
            index = track_info.index
            medium_index = track_info.medium_index
            medium = track_info.medium
            mediums = self.match.info.mediums
        else:
            index = medium_index = track_info.track
            medium = track_info.disc
            mediums = track_info.disctotal
        if config["per_disc_numbering"]:
            if mediums and mediums > 1:
                return f"{medium}-{medium_index}"
            else:
                return str(medium_index if medium_index is not None else index)
        else:
            return str(index)

    def make_track_numbers(self, item, track_info):
        """Format colored track indices."""
        cur_track = self.format_index(item)
        new_track = self.format_index(track_info)
        changed = False
        # Choose color based on change.
        if cur_track != new_track:
            changed = True
            if item.track in (track_info.index, track_info.medium_index):
                highlight_color = "text_highlight_minor"
            else:
                highlight_color = "text_highlight"
        else:
            highlight_color = "text_faint"

        lhs_track = ui.colorize(highlight_color, f"(#{cur_track})")
        rhs_track = ui.colorize(highlight_color, f"(#{new_track})")
        return lhs_track, rhs_track, changed

    @staticmethod
    def make_track_titles(item, track_info):
        """Format colored track titles."""
        new_title = track_info.title
        if not item.title.strip():
            # If there's no title, we use the filename. Don't colordiff.
            cur_title = displayable_path(os.path.basename(item.path))
            return cur_title, new_title, True
        else:
            # If there is a title, highlight differences.
            cur_title = item.title.strip()
            cur_col, new_col = ui.colordiff(cur_title, new_title)
            return cur_col, new_col, cur_title != new_title

    @staticmethod
    def make_track_lengths(item, track_info):
        """Format colored track lengths."""
        changed = False
        if (
            item.length
            and track_info.length
            and abs(item.length - track_info.length)
            >= config["ui"]["length_diff_thresh"].as_number()
        ):
            highlight_color = "text_highlight"
            changed = True
        else:
            highlight_color = "text_highlight_minor"

        # Handle nonetype lengths by setting to 0
        cur_length0 = item.length if item.length else 0
        new_length0 = track_info.length if track_info.length else 0
        # format into string
        cur_length = f"({human_seconds_short(cur_length0)})"
        new_length = f"({human_seconds_short(new_length0)})"
        # colorize
        lhs_length = ui.colorize(highlight_color, cur_length)
        rhs_length = ui.colorize(highlight_color, new_length)

        return lhs_length, rhs_length, changed

    def make_line(self, item, track_info):
        """Extract changes from item -> new TrackInfo object, and colorize
        appropriately. Returns (lhs, rhs) for column printing.
        """
        # Track titles.
        lhs_title, rhs_title, diff_title = self.make_track_titles(
            item, track_info
        )
        # Track number change.
        lhs_track, rhs_track, diff_track = self.make_track_numbers(
            item, track_info
        )
        # Length change.
        lhs_length, rhs_length, diff_length = self.make_track_lengths(
            item, track_info
        )

        changed = diff_title or diff_track or diff_length

        # Construct lhs and rhs dicts.
        # Previously, we printed the penalties, however this is no longer
        # the case, thus the 'info' dictionary is unneeded.
        # penalties = penalty_string(self.match.distance.tracks[track_info])

        lhs = {
            "prefix": f"{self.changed_prefix if changed else '*'} {lhs_track} ",
            "contents": lhs_title,
            "suffix": f" {lhs_length}",
        }
        rhs = {"prefix": "", "contents": "", "suffix": ""}
        if not changed:
            # Only return the left side, as nothing changed.
            return (lhs, rhs)
        else:
            # Construct a dictionary for the "changed to" side
            rhs = {
                "prefix": f"{rhs_track} ",
                "contents": rhs_title,
                "suffix": f" {rhs_length}",
            }
            return (lhs, rhs)

    def print_tracklist(self, lines):
        """Calculates column widths for tracks stored as line tuples:
        (left, right). Then prints each line of tracklist.
        """
        if len(lines) == 0:
            # If no lines provided, e.g. details not required, do nothing.
            return

        def get_width(side):
            """Return the width of left or right in uncolorized characters."""
            try:
                return len(
                    ui.uncolorize(
                        " ".join(
                            [side["prefix"], side["contents"], side["suffix"]]
                        )
                    )
                )
            except KeyError:
                # An empty dictionary -> Nothing to report
                return 0

        # Check how to fit content into terminal window
        indent_width = len(self.indent_tracklist)
        terminal_width = ui.term_width()
        joiner_width = len("".join(["* ", " -> "]))
        col_width = (terminal_width - indent_width - joiner_width) // 2
        max_width_l = max(get_width(line_tuple[0]) for line_tuple in lines)
        max_width_r = max(get_width(line_tuple[1]) for line_tuple in lines)

        if (
            (max_width_l <= col_width)
            and (max_width_r <= col_width)
            or (
                ((max_width_l > col_width) or (max_width_r > col_width))
                and ((max_width_l + max_width_r) <= col_width * 2)
            )
        ):
            # All content fits. Either both maximum widths are below column
            # widths, or one of the columns is larger than allowed but the
            # other is smaller than allowed.
            # In this case we can afford to shrink the columns to fit their
            # largest string
            col_width_l = max_width_l
            col_width_r = max_width_r
        else:
            # Not all content fits - stick with original half/half split
            col_width_l = col_width
            col_width_r = col_width

        # Print out each line, using the calculated width from above.
        for left, right in lines:
            left["width"] = col_width_l
            right["width"] = col_width_r
            self.print_layout(self.indent_tracklist, left, right)


class AlbumChange(ChangeRepresentation):
    """Album change representation, setting cur_album"""

    def __init__(self, cur_artist, cur_album, match):
        super().__init__()
        self.cur_artist = cur_artist
        self.cur_album = cur_album
        self.match = match

    def show_match_tracks(self):
        """Print out the tracks of the match, summarizing changes the match
        suggests for them.
        """
        # Tracks.
        # match is an AlbumMatch NamedTuple, mapping is a dict
        # Sort the pairs by the track_info index (at index 1 of the NamedTuple)
        pairs = list(self.match.mapping.items())
        pairs.sort(key=lambda item_and_track_info: item_and_track_info[1].index)
        # Build up LHS and RHS for track difference display. The `lines` list
        # contains `(left, right)` tuples.
        lines = []
        medium = disctitle = None
        for item, track_info in pairs:
            # If the track is the first on a new medium, show medium
            # number and title.
            if medium != track_info.medium or disctitle != track_info.disctitle:
                # Create header for new medium
                header = self.make_medium_info_line(track_info)
                if header != "":
                    # Print tracks from previous medium
                    self.print_tracklist(lines)
                    lines = []
                    print_(f"{self.indent_detail}{header}")
                # Save new medium details for future comparison.
                medium, disctitle = track_info.medium, track_info.disctitle

            # Construct the line tuple for the track.
            left, right = self.make_line(item, track_info)
            if right["contents"] != "":
                lines.append((left, right))
            else:
                if config["import"]["detail"]:
                    lines.append((left, right))
        self.print_tracklist(lines)

        # Missing and unmatched tracks.
        if self.match.extra_tracks:
            print_(
                "Missing tracks"
                f" ({len(self.match.extra_tracks)}/{len(self.match.info.tracks)} -"
                f" {len(self.match.extra_tracks) / len(self.match.info.tracks):.1%}):"
            )
        for track_info in self.match.extra_tracks:
            line = f" ! {track_info.title} (#{self.format_index(track_info)})"
            if track_info.length:
                line += f" ({human_seconds_short(track_info.length)})"
            print_(ui.colorize("text_warning", line))
        if self.match.extra_items:
            print_(f"Unmatched tracks ({len(self.match.extra_items)}):")
        for item in self.match.extra_items:
            line = f" ! {item.title} (#{self.format_index(item)})"
            if item.length:
                line += f" ({human_seconds_short(item.length)})"
            print_(ui.colorize("text_warning", line))


class TrackChange(ChangeRepresentation):
    """Track change representation, comparing item with match."""

    def __init__(self, cur_artist, cur_title, match):
        super().__init__()
        self.cur_artist = cur_artist
        self.cur_title = cur_title
        self.match = match


def show_change(cur_artist, cur_album, match):
    """Print out a representation of the changes that will be made if an
    album's tags are changed according to `match`, which must be an AlbumMatch
    object.
    """
    change = AlbumChange(
        cur_artist=cur_artist, cur_album=cur_album, match=match
    )

    # Print the match header.
    change.show_match_header()

    # Print the match details.
    change.show_match_details()

    # Print the match tracks.
    change.show_match_tracks()


def show_item_change(item, match):
    """Print out the change that would occur by tagging `item` with the
    metadata from `match`, a TrackMatch object.
    """
    change = TrackChange(
        cur_artist=item.artist, cur_title=item.title, match=match
    )
    # Print the match header.
    change.show_match_header()
    # Print the match details.
    change.show_match_details()


def summarize_items(items, singleton):
    """Produces a brief summary line describing a set of items. Used for
    manually resolving duplicates during import.

    `items` is a list of `Item` objects. `singleton` indicates whether
    this is an album or single-item import (if the latter, them `items`
    should only have one element).
    """
    summary_parts = []
    if not singleton:
        summary_parts.append(f"{len(items)} items")

    format_counts = {}
    for item in items:
        format_counts[item.format] = format_counts.get(item.format, 0) + 1
    if len(format_counts) == 1:
        # A single format.
        summary_parts.append(items[0].format)
    else:
        # Enumerate all the formats by decreasing frequencies:
        for fmt, count in sorted(
            format_counts.items(),
            key=lambda fmt_and_count: (-fmt_and_count[1], fmt_and_count[0]),
        ):
            summary_parts.append(f"{fmt} {count}")

    if items:
        average_bitrate = sum([item.bitrate for item in items]) / len(items)
        total_duration = sum([item.length for item in items])
        total_filesize = sum([item.filesize for item in items])
        summary_parts.append(f"{int(average_bitrate / 1000)}kbps")
        if items[0].format == "FLAC":
            sample_bits = (
                f"{round(int(items[0].samplerate) / 1000, 1)}kHz"
                f"/{items[0].bitdepth} bit"
            )
            summary_parts.append(sample_bits)
        summary_parts.append(human_seconds_short(total_duration))
        summary_parts.append(human_bytes(total_filesize))

    return ", ".join(summary_parts)


def _summary_judgment(rec):
    """Determines whether a decision should be made without even asking
    the user. This occurs in quiet mode and when an action is chosen for
    NONE recommendations. Return None if the user should be queried.
    Otherwise, returns an action. May also print to the console if a
    summary judgment is made.
    """

    if config["import"]["quiet"]:
        if rec == Recommendation.strong:
            return importer.Action.APPLY
        else:
            action = config["import"]["quiet_fallback"].as_choice(
                {
                    "skip": importer.Action.SKIP,
                    "asis": importer.Action.ASIS,
                }
            )
    elif config["import"]["timid"]:
        return None
    elif rec == Recommendation.none:
        action = config["import"]["none_rec_action"].as_choice(
            {
                "skip": importer.Action.SKIP,
                "asis": importer.Action.ASIS,
                "ask": None,
            }
        )
    else:
        return None

    if action == importer.Action.SKIP:
        print_("Skipping.")
    elif action == importer.Action.ASIS:
        print_("Importing as-is.")
    return action


class PromptChoice(NamedTuple):
    short: str
    long: str
    callback: Any


def choose_candidate(
    candidates,
    singleton,
    rec,
    cur_artist=None,
    cur_album=None,
    item=None,
    itemcount=None,
    choices=[],
):
    """Given a sorted list of candidates, ask the user for a selection
    of which candidate to use. Applies to both full albums and
    singletons  (tracks). Candidates are either AlbumMatch or TrackMatch
    objects depending on `singleton`. for albums, `cur_artist`,
    `cur_album`, and `itemcount` must be provided. For singletons,
    `item` must be provided.

    `choices` is a list of `PromptChoice`s to be used in each prompt.

    Returns one of the following:
    * the result of the choice, which may be SKIP or ASIS
    * a candidate (an AlbumMatch/TrackMatch object)
    * a chosen `PromptChoice` from `choices`
    """
    # Sanity check.
    if singleton:
        assert item is not None
    else:
        assert cur_artist is not None
        assert cur_album is not None

    # Build helper variables for the prompt choices.
    choice_opts = tuple(c.long for c in choices)
    choice_actions = {c.short: c for c in choices}

    # Zero candidates.
    if not candidates:
        if singleton:
            print_("No matching recordings found.")
        else:
            print_(f"No matching release found for {itemcount} tracks.")
            print_(
                "For help, see: "
                "https://beets.readthedocs.org/en/latest/faq.html#nomatch"
            )
        sel = ui.input_options(choice_opts)
        if sel in choice_actions:
            return choice_actions[sel]
        else:
            assert False

    # Is the change good enough?
    bypass_candidates = False
    if rec != Recommendation.none:
        match = candidates[0]
        bypass_candidates = True

    while True:
        # Display and choose from candidates.
        require = rec <= Recommendation.low

        if not bypass_candidates:
            # Display list of candidates.
            print_("")
            print_(
                f"Finding tags for {'track' if singleton else 'album'} "
                f'"{item.artist if singleton else cur_artist} -'
                f' {item.title if singleton else cur_album}".'
            )

            print_("  Candidates:")
            for i, match in enumerate(candidates):
                # Index, metadata, and distance.
                index0 = f"{i + 1}."
                index = dist_colorize(index0, match.distance)
                dist = f"({(1 - match.distance) * 100:.1f}%)"
                distance = dist_colorize(dist, match.distance)
                metadata = (
                    f"{match.info.artist} -"
                    f" {match.info.title if singleton else match.info.album}"
                )
                if i == 0:
                    metadata = dist_colorize(metadata, match.distance)
                else:
                    metadata = ui.colorize("text_highlight_minor", metadata)
                line1 = [index, distance, metadata]
                print_(f"  {' '.join(line1)}")

                # Penalties.
                penalties = penalty_string(match.distance, 3)
                if penalties:
                    print_(f"{' ' * 13}{penalties}")

                # Disambiguation
                disambig = disambig_string(match.info)
                if disambig:
                    print_(f"{' ' * 13}{disambig}")

            # Ask the user for a choice.
            sel = ui.input_options(choice_opts, numrange=(1, len(candidates)))
            if sel == "m":
                pass
            elif sel in choice_actions:
                return choice_actions[sel]
            else:  # Numerical selection.
                match = candidates[sel - 1]
                if sel != 1:
                    # When choosing anything but the first match,
                    # disable the default action.
                    require = True
        bypass_candidates = False

        # Show what we're about to do.
        if singleton:
            show_item_change(item, match)
        else:
            show_change(cur_artist, cur_album, match)

        # Exact match => tag automatically if we're not in timid mode.
        if rec == Recommendation.strong and not config["import"]["timid"]:
            return match

        # Ask for confirmation.
        default = config["import"]["default_action"].as_choice(
            {
                "apply": "a",
                "skip": "s",
                "asis": "u",
                "none": None,
            }
        )
        if default is None:
            require = True
        # Bell ring when user interaction is needed.
        if config["import"]["bell"]:
            ui.print_("\a", end="")
        sel = ui.input_options(
            ("Apply", "More candidates") + choice_opts,
            require=require,
            default=default,
        )
        if sel == "a":
            return match
        elif sel in choice_actions:
            return choice_actions[sel]


def manual_search(session, task):
    """Get a new `Proposal` using manual search criteria.

    Input either an artist and album (for full albums) or artist and
    track name (for singletons) for manual search.
    """
    artist = input_("Artist:").strip()
    name = input_("Album:" if task.is_album else "Track:").strip()

    if task.is_album:
        _, _, prop = autotag.tag_album(task.items, artist, name)
        return prop
    else:
        return autotag.tag_item(task.item, artist, name)


def manual_id(session, task):
    """Get a new `Proposal` using a manually-entered ID.

    Input an ID, either for an album ("release") or a track ("recording").
    """
    prompt = f"Enter {'release' if task.is_album else 'recording'} ID:"
    search_id = input_(prompt).strip()

    if task.is_album:
        _, _, prop = autotag.tag_album(task.items, search_ids=search_id.split())
        return prop
    else:
        return autotag.tag_item(task.item, search_ids=search_id.split())


def abort_action(session, task):
    """A prompt choice callback that aborts the importer."""
    raise importer.ImportAbortError()


class TerminalImportSession(importer.ImportSession):
    """An import session that runs in a terminal."""

    def choose_match(self, task):
        """Given an initial autotagging of items, go through an interactive
        dance with the user to ask for a choice of metadata. Returns an
        AlbumMatch object, ASIS, or SKIP.
        """
        # Show what we're tagging.
        print_()

        path_str0 = displayable_path(task.paths, "\n")
        path_str = ui.colorize("import_path", path_str0)
        items_str0 = f"({len(task.items)} items)"
        items_str = ui.colorize("import_path_items", items_str0)
        print_(" ".join([path_str, items_str]))

        # Let plugins display info or prompt the user before we go through the
        # process of selecting candidate.
        results = plugins.send(
            "import_task_before_choice", session=self, task=task
        )
        actions = [action for action in results if action]

        if len(actions) == 1:
            return actions[0]
        elif len(actions) > 1:
            raise plugins.PluginConflictError(
                "Only one handler for `import_task_before_choice` may return "
                "an action."
            )

        # Take immediate action if appropriate.
        action = _summary_judgment(task.rec)
        if action == importer.Action.APPLY:
            match = task.candidates[0]
            show_change(task.cur_artist, task.cur_album, match)
            return match
        elif action is not None:
            return action

        # Loop until we have a choice.
        while True:
            # Ask for a choice from the user. The result of
            # `choose_candidate` may be an `importer.Action`, an
            # `AlbumMatch` object for a specific selection, or a
            # `PromptChoice`.
            choices = self._get_choices(task)
            choice = choose_candidate(
                task.candidates,
                False,
                task.rec,
                task.cur_artist,
                task.cur_album,
                itemcount=len(task.items),
                choices=choices,
            )

            # Basic choices that require no more action here.
            if choice in (importer.Action.SKIP, importer.Action.ASIS):
                # Pass selection to main control flow.
                return choice

            # Plugin-provided choices. We invoke the associated callback
            # function.
            elif choice in choices:
                post_choice = choice.callback(self, task)
                if isinstance(post_choice, importer.Action):
                    return post_choice
                elif isinstance(post_choice, autotag.Proposal):
                    # Use the new candidates and continue around the loop.
                    task.candidates = post_choice.candidates
                    task.rec = post_choice.recommendation

            # Otherwise, we have a specific match selection.
            else:
                # We have a candidate! Finish tagging. Here, choice is an
                # AlbumMatch object.
                assert isinstance(choice, autotag.AlbumMatch)
                return choice

    def choose_item(self, task):
        """Ask the user for a choice about tagging a single item. Returns
        either an action constant or a TrackMatch object.
        """
        print_()
        print_(displayable_path(task.item.path))
        candidates, rec = task.candidates, task.rec

        # Take immediate action if appropriate.
        action = _summary_judgment(task.rec)
        if action == importer.Action.APPLY:
            match = candidates[0]
            show_item_change(task.item, match)
            return match
        elif action is not None:
            return action

        while True:
            # Ask for a choice.
            choices = self._get_choices(task)
            choice = choose_candidate(
                candidates, True, rec, item=task.item, choices=choices
            )

            if choice in (importer.Action.SKIP, importer.Action.ASIS):
                return choice

            elif choice in choices:
                post_choice = choice.callback(self, task)
                if isinstance(post_choice, importer.Action):
                    return post_choice
                elif isinstance(post_choice, autotag.Proposal):
                    candidates = post_choice.candidates
                    rec = post_choice.recommendation

            else:
                # Chose a candidate.
                assert isinstance(choice, autotag.TrackMatch)
                return choice

    def resolve_duplicate(self, task, found_duplicates):
        """Decide what to do when a new album or item seems similar to one
        that's already in the library.
        """
        log.warning(
            "This {} is already in the library!",
            ("album" if task.is_album else "item"),
        )

        if config["import"]["quiet"]:
            # In quiet mode, don't prompt -- just skip.
            log.info("Skipping.")
            sel = "s"
        else:
            # Print some detail about the existing and new items so the
            # user can make an informed decision.
            for duplicate in found_duplicates:
                print_(
                    "Old: "
                    + summarize_items(
                        (
                            list(duplicate.items())
                            if task.is_album
                            else [duplicate]
                        ),
                        not task.is_album,
                    )
                )
                if config["import"]["duplicate_verbose_prompt"]:
                    if task.is_album:
                        for dup in duplicate.items():
                            print(f"  {dup}")
                    else:
                        print(f"  {duplicate}")

            print_(
                "New: "
                + summarize_items(
                    task.imported_items(),
                    not task.is_album,
                )
            )
            if config["import"]["duplicate_verbose_prompt"]:
                for item in task.imported_items():
                    print(f"  {item}")

            sel = ui.input_options(
                ("Skip new", "Keep all", "Remove old", "Merge all")
            )

        if sel == "s":
            # Skip new.
            task.set_choice(importer.Action.SKIP)
        elif sel == "k":
            # Keep both. Do nothing; leave the choice intact.
            pass
        elif sel == "r":
            # Remove old.
            task.should_remove_duplicates = True
        elif sel == "m":
            task.should_merge_duplicates = True
        else:
            assert False

    def should_resume(self, path):
        return ui.input_yn(
            f"Import of the directory:\n{displayable_path(path)}\n"
            "was interrupted. Resume (Y/n)?"
        )

    def _get_choices(self, task):
        """Get the list of prompt choices that should be presented to the
        user. This consists of both built-in choices and ones provided by
        plugins.

        The `before_choose_candidate` event is sent to the plugins, with
        session and task as its parameters. Plugins are responsible for
        checking the right conditions and returning a list of `PromptChoice`s,
        which is flattened and checked for conflicts.

        If two or more choices have the same short letter, a warning is
        emitted and all but one choices are discarded, giving preference
        to the default importer choices.

        Returns a list of `PromptChoice`s.
        """
        # Standard, built-in choices.
        choices = [
            PromptChoice("s", "Skip", lambda s, t: importer.Action.SKIP),
            PromptChoice("u", "Use as-is", lambda s, t: importer.Action.ASIS),
        ]
        if task.is_album:
            choices += [
                PromptChoice(
                    "t", "as Tracks", lambda s, t: importer.Action.TRACKS
                ),
                PromptChoice(
                    "g", "Group albums", lambda s, t: importer.Action.ALBUMS
                ),
            ]
        choices += [
            PromptChoice("e", "Enter search", manual_search),
            PromptChoice("i", "enter Id", manual_id),
            PromptChoice("b", "aBort", abort_action),
        ]

        # Send the before_choose_candidate event and flatten list.
        extra_choices = list(
            chain(
                *plugins.send(
                    "before_choose_candidate", session=self, task=task
                )
            )
        )

        # Add a "dummy" choice for the other baked-in option, for
        # duplicate checking.
        all_choices = (
            [
                PromptChoice("a", "Apply", None),
            ]
            + choices
            + extra_choices
        )

        # Check for conflicts.
        short_letters = [c.short for c in all_choices]
        if len(short_letters) != len(set(short_letters)):
            # Duplicate short letter has been found.
            duplicates = [
                i for i, count in Counter(short_letters).items() if count > 1
            ]
            for short in duplicates:
                # Keep the first of the choices, removing the rest.
                dup_choices = [c for c in all_choices if c.short == short]
                for c in dup_choices[1:]:
                    log.warning(
                        "Prompt choice '{0.long}' removed due to conflict "
                        "with '{1[0].long}' (short letter: '{0.short}')",
                        c,
                        dup_choices,
                    )
                    extra_choices.remove(c)

        return choices + extra_choices


# The import command.


def import_files(lib, paths: list[bytes], query):
    """Import the files in the given list of paths or matching the
    query.
    """
    # Check parameter consistency.
    if config["import"]["quiet"] and config["import"]["timid"]:
        raise ui.UserError("can't be both quiet and timid")

    # Open the log.
    if config["import"]["log"].get() is not None:
        logpath = syspath(config["import"]["log"].as_filename())
        try:
            loghandler = logging.FileHandler(logpath, encoding="utf-8")
        except OSError:
            raise ui.UserError(
                "Could not open log file for writing:"
                f" {displayable_path(logpath)}"
            )
    else:
        loghandler = None

    # Never ask for input in quiet mode.
    if config["import"]["resume"].get() == "ask" and config["import"]["quiet"]:
        config["import"]["resume"] = False

    session = TerminalImportSession(lib, loghandler, paths, query)
    session.run()

    # Emit event.
    plugins.send("import", lib=lib, paths=paths)


def import_func(lib, opts, args: list[str]):
    config["import"].set_args(opts)

    # Special case: --copy flag suppresses import_move (which would
    # otherwise take precedence).
    if opts.copy:
        config["import"]["move"] = False

    if opts.library:
        query = args
        byte_paths = []
    else:
        query = None
        paths = args

        # The paths from the logfiles go into a separate list to allow handling
        # errors differently from user-specified paths.
        paths_from_logfiles = list(_parse_logfiles(opts.from_logfiles or []))

        if not paths and not paths_from_logfiles:
            raise ui.UserError("no path specified")

        byte_paths = [os.fsencode(p) for p in paths]
        paths_from_logfiles = [os.fsencode(p) for p in paths_from_logfiles]

        # Check the user-specified directories.
        for path in byte_paths:
            if not os.path.exists(syspath(normpath(path))):
                raise ui.UserError(
                    f"no such file or directory: {displayable_path(path)}"
                )

        # Check the directories from the logfiles, but don't throw an error in
        # case those paths don't exist. Maybe some of those paths have already
        # been imported and moved separately, so logging a warning should
        # suffice.
        for path in paths_from_logfiles:
            if not os.path.exists(syspath(normpath(path))):
                log.warning(
                    "No such file or directory: {}", displayable_path(path)
                )
                continue

            byte_paths.append(path)

        # If all paths were read from a logfile, and none of them exist, throw
        # an error
        if not paths:
            raise ui.UserError("none of the paths are importable")

    import_files(lib, byte_paths, query)


import_cmd = ui.Subcommand(
    "import", help="import new music", aliases=("imp", "im")
)
import_cmd.parser.add_option(
    "-c",
    "--copy",
    action="store_true",
    default=None,
    help="copy tracks into library directory (default)",
)
import_cmd.parser.add_option(
    "-C",
    "--nocopy",
    action="store_false",
    dest="copy",
    help="don't copy tracks (opposite of -c)",
)
import_cmd.parser.add_option(
    "-m",
    "--move",
    action="store_true",
    dest="move",
    help="move tracks into the library (overrides -c)",
)
import_cmd.parser.add_option(
    "-w",
    "--write",
    action="store_true",
    default=None,
    help="write new metadata to files' tags (default)",
)
import_cmd.parser.add_option(
    "-W",
    "--nowrite",
    action="store_false",
    dest="write",
    help="don't write metadata (opposite of -w)",
)
import_cmd.parser.add_option(
    "-a",
    "--autotag",
    action="store_true",
    dest="autotag",
    help="infer tags for imported files (default)",
)
import_cmd.parser.add_option(
    "-A",
    "--noautotag",
    action="store_false",
    dest="autotag",
    help="don't infer tags for imported files (opposite of -a)",
)
import_cmd.parser.add_option(
    "-p",
    "--resume",
    action="store_true",
    default=None,
    help="resume importing if interrupted",
)
import_cmd.parser.add_option(
    "-P",
    "--noresume",
    action="store_false",
    dest="resume",
    help="do not try to resume importing",
)
import_cmd.parser.add_option(
    "-q",
    "--quiet",
    action="store_true",
    dest="quiet",
    help="never prompt for input: skip albums instead",
)
import_cmd.parser.add_option(
    "--quiet-fallback",
    type="string",
    dest="quiet_fallback",
    help="decision in quiet mode when no strong match: skip or asis",
)
import_cmd.parser.add_option(
    "-l",
    "--log",
    dest="log",
    help="file to log untaggable albums for later review",
)
import_cmd.parser.add_option(
    "-s",
    "--singletons",
    action="store_true",
    help="import individual tracks instead of full albums",
)
import_cmd.parser.add_option(
    "-t",
    "--timid",
    dest="timid",
    action="store_true",
    help="always confirm all actions",
)
import_cmd.parser.add_option(
    "-L",
    "--library",
    dest="library",
    action="store_true",
    help="retag items matching a query",
)
import_cmd.parser.add_option(
    "-i",
    "--incremental",
    dest="incremental",
    action="store_true",
    help="skip already-imported directories",
)
import_cmd.parser.add_option(
    "-I",
    "--noincremental",
    dest="incremental",
    action="store_false",
    help="do not skip already-imported directories",
)
import_cmd.parser.add_option(
    "-R",
    "--incremental-skip-later",
    action="store_true",
    dest="incremental_skip_later",
    help="do not record skipped files during incremental import",
)
import_cmd.parser.add_option(
    "-r",
    "--noincremental-skip-later",
    action="store_false",
    dest="incremental_skip_later",
    help="record skipped files during incremental import",
)
import_cmd.parser.add_option(
    "--from-scratch",
    dest="from_scratch",
    action="store_true",
    help="erase existing metadata before applying new metadata",
)
import_cmd.parser.add_option(
    "--flat",
    dest="flat",
    action="store_true",
    help="import an entire tree as a single album",
)
import_cmd.parser.add_option(
    "-g",
    "--group-albums",
    dest="group_albums",
    action="store_true",
    help="group tracks in a folder into separate albums",
)
import_cmd.parser.add_option(
    "--pretend",
    dest="pretend",
    action="store_true",
    help="just print the files to import",
)
import_cmd.parser.add_option(
    "-S",
    "--search-id",
    dest="search_ids",
    action="append",
    metavar="ID",
    help="restrict matching to a specific metadata backend ID",
)
import_cmd.parser.add_option(
    "--from-logfile",
    dest="from_logfiles",
    action="append",
    metavar="PATH",
    help="read skipped paths from an existing logfile",
)
import_cmd.parser.add_option(
    "--set",
    dest="set_fields",
    action="callback",
    callback=_store_dict,
    metavar="FIELD=VALUE",
    help="set the given fields to the supplied values",
)
import_cmd.func = import_func
default_commands.append(import_cmd)


# write: Write tags into files.


def write_items(lib, query, pretend, force):
    """Write tag information from the database to the respective files
    in the filesystem.
    """
    items, albums = _do_query(lib, query, False, False)

    for item in items:
        # Item deleted?
        if not os.path.exists(syspath(item.path)):
            log.info("missing file: {.filepath}", item)
            continue

        # Get an Item object reflecting the "clean" (on-disk) state.
        try:
            clean_item = library.Item.from_path(item.path)
        except library.ReadError as exc:
            log.error("error reading {.filepath}: {}", item, exc)
            continue

        # Check for and display changes.
        changed = ui.show_model_changes(
            item, clean_item, library.Item._media_tag_fields, force
        )
        if (changed or force) and not pretend:
            # We use `try_sync` here to keep the mtime up to date in the
            # database.
            item.try_sync(True, False)


def write_func(lib, opts, args):
    write_items(lib, args, opts.pretend, opts.force)


write_cmd = ui.Subcommand("write", help="write tag information to files")
write_cmd.parser.add_option(
    "-p",
    "--pretend",
    action="store_true",
    help="show all changes but do nothing",
)
write_cmd.parser.add_option(
    "-f",
    "--force",
    action="store_true",
    help="write tags even if the existing tags match the database",
)
write_cmd.func = write_func
default_commands.append(write_cmd)
