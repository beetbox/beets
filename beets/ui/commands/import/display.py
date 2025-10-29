import os
from collections.abc import Sequence
from functools import cached_property

from beets import autotag, config, logging, ui
from beets.autotag import hooks
from beets.util import displayable_path
from beets.util.units import human_seconds_short

VARIOUS_ARTISTS = "Various Artists"

# Global logger.
log = logging.getLogger("beets")


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
            ui.print_column_layout(indent, left, right, separator, max_width)
        else:
            ui.print_newline_layout(indent, left, right, separator, max_width)

    def show_match_header(self):
        """Print out a 'header' identifying the suggested match (album name,
        artist name,...) and summarizing the changes that would be made should
        the user accept the match.
        """
        # Print newline at beginning of change block.
        ui.print_("")

        # 'Match' line and similarity.
        ui.print_(
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
        ui.print_(
            self.indent_header
            + dist_colorize(artist_album_str, self.match.distance)
        )

        # Penalties.
        penalties = penalty_string(self.match.distance)
        if penalties:
            ui.print_(f"{self.indent_header}{penalties}")

        # Disambiguation.
        disambig = disambig_string(self.match.info)
        if disambig:
            ui.print_(f"{self.indent_header}{disambig}")

        # Data URL.
        if self.match.info.data_url:
            url = ui.colorize("text_faint", f"{self.match.info.data_url}")
            ui.print_(f"{self.indent_header}{url}")

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
            ui.print_(f"{self.indent_detail}*", "Artist:", artist_r)

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
                ui.print_(f"{self.indent_detail}*", "Album:", album_r)
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
                ui.print_(f"{self.indent_detail}*", "Title:", title_r)

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
                    ui.print_(f"{self.indent_detail}{header}")
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
            ui.print_(
                "Missing tracks"
                f" ({len(self.match.extra_tracks)}/{len(self.match.info.tracks)} -"
                f" {len(self.match.extra_tracks) / len(self.match.info.tracks):.1%}):"
            )
        for track_info in self.match.extra_tracks:
            line = f" ! {track_info.title} (#{self.format_index(track_info)})"
            if track_info.length:
                line += f" ({human_seconds_short(track_info.length)})"
            ui.print_(ui.colorize("text_warning", line))
        if self.match.extra_items:
            ui.print_(f"Unmatched tracks ({len(self.match.extra_items)}):")
        for item in self.match.extra_items:
            line = f" ! {item.title} (#{self.format_index(item)})"
            if item.length:
                line += f" ({human_seconds_short(item.length)})"
            ui.print_(ui.colorize("text_warning", line))


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
