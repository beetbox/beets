from beets import ui

from .color import (
    ESC_TEXT_REGEX,
    RESET_COLOR,
    color_len,
    color_split,
    uncolorize,
)


def indent(count):
    """Returns a string with `count` many spaces."""
    return " " * count


def split_into_lines(string, width_tuple):
    """Splits string into a list of substrings at whitespace.

    `width_tuple` is a 3-tuple of `(first_width, last_width, middle_width)`.
    The first substring has a length not longer than `first_width`, the last
    substring has a length not longer than `last_width`, and all other
    substrings have a length not longer than `middle_width`.
    `string` may contain ANSI codes at word borders.
    """
    first_width, middle_width, last_width = width_tuple
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
    result = []
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
        fits_middle = len(result) != 0 and color_len(pot_substr) <= middle_width
        if fits_first or fits_middle:
            # Fitted(!) let's try and add another word before appending
            next_substr = pot_substr
            previous_fit = True
        elif not fits_first and not fits_middle and previous_fit:
            # Extra word didn't fit, append what we have
            result.append(next_substr)
            next_substr = words[i]
            previous_fit = color_len(next_substr) <= middle_width
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
                    result.append(pot_substr[:middle_width])
                    next_substr = pot_substr[middle_width:]
            else:
                # Colored strings
                if len(result) == 0:
                    this_line, next_line = color_split(pot_substr, first_width)
                    result.append(this_line)
                    next_substr = next_line
                else:
                    this_line, next_line = color_split(pot_substr, middle_width)
                    result.append(this_line)
                    next_substr = next_line
            previous_fit = color_len(next_substr) <= middle_width

    # We finished constructing the substrings, but the last substring
    # has not yet been added to the result.
    result.append(next_substr)
    # Also, the length of the last substring was only checked against
    # `middle_width`. Append an empty substring as the new last substring if
    # the last substring is too long.
    if not color_len(next_substr) <= last_width:
        result.append("")
    return result


def print_column_layout(
    indent_str, left, right, separator=" -> ", max_width=ui.term_width()
):
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
    if f"{right['prefix']}{right['contents']}{right['suffix']}" == "":
        # No right hand information, so we don't need a separator.
        separator = ""
    first_line_no_wrap = (
        f"{indent_str}{left['prefix']}{left['contents']}{left['suffix']}"
        f"{separator}{right['prefix']}{right['contents']}{right['suffix']}"
    )
    if color_len(first_line_no_wrap) < max_width:
        # Everything fits, print out line.
        ui.print_(first_line_no_wrap)
    else:
        # Wrap into columns
        if "width" not in left or "width" not in right:
            # If widths have not been defined, set to share space.
            left["width"] = (
                max_width - len(indent_str) - color_len(separator)
            ) // 2
            right["width"] = (
                max_width - len(indent_str) - color_len(separator)
            ) // 2
        # On the first line, account for suffix as well as prefix
        left_width_tuple = (
            left["width"]
            - color_len(left["prefix"])
            - color_len(left["suffix"]),
            left["width"] - color_len(left["prefix"]),
            left["width"] - color_len(left["prefix"]),
        )

        left_split = split_into_lines(left["contents"], left_width_tuple)
        right_width_tuple = (
            right["width"]
            - color_len(right["prefix"])
            - color_len(right["suffix"]),
            right["width"] - color_len(right["prefix"]),
            right["width"] - color_len(right["prefix"]),
        )

        right_split = split_into_lines(right["contents"], right_width_tuple)
        max_line_count = max(len(left_split), len(right_split))

        out = ""
        for i in range(max_line_count):
            # indentation
            out += indent_str

            # Prefix or indent_str for line
            if i == 0:
                out += left["prefix"]
            else:
                out += indent(color_len(left["prefix"]))

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
            padding = left["width"] - color_len(left["prefix"]) - left_part_len

            # Remove some padding on the first line to display
            # length
            if i == 0:
                padding -= color_len(left["suffix"])

            out += indent(padding)

            if i == 0:
                out += left["suffix"]

            # Separator between columns.
            if i == 0:
                out += separator
            else:
                out += indent(color_len(separator))

            # Right prefix, contents, padding, suffix
            if i == 0:
                out += right["prefix"]
            else:
                out += indent(color_len(right["prefix"]))

            # Line i of right hand side.
            if i < len(right_split):
                out += right_split[i]
                right_part_len = color_len(right_split[i])
            else:
                right_part_len = 0

            # Padding until end of column
            padding = (
                right["width"] - color_len(right["prefix"]) - right_part_len
            )
            # Remove some padding on the first line to display
            # length
            if i == 0:
                padding -= color_len(right["suffix"])
            out += indent(padding)
            # Length in first line
            if i == 0:
                out += right["suffix"]

            # Linebreak, except in the last line.
            if i < max_line_count - 1:
                out += "\n"

        # Constructed all of the columns, now print
        ui.print_(out)


def print_newline_layout(
    indent_str, left, right, separator=" -> ", max_width=ui.term_width()
):
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
    if f"{right['prefix']}{right['contents']}{right['suffix']}" == "":
        # No right hand information, so we don't need a separator.
        separator = ""
    first_line_no_wrap = (
        f"{indent_str}{left['prefix']}{left['contents']}{left['suffix']}"
        f"{separator}{right['prefix']}{right['contents']}{right['suffix']}"
    )
    if color_len(first_line_no_wrap) < max_width:
        # Everything fits, print out line.
        ui.print_(first_line_no_wrap)
    else:
        # Newline separation, with wrapping
        empty_space = max_width - len(indent_str)
        # On lower lines we will double the indent for clarity
        left_width_tuple = (
            empty_space,
            empty_space - len(indent_str),
            empty_space - len(indent_str),
        )
        left_str = f"{left['prefix']}{left['contents']}{left['suffix']}"
        left_split = split_into_lines(left_str, left_width_tuple)
        # Repeat calculations for rhs, including separator on first line
        right_width_tuple = (
            empty_space - color_len(separator),
            empty_space - len(indent_str),
            empty_space - len(indent_str),
        )
        right_str = f"{right['prefix']}{right['contents']}{right['suffix']}"
        right_split = split_into_lines(right_str, right_width_tuple)
        for i, line in enumerate(left_split):
            if i == 0:
                ui.print_(f"{indent_str}{line}")
            elif line != "":
                # Ignore empty lines
                ui.print_(f"{indent_str * 2}{line}")
        for i, line in enumerate(right_split):
            if i == 0:
                ui.print_(f"{indent_str}{separator}{line}")
            elif line != "":
                ui.print_(f"{indent_str * 2}{line}")
