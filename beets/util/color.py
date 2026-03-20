from __future__ import annotations

import os
import re
from functools import cache
from typing import Literal

import confuse

from beets import config

# ANSI terminal colorization code heavily inspired by pygments:
# https://bitbucket.org/birkenfeld/pygments-main/src/default/pygments/console.py
# (pygments is by Tim Hatch, Armin Ronacher, et al.)
COLOR_ESCAPE = "\x1b"
LEGACY_COLORS = {
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
CODE_BY_COLOR = {
    # Styles.
    "normal": 0,
    "bold": 1,
    "faint": 2,
    "italic": 3,
    "underline": 4,
    "blink_slow": 5,
    "blink_rapid": 6,
    "inverse": 7,
    "conceal": 8,
    "crossed_out": 9,
    # Text colors.
    "black": 30,
    "red": 31,
    "green": 32,
    "yellow": 33,
    "blue": 34,
    "magenta": 35,
    "cyan": 36,
    "white": 37,
    "bright_black": 90,
    "bright_red": 91,
    "bright_green": 92,
    "bright_yellow": 93,
    "bright_blue": 94,
    "bright_magenta": 95,
    "bright_cyan": 96,
    "bright_white": 97,
    # Background colors.
    "bg_black": 40,
    "bg_red": 41,
    "bg_green": 42,
    "bg_yellow": 43,
    "bg_blue": 44,
    "bg_magenta": 45,
    "bg_cyan": 46,
    "bg_white": 47,
    "bg_bright_black": 100,
    "bg_bright_red": 101,
    "bg_bright_green": 102,
    "bg_bright_yellow": 103,
    "bg_bright_blue": 104,
    "bg_bright_magenta": 105,
    "bg_bright_cyan": 106,
    "bg_bright_white": 107,
}
RESET_COLOR = f"{COLOR_ESCAPE}[39;49;00m"
# Precompile common ANSI-escape regex patterns
ANSI_CODE_REGEX = re.compile(rf"({COLOR_ESCAPE}\[[;0-9]*m)")
ESC_TEXT_REGEX = re.compile(
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
    template_dict: dict[ColorName, confuse.OneOf[str | list[str]]] = {
        n: confuse.OneOf(
            [
                confuse.Choice(sorted(LEGACY_COLORS)),
                confuse.Sequence(confuse.Choice(sorted(CODE_BY_COLOR))),
            ]
        )
        for n in ColorName.__args__  # type: ignore[attr-defined]
    }
    template = confuse.MappingTemplate(template_dict)
    colors_by_color_name = {
        k: (v if isinstance(v, list) else LEGACY_COLORS.get(v, [v]))
        for k, v in config["ui"]["colors"].get(template).items()
    }

    return {
        n: ";".join(str(CODE_BY_COLOR[c]) for c in colors)
        for n, colors in colors_by_color_name.items()
    }


def _colorize(color_name: ColorName, text: str) -> str:
    """Apply ANSI color formatting to text based on configuration settings."""
    color_code = get_color_config()[color_name]
    return f"{COLOR_ESCAPE}[{color_code}m{text}{RESET_COLOR}"


def colorize(color_name: ColorName, text: str) -> str:
    """Colorize text when color output is enabled."""
    if config["ui"]["color"] and "NO_COLOR" not in os.environ:
        return _colorize(color_name, text)

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


def color_split(colored_text: str, index: int) -> tuple[str, str]:
    length = 0
    pre_split = ""
    post_split = ""
    found_color_code = None
    found_split = False
    for part in ANSI_CODE_REGEX.split(colored_text):
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
                    split_index = index - (length - color_len(part))
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
