from __future__ import annotations

import os
import re
from difflib import SequenceMatcher
from functools import cache
from itertools import chain
from typing import Final, Literal

from beets import config, util
from beets.ui._common import UserError

# Colorization.

# ANSI terminal colorization code heavily inspired by pygments:
# https://bitbucket.org/birkenfeld/pygments-main/src/default/pygments/console.py
# (pygments is by Tim Hatch, Armin Ronacher, et al.)

COLOR_ESCAPE: Final = "\x1b"
LEGACY_COLORS: Final = {
    "black": ["black"],
    "darkred": ["red"],
    "darkgreen": ["green"],
    "brown": ["yellow"],
    "darkyellow": ["yellow"],
    "darkblue": ["blue"],
    "purple": ["magenta"],
    "darkmagenta": ["magenta"],
    "teal": ["cyan"],
    "darkcyan": ["cyan"],
    "lightgray": ["white"],
    "darkgray": ["bold", "black"],
    "red": ["bold", "red"],
    "green": ["bold", "green"],
    "yellow": ["bold", "yellow"],
    "blue": ["bold", "blue"],
    "fuchsia": ["bold", "magenta"],
    "magenta": ["bold", "magenta"],
    "turquoise": ["bold", "cyan"],
    "cyan": ["bold", "cyan"],
    "white": ["bold", "white"],
}
# All ANSI Colors.
CODE_BY_COLOR: Final = {
    # Styles.
    "normal": 0,
    "bold": 1,
    "faint": 2,
    # "italic":       3,
    "underline": 4,
    # "blink_slow":   5,
    # "blink_rapid":  6,
    "inverse": 7,
    # "conceal":      8,
    # "crossed_out":  9
    # Text colors.
    "black": 30,
    "red": 31,
    "green": 32,
    "yellow": 33,
    "blue": 34,
    "magenta": 35,
    "cyan": 36,
    "white": 37,
    # Background colors.
    "bg_black": 40,
    "bg_red": 41,
    "bg_green": 42,
    "bg_yellow": 43,
    "bg_blue": 44,
    "bg_magenta": 45,
    "bg_cyan": 46,
    "bg_white": 47,
}
RESET_COLOR: Final = f"{COLOR_ESCAPE}[39;49;00m"
# Precompile common ANSI-escape regex patterns
ANSI_CODE_REGEX: Final = re.compile(rf"({COLOR_ESCAPE}\[[;0-9]*m)")
ESC_TEXT_REGEX: Final = re.compile(
    rf"""(?P<pretext>[^{COLOR_ESCAPE}]*)
         (?P<esc>(?:{ANSI_CODE_REGEX.pattern})+)
         (?P<text>[^{COLOR_ESCAPE}]+)(?P<reset>{re.escape(RESET_COLOR)})
         (?P<posttext>[^{COLOR_ESCAPE}]*)""",
    re.VERBOSE,
)
ColorName = Literal[
    "text_success",
    "text_warning",
    "text_error",
    "text_highlight",
    "text_highlight_minor",
    "action_default",
    "action",
    # New Colors
    "text_faint",
    "import_path",
    "import_path_items",
    "action_description",
    "changed",
    "text_diff_added",
    "text_diff_removed",
]


@cache
def get_color_config() -> dict[ColorName, str]:
    """Parse and validate color configuration, converting names to ANSI codes.

    Processes the UI color configuration, handling both new list format and
    legacy single-color format. Validates all color names against known codes
    and raises an error for any invalid entries.
    """
    colors_by_color_name: dict[ColorName, list[str]] = {
        k: (v if isinstance(v, list) else LEGACY_COLORS.get(v, [v]))
        for k, v in config["ui"]["colors"].flatten().items()
    }

    invalid_colors: set[str]
    if invalid_colors := (
        set(chain.from_iterable(colors_by_color_name.values()))
        - CODE_BY_COLOR.keys()
    ):
        raise UserError(
            f"Invalid color(s) in configuration: {', '.join(invalid_colors)}"
        )

    return {
        n: ";".join(str(CODE_BY_COLOR[c]) for c in colors)
        for n, colors in colors_by_color_name.items()
    }


def colorize(color_name: ColorName, text: str) -> str:
    """Apply ANSI color formatting to text based on configuration settings.

    Returns colored text when color output is enabled and NO_COLOR environment
    variable is not set, otherwise returns plain text unchanged.
    """
    if config["ui"]["color"] and "NO_COLOR" not in os.environ:
        color_code: str = get_color_config()[color_name]
        return f"{COLOR_ESCAPE}[{color_code}m{text}{RESET_COLOR}"

    return text


def uncolorize(colored_text: str) -> str:
    """Remove colors from a string."""
    # Define a regular expression to match ANSI codes.
    # See: http://stackoverflow.com/a/2187024/1382707
    # Explanation of regular expression:
    #     \x1b     - matches ESC character
    #     \[       - matches opening square bracket
    #     [;\d]*   - matches a sequence consisting of one or more digits or
    #                semicola
    #     [A-Za-z] - matches a letter
    return ANSI_CODE_REGEX.sub("", colored_text)


def color_split(colored_text: str, index: int):
    length: int = 0
    pre_split: str = ""
    post_split: str = ""
    found_color_code: str | None = None
    found_split: bool = False
    part: str
    for part in ANSI_CODE_REGEX.split(colored_text) or ():
        # Count how many real letters we have passed
        length += color_len(part)
        if found_split:
            post_split += part
        else:
            if ANSI_CODE_REGEX.match(part):
                # This is a color code
                if part == RESET_COLOR:
                    found_color_code = None
                else:
                    found_color_code = part
                pre_split += part
            else:
                if index < length:
                    # Found part with our split in.
                    split_index: int = index - (length - color_len(part))
                    found_split = True
                    if found_color_code:
                        pre_split += f"{part[:split_index]}{RESET_COLOR}"
                        post_split += f"{found_color_code}{part[split_index:]}"
                    else:
                        pre_split += part[:split_index]
                        post_split += part[split_index:]
                else:
                    # Not found, add this part to the pre split
                    pre_split += part
    return pre_split, post_split


def color_len(colored_text: str) -> int:
    """Measure the length of a string while excluding ANSI codes from the
    measurement. The standard `len(my_string)` method also counts ANSI codes
    to the string length, which is counterproductive when layouting a
    Terminal interface.
    """
    # Return the length of the uncolored string.
    return len(uncolorize(colored_text))


def _colordiff(a: object, b: object) -> tuple[str, str]:
    """Given two values, return the same pair of strings except with
    their differences highlighted in the specified color. Strings are
    highlighted intelligently to show differences; other values are
    stringified and highlighted in their entirety.
    """
    # First, convert paths to readable format
    value: object
    for value in a, b:
        if isinstance(value, bytes):
            # A path field.
            value = util.displayable_path(value)

    if not isinstance(a, str) or not isinstance(b, str):
        # Non-strings: use ordinary equality.
        if a == b:
            return str(a), str(b)
        else:
            return (
                colorize("text_diff_removed", str(a)),
                colorize("text_diff_added", str(b)),
            )

    before: str = ""
    after: str = ""

    op: str
    a_start: int
    a_end: int
    b_start: int
    b_end: int
    matcher: SequenceMatcher[str] = SequenceMatcher(lambda x: False, a, b)
    for op, a_start, a_end, b_start, b_end in matcher.get_opcodes():
        before_part: str
        after_part: str
        before_part, after_part = a[a_start:a_end], b[b_start:b_end]
        if op in {"delete", "replace"}:
            before_part = colorize("text_diff_removed", before_part)
        if op in {"insert", "replace"}:
            after_part = colorize("text_diff_added", after_part)

        before += before_part
        after += after_part

    return before, after


def colordiff(a: object, b: object) -> tuple[str, str]:
    """Colorize differences between two values if color is enabled.
    (Like _colordiff but conditional.)
    """
    if config["ui"]["color"]:
        return _colordiff(a, b)
    else:
        return str(a), str(b)
