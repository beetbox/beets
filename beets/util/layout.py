from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

import beets

from .color import (
    ESC_TEXT_REGEX,
    RESET_COLOR,
    color_len,
    color_split,
    uncolorize,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


class Side(NamedTuple):
    """A labeled segment of a two-column layout row with optional fixed width.

    Holds prefix, content, and suffix strings that together form one side of
    a formatted row. Width measurements account for ANSI color codes, which
    do not contribute to visible character count.
    """

    prefix: str
    contents: str
    suffix: str
    width: int = -1

    @property
    def rendered(self) -> str:
        """Assemble the full display string by joining prefix, contents, and suffix."""
        return f"{self.prefix}{self.contents}{self.suffix}"

    @property
    def prefix_width(self) -> int:
        """Visible character width of the prefix, excluding color codes."""
        return color_len(self.prefix)

    @property
    def suffix_width(self) -> int:
        """Visible character width of the suffix, excluding color codes."""
        return color_len(self.suffix)

    @property
    def rendered_width(self) -> int:
        """Visible character width of the fully assembled string."""
        return color_len(self.rendered)


def indent(count: int) -> str:
    """Returns a string with `count` many spaces."""
    return " " * count


def split_into_lines(string: str, first_width: int, width: int) -> list[str]:
    """Split string into a list of substrings at whitespace.

    The first substring has a length not longer than `first_width`, and the rest
    of substrings have a length not longer than `width`.

    `string` may contain ANSI codes at word borders.
    """
    words = []

    if uncolorize(string) == string:
        # No colors in string
        words = string.split()
    else:
        # Use a regex to find escapes and the text within them.
        for m in ESC_TEXT_REGEX.finditer(string):
            # m contains four groups:
            # pretext - any text before escape sequence
            # esc - intitial escape sequence
            # text - text, no escape sequence, may contain spaces
            # reset - ASCII colour reset
            space_before_text = False
            if m.group("pretext") != "":
                # Some pretext found, let's handle it
                # Add any words in the pretext
                words += m.group("pretext").split()
                if m.group("pretext")[-1] == " ":
                    # Pretext ended on a space
                    space_before_text = True
                else:
                    # Pretext ended mid-word, ensure next word
                    pass
            else:
                # pretext empty, treat as if there is a space before
                space_before_text = True
            if m.group("text")[0] == " ":
                # First character of the text is a space
                space_before_text = True
            # Now, handle the words in the main text:
            raw_words = m.group("text").split()
            if space_before_text:
                # Colorize each word with pre/post escapes
                # Reconstruct colored words
                words += [
                    f"{m['esc']}{raw_word}{RESET_COLOR}"
                    for raw_word in raw_words
                ]
            elif raw_words:
                # Pretext stops mid-word
                if m.group("esc") != RESET_COLOR:
                    # Add the rest of the current word, with a reset after it
                    words[-1] += f"{m['esc']}{raw_words[0]}{RESET_COLOR}"
                    # Add the subsequent colored words:
                    words += [
                        f"{m['esc']}{raw_word}{RESET_COLOR}"
                        for raw_word in raw_words[1:]
                    ]
                else:
                    # Caught a mid-word escape sequence
                    words[-1] += raw_words[0]
                    words += raw_words[1:]
            if (
                m.group("text")[-1] != " "
                and m.group("posttext") != ""
                and m.group("posttext")[0] != " "
            ):
                # reset falls mid-word
                post_text = m.group("posttext").split()
                words[-1] += post_text[0]
                words += post_text[1:]
            else:
                # Add any words after escape sequence
                words += m.group("posttext").split()
    result: list[str] = []
    next_substr = ""
    # Iterate over all words.
    previous_fit = False
    for i in range(len(words)):
        if i == 0:
            pot_substr = words[i]
        else:
            # (optimistically) add the next word to check the fit
            pot_substr = " ".join([next_substr, words[i]])
        # Find out if the pot(ential)_substr fits into the next substring.
        fits_first = len(result) == 0 and color_len(pot_substr) <= first_width
        fits_middle = len(result) != 0 and color_len(pot_substr) <= width
        if fits_first or fits_middle:
            # Fitted(!) let's try and add another word before appending
            next_substr = pot_substr
            previous_fit = True
        elif not fits_first and not fits_middle and previous_fit:
            # Extra word didn't fit, append what we have
            result.append(next_substr)
            next_substr = words[i]
            previous_fit = color_len(next_substr) <= width
        else:
            # Didn't fit anywhere
            if uncolorize(pot_substr) == pot_substr:
                # Simple uncolored string, append a cropped word
                if len(result) == 0:
                    # Crop word by the first_width for the first line
                    result.append(pot_substr[:first_width])
                    # add rest of word to next line
                    next_substr = pot_substr[first_width:]
                else:
                    result.append(pot_substr[:width])
                    next_substr = pot_substr[width:]
            else:
                # Colored strings
                if len(result) == 0:
                    this_line, next_line = color_split(pot_substr, first_width)
                    result.append(this_line)
                    next_substr = next_line
                else:
                    this_line, next_line = color_split(pot_substr, width)
                    result.append(this_line)
                    next_substr = next_line
            previous_fit = color_len(next_substr) <= width

    # We finished constructing the substrings, but the last substring
    # has not yet been added to the result.
    result.append(next_substr)
    return result


def get_column_layout(
    indent_str: str,
    left: Side,
    right: Side,
    max_width: int,
    separator: str,
) -> Iterator[str]:
    """Print left & right data, with separator inbetween
    'left' and 'right' have a structure of:
    {'prefix':u'','contents':u'','suffix':u'','width':0}
    In a column layout the printing will be:
    {indent_str}{lhs0}{separator}{rhs0}
            {lhs1 / padding }{rhs1}
            ...
    The first line of each column (i.e. {lhs0} or {rhs0}) is:
    {prefix}{part of contents}{suffix}
    With subsequent lines (i.e. {lhs1}, {rhs1} onwards) being the
    rest of contents, wrapped if the width would be otherwise exceeded.
    """
    if left.width == -1 or right.width == -1:
        # If widths have not been defined, set to share space.
        width = (max_width - len(indent_str) - len(separator)) // 2
        left = left._replace(width=width)
        right = right._replace(width=width)
    # On the first line, account for suffix as well as prefix
    left_width_without_prefix = left.width - left.prefix_width
    left_split = split_into_lines(
        left.contents,
        left_width_without_prefix - left.suffix_width,
        left_width_without_prefix,
    )

    right_width_without_prefix = right.width - right.prefix_width
    right_split = split_into_lines(
        right.contents,
        right_width_without_prefix - right.suffix_width,
        right_width_without_prefix,
    )

    max_line_count = max(len(left_split), len(right_split))

    out = ""
    for i in range(max_line_count):
        # indentation
        out += indent_str

        # Prefix or indent_str for line
        if i == 0:
            out += left.prefix
        else:
            out += indent(left.prefix_width)

        # Line i of left hand side contents.
        if i < len(left_split):
            out += left_split[i]
            left_part_len = color_len(left_split[i])
        else:
            left_part_len = 0

        # Padding until end of column.
        # Note: differs from original
        # column calcs in not -1 afterwards for space
        # in track number as that is included in 'prefix'
        padding = left.width - left.prefix_width - left_part_len

        # Remove some padding on the first line to display
        # length
        if i == 0:
            padding -= left.suffix_width

        out += indent(padding)

        if i == 0:
            out += left.suffix

        # Separator between columns.
        if i == 0:
            out += separator
        else:
            out += indent(len(separator))

        # Right prefix, contents, padding, suffix
        if i == 0:
            out += right.prefix
        else:
            out += indent(right.prefix_width)

        # Line i of right hand side.
        if i < len(right_split):
            out += right_split[i]
            right_part_len = color_len(right_split[i])
        else:
            right_part_len = 0

        # Padding until end of column
        padding = right.width - right.prefix_width - right_part_len
        # Remove some padding on the first line to display
        # length
        if i == 0:
            padding -= right.suffix_width
        out += indent(padding)
        # Length in first line
        if i == 0:
            out += right.suffix

        # Linebreak, except in the last line.
        if i < max_line_count - 1:
            out += "\n"

    # Constructed all of the columns, now print
    yield out


def get_newline_layout(
    indent_str: str,
    left: Side,
    right: Side,
    max_width: int,
    separator: str,
) -> Iterator[str]:
    """Prints using a newline separator between left & right if
    they go over their allocated widths. The datastructures are
    shared with the column layout. In contrast to the column layout,
    the prefix and suffix are printed at the beginning and end of
    the contents. If no wrapping is required (i.e. everything fits) the
    first line will look exactly the same as the column layout:
    {indent}{lhs0}{separator}{rhs0}
    However if this would go over the width given, the layout now becomes:
    {indent}{lhs0}
    {indent}{separator}{rhs0}
    If {lhs0} would go over the maximum width, the subsequent lines are
    indented a second time for ease of reading.
    """
    width_without_prefix = max_width - len(indent_str)
    width_without_double_prefix = max_width - 2 * len(indent_str)
    # On lower lines we will double the indent for clarity
    left_split = split_into_lines(
        left.rendered,
        width_without_prefix,
        width_without_double_prefix,
    )
    # Repeat calculations for rhs, including separator on first line
    right_split = split_into_lines(
        right.rendered,
        width_without_prefix - len(separator),
        width_without_double_prefix,
    )
    for i, line in enumerate(left_split):
        if i == 0:
            yield f"{indent_str}{line}"
        elif line != "":
            # Ignore empty lines
            yield f"{indent_str * 2}{line}"
    for i, line in enumerate(right_split):
        if i == 0:
            yield f"{indent_str}{separator}{line}"
        elif line != "":
            yield f"{indent_str * 2}{line}"


def get_layout_method() -> Callable[[str, Side, Side, int, str], Iterator[str]]:
    return beets.config["ui"]["import"]["layout"].as_choice(
        {"column": get_column_layout, "newline": get_newline_layout}
    )


def get_layout_lines(
    indent_str: str,
    left: Side,
    right: Side,
    max_width: int,
) -> Iterator[str]:
    # No right hand information, so we don't need a separator.
    separator = "" if right.rendered == "" else " -> "
    first_line_no_wrap = (
        f"{indent_str}{left.rendered}{separator}{right.rendered}"
    )
    if color_len(first_line_no_wrap) < max_width:
        # Everything fits, print out line.
        yield first_line_no_wrap
    else:
        layout_method = get_layout_method()
        yield from layout_method(indent_str, left, right, max_width, separator)
