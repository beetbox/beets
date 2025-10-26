from __future__ import annotations

import optparse
import re
import struct
import sys
import textwrap
import warnings
from typing import TYPE_CHECKING, TypeVar

from beets import config, library, util
from beets.ui._common import UserError
from beets.ui.colors import (
    ESC_TEXT_REGEX,
    RESET_COLOR,
    ColorName,
    color_len,
    color_split,
    colordiff,
    colorize,
    uncolorize,
)
from beets.util import as_string
from beets.util.functemplate import Template, template

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from typing import Any, Final, TextIO, TypedDict

    import confuse
    from typing_extensions import NotRequired, Unpack

    from beets.dbcore import db

    class ColumnLayout(TypedDict):
        prefix: str
        contents: str
        suffix: str
        width: NotRequired[int]

    class OptionParserParams(TypedDict):
        usage: NotRequired[str | None]
        option_list: NotRequired[Iterable[optparse.Option] | None]
        option_class: NotRequired[type[optparse.Option]]
        version: NotRequired[str | None]
        conflict_handler: NotRequired[str]
        description: NotRequired[str | None]
        formatter: NotRequired[optparse.HelpFormatter | None]
        add_help_option: NotRequired[bool]
        prog: NotRequired[str | None]
        epilog: NotRequired[str | None]


if not sys.version_info < (3, 12):
    from typing import override  # pyright: ignore[reportUnreachable]
else:
    from typing_extensions import override


T = TypeVar("T")


PF_KEY_QUERIES: Final = {
    "comp": "comp:true",
    "singleton": "singleton:true",
}


# Encoding utilities.


def _in_encoding() -> str:
    """Get the encoding to use for *inputting* strings from the console."""
    return _stream_encoding(sys.stdin)


def _out_encoding() -> str:
    """Get the encoding to use for *outputting* strings to the console."""
    return _stream_encoding(sys.stdout)


def _stream_encoding(stream: TextIO | Any, default: str = "utf-8") -> str:
    """A helper for `_in_encoding` and `_out_encoding`: get the stream's
    preferred encoding, using a configured override or a default
    fallback if neither is not specified.
    """
    # Configured override?
    encoding: str
    if encoding := config["terminal_encoding"].get():
        return encoding

    # For testing: When sys.stdout or sys.stdin is a StringIO under the
    # test harness, it doesn't have an `encoding` attribute. Just use
    # UTF-8.
    if not hasattr(stream, "encoding"):
        return default

    # Python's guessed output stream encoding, or UTF-8 as a fallback
    # (e.g., when piped to a file).
    return stream.encoding or default


def decargs(arglist: list[bytes]) -> list[bytes]:
    """Given a list of command-line argument bytestrings, attempts to
    decode them to Unicode strings when running under Python 2.

    .. deprecated:: 2.4.0
        This function will be removed in 3.0.0.
    """
    warnings.warn(
        "decargs() is deprecated and will be removed in version 3.0.0.",
        DeprecationWarning,
        stacklevel=2,
    )
    return arglist


def print_(*strings: str, end: str = "\n") -> None:
    """Like print, but rather than raising an error when a character
    is not in the terminal's encoding's character set, just silently
    replaces it.

    The `end` keyword argument behaves similarly to the built-in `print`
    (it defaults to a newline).
    """
    txt: str = f"{' '.join(strings or ('',))}{end}"

    # Encode the string and write it to stdout.
    # On Python 3, sys.stdout expects text strings and uses the
    # exception-throwing encoding error policy. To avoid throwing
    # errors and use our configurable encoding override, we use the
    # underlying bytes buffer instead.
    if hasattr(sys.stdout, "buffer"):
        out: bytes = txt.encode(_out_encoding(), "replace")
        _ = sys.stdout.buffer.write(out)
        _ = sys.stdout.buffer.flush()
    else:
        # In our test harnesses (e.g., DummyOut), sys.stdout.buffer
        # does not exist. We instead just record the text string.
        _ = sys.stdout.write(txt)


# Configuration wrappers.


def _bool_fallback(a: bool | None, b: bool | None) -> bool:
    """Given a boolean or None, return the original value or a fallback."""
    if a is None:
        assert isinstance(b, bool)
        return b
    else:
        assert isinstance(a, bool)
        return a


def should_write(write_opt: bool | None = None) -> bool:
    """Decide whether a command that updates metadata should also write
    tags, using the importer configuration as the default.
    """
    return _bool_fallback(write_opt, config["import"]["write"].get(bool))


def should_move(move_opt: bool | None = None) -> bool:
    """Decide whether a command that updates metadata should also move
    files when they're inside the library, using the importer
    configuration as the default.

    Specifically, commands should move files after metadata updates only
    when the importer is configured *either* to move *or* to copy files.
    They should avoid moving files when the importer is configured not
    to touch any filenames.
    """
    return _bool_fallback(
        move_opt,
        config["import"]["move"].get(bool)
        or config["import"]["copy"].get(bool),
    )


# Input prompts.


def indent(count: int) -> str:
    """Returns a string with `count` many spaces."""
    return " " * count


def input_(prompt: str | None = None) -> str:
    """Like `input`, but decodes the result to a Unicode string.
    Raises a UserError if stdin is not available. The prompt is sent to
    stdout rather than stderr. A printed between the prompt and the
    input cursor.
    """
    # raw_input incorrectly sends prompts to stderr, not stdout, so we
    # use print_() explicitly to display prompts.
    # https://bugs.python.org/issue1927
    if prompt:
        print_(prompt, end=" ")

    try:
        resp: str = input()
    except EOFError as e:
        raise UserError("stdin stream ended while input required") from e

    return resp


def input_options(
    options: Iterable[str],
    require: bool = False,
    prompt: str | None = None,
    fallback_prompt: str | None = None,
    numrange: tuple[int, int] | None = None,
    default: int | str | None = None,
    max_width: int = 72,
) -> int | str:
    """Prompts a user for input. The sequence of `options` defines the
    choices the user has. A single-letter shortcut is inferred for each
    option; the user's choice is returned as that single, lower-case
    letter. The options should be provided as lower-case strings unless
    a particular shortcut is desired; in that case, only that letter
    should be capitalized.

    By default, the first option is the default. `default` can be provided to
    override this. If `require` is provided, then there is no default. The
    prompt and fallback prompt are also inferred but can be overridden.

    If numrange is provided, it is a pair of `(high, low)` (both ints)
    indicating that, in addition to `options`, the user may enter an
    integer in that inclusive range.

    `max_width` specifies the maximum number of columns in the
    automatically generated prompt string.
    """
    # Assign single letters to each option. Also capitalize the options
    # to indicate the letter.
    letters: dict[str, str] = {}
    display_letters: list[str] = []
    capitalized: list[str] = []
    first: bool = True
    option: str
    for option in options:
        # Is a letter already capitalized?
        letter: str
        found_letter: str
        for letter in option:
            if letter.isalpha() and letter.upper() == letter:
                found_letter = letter
                break
        else:
            # Infer a letter.
            for letter in option:
                if not letter.isalpha():
                    continue  # Don't use punctuation.
                if letter not in letters:
                    found_letter = letter
                    break
            else:
                raise ValueError("no unambiguous lettering found")

        letters[found_letter.lower()] = option
        index: int = option.index(found_letter)

        # Mark the option's shortcut letter for display.
        show_letter: str
        is_default: bool
        if not require and (
            (default is None and not numrange and first)
            or (
                isinstance(default, str)
                and found_letter.lower() == default.lower()
            )
        ):
            # The first option is the default; mark it.
            show_letter = f"[{found_letter.upper()}]"
            is_default = True
        else:
            show_letter = found_letter.upper()
            is_default = False

        # Colorize the letter shortcut.
        show_letter = colorize(
            "action_default" if is_default else "action", show_letter
        )

        # Insert the highlighted letter back into the word.
        descr_color: ColorName = (
            "action_default" if is_default else "action_description"
        )
        capitalized.append(
            colorize(descr_color, option[:index])
            + show_letter
            + colorize(descr_color, option[index + 1 :])
        )
        display_letters.append(found_letter.upper())

        first = False

    # The default is just the first option if unspecified.
    if require:
        default = None
    elif default is None:
        default = numrange[0] if numrange else display_letters[0].lower()

    # Make a prompt if one is not provided.
    if not prompt:
        prompt_parts: list[str] = []
        prompt_part_lengths: list[int] = []
        if numrange:
            if isinstance(default, int):
                default_name: str = str(default)
                default_name = colorize("action_default", default_name)
                tmpl: str = "# selection (default {})"
                prompt_parts.append(tmpl.format(default_name))
                prompt_part_lengths.append(len(tmpl) - 2 + len(str(default)))
            else:
                prompt_parts.append("# selection")
                prompt_part_lengths.append(len(prompt_parts[-1]))
        prompt_parts += capitalized
        prompt_part_lengths += [len(s) for s in options]

        # Wrap the query text.
        # Start prompt with U+279C: Heavy Round-Tipped Rightwards Arrow
        prompt = colorize("action", "\u279c ")
        line_length: int = 0
        i: int
        part: str
        length: int
        for i, (part, length) in enumerate(
            zip(prompt_parts, prompt_part_lengths)
        ):
            # Add punctuation.
            if i == len(prompt_parts) - 1:
                part += colorize("action_description", "?")
            else:
                part += colorize("action_description", ",")
            length += 1

            # Choose either the current line or the beginning of the next.
            if line_length + length + 1 > max_width:
                prompt += "\n"
                line_length = 0

            if line_length != 0:
                # Not the beginning of the line; need a space.
                part = f" {part}"
                length += 1

            prompt += part
            line_length += length

    # Make a fallback prompt too. This is displayed if the user enters
    # something that is not recognized.
    if not fallback_prompt:
        fallback_prompt = "Enter one of "
        if numrange:
            fallback_prompt += "{}-{}, ".format(*numrange)
        fallback_prompt += f"{', '.join(display_letters)}:"

    resp: int | str | None = input_(prompt)
    while True:
        if isinstance(resp, str):
            resp = resp.strip().lower()

        # Try default option.
        if default is not None and not resp:
            resp = default

        # Try an integer input if available.
        if numrange:
            try:
                resp = int(resp)  # type: ignore[arg-type]
            except ValueError:
                pass
            else:
                low: int
                high: int
                low, high = numrange
                if low <= resp <= high:
                    return resp
                else:
                    resp = None

        # Try a normal letter input.
        if isinstance(resp, str):
            resp = resp[0]
            if resp in letters:
                return resp

        # Prompt for new input.
        resp = input_(fallback_prompt)


def input_yn(prompt: str | None, require: bool = False) -> bool:
    """Prompts the user for a "yes" or "no" response. The default is
    "yes" unless `require` is `True`, in which case there is no default.
    """
    # Start prompt with U+279C: Heavy Round-Tipped Rightwards Arrow
    yesno: str = colorize("action", "\u279c ") + colorize(
        "action_description", "Enter Y or N:"
    )
    sel: int | str = input_options(("y", "n"), require, prompt, yesno)
    return sel == "y"


def input_select_objects(
    prompt: str | None,
    objs: list[T],
    rep: Callable[[T], None],
    prompt_all: str | None = None,
) -> list[T]:
    """Prompt to user to choose all, none, or some of the given objects.
    Return the list of selected objects.

    `prompt` is the prompt string to use for each question (it should be
    phrased as an imperative verb). If `prompt_all` is given, it is used
    instead of `prompt` for the first (yes(/no/select) question.
    `rep` is a function to call on each object to print it out when confirming
    objects individually.
    """
    choice: int | str = input_options(
        ("y", "n", "s"), False, f"{prompt_all or prompt}? (Yes/no/select)"
    )
    print()  # Blank line.

    if choice == "y":  # Yes.
        return objs

    elif choice == "s":  # Select.
        out: list[T] = []
        obj: T
        for obj in objs:
            rep(obj)
            answer: int | str = input_options(
                ("y", "n", "q"),
                True,
                f"{prompt}? (yes/no/quit)",
                "Enter Y or N:",
            )
            if answer == "y":
                out.append(obj)
            elif answer == "q":
                return out
        return out

    else:  # No.
        return []


def get_path_formats(
    subview: confuse.Subview | None = None,
) -> list[tuple[str, Template]]:
    """Get the configuration's path formats as a list of query/template
    pairs.
    """
    path_formats: list[tuple[str, Template]] = []
    subview = subview or config["paths"]
    query: str
    view: confuse.Subview
    for query, view in subview.items():
        query = PF_KEY_QUERIES.get(query, query)  # Expand common queries.
        path_formats.append((query, template(view.as_str())))
    return path_formats


def get_replacements() -> list[tuple[re.Pattern[str], str]]:
    """Confuse validation function that reads regex/string pairs."""
    replacements: list[tuple[re.Pattern[str], str]] = []
    pattern: str
    repl: str
    for pattern, repl in config["replace"].get(dict).items():
        repl = repl or ""
        try:
            replacements.append((re.compile(pattern), repl))
        except re.error:
            raise UserError(
                f"malformed regular expression in replace: {pattern}"
            )
    return replacements


def term_width() -> int:
    """Get the width (columns) of the terminal."""
    fallback: int = config["ui"]["terminal_width"].get(int)

    # The fcntl and termios modules are not available on non-Unix
    # platforms, so we fall back to a constant.
    try:
        import fcntl
        import termios
    except ImportError:
        return fallback

    width: int
    try:
        buf: bytes = fcntl.ioctl(0, termios.TIOCGWINSZ, b" " * 4)
    except OSError:
        return fallback
    try:
        _, width = struct.unpack("hh", buf)
    except struct.error:
        return fallback
    return width


def split_into_lines(string: str, width_tuple: tuple[int, int, int]):
    """Splits string into a list of substrings at whitespace.

    `width_tuple` is a 3-tuple of `(first_width, last_width, middle_width)`.
    The first substring has a length not longer than `first_width`, the last
    substring has a length not longer than `last_width`, and all other
    substrings have a length not longer than `middle_width`.
    `string` may contain ANSI codes at word borders.
    """
    first_width, middle_width, last_width = width_tuple
    words: list[str]

    if uncolorize(string) == string:
        # No colors in string
        words = string.split()
    else:
        # Use a regex to find escapes and the text within them.
        words = []
        m: re.Match[str]
        for m in ESC_TEXT_REGEX.finditer(string):
            # m contains four groups:
            # pretext - any text before escape sequence
            # esc - intitial escape sequence
            # text - text, no escape sequence, may contain spaces
            # reset - ASCII colour reset
            space_before_text: bool = False
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
            raw_words: list[str] = m.group("text").split()
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
                post_text: list[str] = m.group("posttext").split()
                words[-1] += post_text[0]
                words += post_text[1:]
            else:
                # Add any words after escape sequence
                words += m.group("posttext").split()
    result: list[str] = []
    next_substr: str = str("")
    # Iterate over all words.
    previous_fit: bool = False
    i: int
    for i in range(len(words)):  # pyrefly: ignore[bad-assignment]
        pot_substr: str = (  # (optimistically) add the next word to check the fit
            words[i] if i == 0 else " ".join([next_substr, words[i]])
        )
        # Find out if the pot(ential)_substr fits into the next substring.
        fits_first: bool = (
            len(result) == 0 and color_len(pot_substr) <= first_width
        )
        fits_middle: bool = (
            len(result) != 0 and color_len(pot_substr) <= middle_width
        )
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
    indent_str: str,
    left: ColumnLayout,
    right: ColumnLayout,
    separator: str = " -> ",
    max_width: int = term_width(),
) -> None:
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
    if not any((right["prefix"], right["contents"], right["suffix"])):
        # No right hand information, so we don't need a separator.
        separator = ""
    first_line_no_wrap: str = (
        f"{indent_str}{left['prefix']}{left['contents']}{left['suffix']}"
        f"{separator}{right['prefix']}{right['contents']}{right['suffix']}"
    )
    if color_len(first_line_no_wrap) < max_width:
        # Everything fits, print out line.
        print_(first_line_no_wrap)
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
        left_width_tuple: tuple[int, int, int] = (
            left["width"]
            - color_len(left["prefix"])
            - color_len(left["suffix"]),
            left["width"] - color_len(left["prefix"]),
            left["width"] - color_len(left["prefix"]),
        )

        left_split: list[str] = split_into_lines(
            left["contents"], left_width_tuple
        )
        right_width_tuple: tuple[int, int, int] = (
            right["width"]
            - color_len(right["prefix"])
            - color_len(right["suffix"]),
            right["width"] - color_len(right["prefix"]),
            right["width"] - color_len(right["prefix"]),
        )

        right_split: list[str] = split_into_lines(
            right["contents"], right_width_tuple
        )
        max_line_count: int = max(len(left_split), len(right_split))

        out: str = ""
        i: int
        for i in range(max_line_count):
            # indentation
            out += indent_str

            # Prefix or indent_str for line
            out += (
                left["prefix"] if i == 0 else indent(color_len(left["prefix"]))
            )

            # Line i of left hand side contents.
            left_part_len: int
            if i < len(left_split):
                out += left_split[i]
                left_part_len = color_len(left_split[i])
            else:
                left_part_len = 0

            # Padding until end of column.
            # Note: differs from original
            # column calcs in not -1 afterwards for space
            # in track number as that is included in 'prefix'
            padding: int = (
                left["width"] - color_len(left["prefix"]) - left_part_len
            )

            # Remove some padding on the first line to display
            # length
            if i == 0:
                padding -= color_len(left["suffix"])

            out += indent(padding)

            if i == 0:
                out += left["suffix"]

            # Separator between columns.
            out += separator if i == 0 else indent(color_len(separator))

            # Right prefix, contents, padding, suffix
            out += (
                right["prefix"]
                if i == 0
                else indent(color_len(right["prefix"]))
            )

            # Line i of right hand side.
            right_part_len: int
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
        print_(out)


def print_newline_layout(
    indent_str: str,
    left: ColumnLayout,
    right: ColumnLayout,
    separator: str = " -> ",
    max_width: int = term_width(),
) -> None:
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
    first_line_no_wrap: str = (
        f"{indent_str}{left['prefix']}{left['contents']}{left['suffix']}"
        f"{separator}{right['prefix']}{right['contents']}{right['suffix']}"
    )
    if color_len(first_line_no_wrap) < max_width:
        # Everything fits, print out line.
        print_(first_line_no_wrap)
    else:
        # Newline separation, with wrapping
        empty_space: int = max_width - len(indent_str)
        # On lower lines we will double the indent for clarity
        left_width_tuple: tuple[int, int, int] = (
            empty_space,
            empty_space - len(indent_str),
            empty_space - len(indent_str),
        )
        left_str: str = f"{left['prefix']}{left['contents']}{left['suffix']}"
        left_split: list[str] = split_into_lines(left_str, left_width_tuple)
        # Repeat calculations for rhs, including separator on first line
        right_width_tuple = (
            empty_space - color_len(separator),
            empty_space - len(indent_str),
            empty_space - len(indent_str),
        )
        right_str: str = (
            f"{right['prefix']}{right['contents']}{right['suffix']}"
        )
        right_split: list[str] = split_into_lines(right_str, right_width_tuple)
        i: int
        line: str
        for i, line in enumerate(left_split):
            if i == 0:
                print_(f"{indent_str}{line}")
            elif line != "":
                # Ignore empty lines
                print_(f"{indent_str * 2}{line}")
        for i, line in enumerate(right_split):
            if i == 0:
                print_(f"{indent_str}{separator}{line}")
            elif line != "":
                print_(f"{indent_str * 2}{line}")


FLOAT_EPSILON: Final = 0.01


def _field_diff(
    field: str,
    old: library.LibModel,
    old_fmt: db.FormattedMapping | None,
    new: library.LibModel,
    new_fmt: db.FormattedMapping,
) -> str | None:
    """Given two Model objects and their formatted views, format their values
    for `field` and highlight changes among them. Return a human-readable
    string. If the value has not changed, return None instead.
    """
    oldval = old.get(field)
    newval = new.get(field)

    # If no change, abort.
    if (
        isinstance(oldval, float)
        and isinstance(newval, float)
        and abs(oldval - newval) < FLOAT_EPSILON
    ):
        return None
    elif oldval == newval:
        return None

    # Get formatted values for output.
    oldstr: str = old_fmt.get(field, "") if old_fmt else ""
    newstr: str = new_fmt.get(field, "")

    # For strings, highlight changes. For others, colorize the whole
    # thing.
    if isinstance(oldval, str):
        oldstr, newstr = colordiff(oldval, newstr)
    else:
        oldstr = colorize("text_diff_removed", oldstr)
        newstr = colorize("text_diff_added", newstr)

    return f"{oldstr} -> {newstr}"


def show_model_changes(
    new: library.LibModel,
    old: library.LibModel | None = None,
    fields: Iterable[str] | None = None,
    always: bool = False,
    print_obj: bool = True,
) -> bool:
    """Given a Model object, print a list of changes from its pristine
    version stored in the database. Return a boolean indicating whether
    any changes were found.

    `old` may be the "original" object to avoid using the pristine
    version from the database. `fields` may be a list of fields to
    restrict the detection to. `always` indicates whether the object is
    always identified, regardless of whether any changes are present.
    """
    if not old and new._db:
        old = new._db._get(type(new), new.id)

    # Keep the formatted views around instead of re-creating them in each
    # iteration step
    old_fmt: db.FormattedMapping | None = old.formatted() if old else None
    new_fmt: db.FormattedMapping = new.formatted()

    # Build up lines showing changed fields
    field: str
    changes: list[str] = []
    if old:
        for field in old:
            # Subset of the fields. Never show mtime.
            if field == "mtime" or (fields and field not in fields):
                continue

            # Detect and show difference for this field.
            line: str | None = _field_diff(field, old, old_fmt, new, new_fmt)
            if line:
                changes.append(f"  {field}: {line}")

    # New fields.
    for field in set(new) - set(old or ()):
        if fields and field not in fields:
            continue

        changes.append(
            f"  {field}: {colorize('text_highlight', new_fmt[field])}"
        )

    # Print changes.
    if print_obj and (changes or always):
        print_(format(old))
    if changes:
        print_("\n".join(changes))

    return bool(changes)


def show_path_changes(
    path_changes: Iterable[tuple[util.PathLike, util.PathLike]],
) -> None:
    """Given a list of tuples (source, destination) that indicate the
    path changes, log the changes as INFO-level output to the beets log.
    The output is guaranteed to be unicode.

    Every pair is shown on a single line if the terminal width permits it,
    else it is split over two lines. E.g.,

    Source -> Destination

    vs.

    Source
        -> Destination
    """
    sources: Iterable[bytes | str]
    destinations: Iterable[bytes | str]
    sources, destinations = zip(*path_changes)

    # Ensure unicode output
    sources = list(map(util.displayable_path, sources))
    destinations = list(map(util.displayable_path, destinations))

    # Calculate widths for terminal split
    col_width: int = (term_width() - len(" -> ")) // 2
    max_width: int = len(max([sources + destinations], key=len))

    source: bytes | str
    dest: bytes | str
    if max_width > col_width:
        # Print every change over two lines
        for source, dest in zip(sources, destinations):
            color_source: str
            color_dest: str
            color_source, color_dest = colordiff(source, dest)
            print_(f"{color_source} \n  -> {color_dest}")
    else:
        # Print every change on a single line, and add a header
        title_pad: int = max_width - len("Source ") + len(" -> ")

        print_(f"Source {' ' * title_pad} Destination")
        for source, dest in zip(sources, destinations):
            pad: int = max_width - len(source)
            color_source, color_dest = colordiff(source, dest)
            print_(f"{color_source} {' ' * pad} -> {color_dest}")


# Helper functions for option parsing.


def _store_dict(
    option: optparse.Option,
    opt_str: str,
    value: str,
    parser: optparse.OptionParser,
) -> None:
    """Custom action callback to parse options which have ``key=value``
    pairs as values. All such pairs passed for this option are
    aggregated into a dictionary.
    """
    dest: str = option.dest or ""
    option_values: dict[str, str] | None = getattr(parser.values, dest, None)

    if option_values is None:
        # This is the first supplied ``key=value`` pair of option.
        # Initialize empty dictionary and get a reference to it.
        setattr(parser.values, dest, {})
        option_values = getattr(parser.values, dest)

    try:
        key: str
        key, value = value.split("=", 1)
        if not (key and value):
            raise ValueError
    except ValueError:
        raise UserError(
            f"supplied argument `{value}' is not of the form `key=value'"
        )

    option_values[key] = value


optparse.Option.ALWAYS_TYPED_ACTIONS += ("callback",)


class CommonOptionsParser(optparse.OptionParser):
    """Offers a simple way to add common formatting options.

    Options available include:
        - matching albums instead of tracks: add_album_option()
        - showing paths instead of items/albums: add_path_option()
        - changing the format of displayed items/albums: add_format_option()

    The last one can have several behaviors:
        - against a special target
        - with a certain format
        - autodetected target with the album option

    Each method is fully documented in the related method.
    """

    def __init__(
        self,
        **kwargs: Unpack[OptionParserParams],
    ) -> None:
        super().__init__(**kwargs)
        self._album_flags: set[str] | None = None
        # this serves both as an indicator that we offer the feature AND allows
        # us to check whether it has been specified on the CLI - bypassing the
        # fact that arguments may be in any order

    def add_album_option(
        self, flags: tuple[str, str] = ("-a", "--album")
    ) -> None:
        """Add a -a/--album option to match albums instead of tracks.

        If used then the format option can auto-detect whether we're setting
        the format for items or albums.
        Sets the album property on the options extracted from the CLI.
        """
        album: optparse.Option = optparse.Option(
            *flags, action="store_true", help="match albums instead of tracks"
        )
        self.add_option(album)
        self._album_flags = set(flags)

    def _set_format(
        self,
        option: optparse.Option,
        opt_str: str,
        value: str,
        parser: CommonOptionsParser,
        target: type[library.Album | library.Item] | None = None,
        fmt: str | None = None,
        store_true: bool = False,
    ) -> None:
        """Internal callback that sets the correct format while parsing CLI
        arguments.
        """
        if store_true and option.dest:
            setattr(parser.values, option.dest, True)

        # Use the explicitly specified format, or the string from the option.
        value = fmt or value or ""
        if parser.values is None:
            parser.values = optparse.Values()
        parser.values.format = value

        if target:
            config[target._format_config_key].set(value)
            return

        if self._album_flags:
            if parser.values.album:
                target = library.Album
            else:
                # the option is either missing either not parsed yet
                if self._album_flags & set(parser.rargs or ()):
                    target = library.Album
                else:
                    target = library.Item
            config[target._format_config_key].set(value)
        else:
            config[library.Item._format_config_key].set(value)
            config[library.Album._format_config_key].set(value)

    def add_path_option(
        self, flags: tuple[str, str] = ("-p", "--path")
    ) -> None:
        """Add a -p/--path option to display the path instead of the default
        format.

        By default this affects both items and albums. If add_album_option()
        is used then the target will be autodetected.

        Sets the format property to '$path' on the options extracted from the
        CLI.
        """
        path: optparse.Option = optparse.Option(
            *flags,
            nargs=0,
            action="callback",
            callback=self._set_format,
            callback_kwargs={"fmt": "$path", "store_true": True},
            help="print paths for matched items or albums",
        )
        self.add_option(path)

    def add_format_option(
        self,
        flags: tuple[str, ...] = ("-f", "--format"),
        target: str | type[library.LibModel] | None = None,
    ) -> None:
        """Add -f/--format option to print some LibModel instances with a
        custom format.

        `target` is optional and can be one of ``library.Item``, 'item',
        ``library.Album`` and 'album'.

        Several behaviors are available:
            - if `target` is given then the format is only applied to that
            LibModel
            - if the album option is used then the target will be autodetected
            - otherwise the format is applied to both items and albums.

        Sets the format property on the options extracted from the CLI.
        """
        kwargs: dict[str, type[library.LibModel]] = {}
        if target:
            if isinstance(target, str):
                target = {"item": library.Item, "album": library.Album}[target]
            kwargs["target"] = target

        opt: optparse.Option = optparse.Option(
            *flags,
            action="callback",
            callback=self._set_format,
            callback_kwargs=kwargs,
            help="print with custom format",
        )
        self.add_option(opt)
        return None

    def add_all_common_options(self) -> None:
        """Add album, path and format options."""
        self.add_album_option()
        self.add_path_option()
        self.add_format_option()


# Subcommand parsing infrastructure.
#
# This is a fairly generic subcommand parser for optparse. It is
# maintained externally here:
# https://gist.github.com/462717
# There you will also find a better description of the code and a more
# succinct example program.


class Subcommand:
    """A subcommand of a root command-line application that may be
    invoked by a SubcommandOptionParser.
    """

    def __init__(
        self,
        name: str,
        func: (
            Callable[
                [library.Library, optparse.Values, list[str] | tuple[str]],
                Any,
            ]
        )
        | None = None,
        parser: CommonOptionsParser | None = None,
        help: str = "",
        aliases: tuple[str, ...] = (),
        hide: bool = False,
    ) -> None:
        """Creates a new subcommand. name is the primary way to invoke
        the subcommand; aliases are alternate names. parser is an
        OptionParser responsible for parsing the subcommand's options.
        help is a short description of the command. If no parser is
        given, it defaults to a new, empty CommonOptionsParser.
        """
        self.name: str = name
        self.func: Callable[
            [library.Library, optparse.Values, list[str] | tuple[str]], Any
        ]
        if func:
            self.func = func

        self.parser: CommonOptionsParser = parser or CommonOptionsParser()
        self.aliases: tuple[str, ...] = aliases
        self.help: str = help
        self.hide: bool = hide
        self._root_parser: optparse.OptionParser | None = None

    def print_help(self) -> None:
        self.parser.print_help()

    def parse_args(self, args: list[str]) -> tuple[optparse.Values, list[str]]:
        return self.parser.parse_args(args)

    @property
    def root_parser(self) -> optparse.OptionParser | None:
        return self._root_parser

    @root_parser.setter
    def root_parser(self, root_parser: optparse.OptionParser) -> None:
        self._root_parser = root_parser
        self.parser.prog = (
            f"{as_string(root_parser.get_prog_name())} {self.name}"
        )


class SubcommandsOptionParser(CommonOptionsParser):
    """A variant of OptionParser that parses subcommands and their
    arguments.
    """

    def __init__(self, **kwargs: Unpack[OptionParserParams]) -> None:
        """Create a new subcommand-aware option parser. All of the
        options to OptionParser.__init__ are supported in addition
        to subcommands, a sequence of Subcommand objects.
        """
        # A more helpful default usage.
        if "usage" not in kwargs:
            kwargs["usage"] = """
    %prog COMMAND [ARGS...]
    %prog help COMMAND"""
        kwargs["add_help_option"] = False

        # Super constructor.
        super().__init__(**kwargs)

        # Our root parser needs to stop on the first unrecognized argument.
        self.disable_interspersed_args()

        self.subcommands: list[Subcommand] = []

    def add_subcommand(self, *cmds: Subcommand) -> None:
        """Adds a Subcommand object to the parser's list of commands."""
        for cmd in cmds:
            cmd.root_parser = self
            self.subcommands.append(cmd)

    # Add the list of subcommands to the help message.
    @override
    def format_help(
        self, formatter: optparse.HelpFormatter | None = None
    ) -> str:
        # Get the original help message, to which we will append.
        out: str = super().format_help(formatter)
        if formatter is None:
            formatter = self.formatter

        # Subcommands header.
        result: list[str] = ["\n" + formatter.format_heading("Commands")]
        formatter.indent()

        # Generate the display names (including aliases).
        # Also determine the help position.
        disp_names: list[str] = []
        help_position: int = 0
        subcommands: list[Subcommand] = [
            c for c in self.subcommands if not c.hide
        ]
        subcommands.sort(key=lambda c: c.name)
        name: str
        subcommand: Subcommand
        for subcommand in subcommands:
            name = subcommand.name
            if subcommand.aliases:
                name += f" ({', '.join(subcommand.aliases)})"
            disp_names.append(name)

            # Set the help position based on the max width.
            proposed_help_position: int = (
                len(name) + formatter.current_indent + 2
            )
            if proposed_help_position <= formatter.max_help_position:
                help_position = max(help_position, proposed_help_position)

        # Add each subcommand to the output.
        for subcommand, name in zip(subcommands, disp_names):
            # Lifted directly from optparse.py.
            name_width: int = help_position - formatter.current_indent - 2
            indent_first: int
            if len(name) > name_width:
                name = f"{' ' * formatter.current_indent}{name}\n"
                indent_first = help_position
            else:
                name = f"{' ' * formatter.current_indent}{name:<{name_width}}\n"
                indent_first = 0
            result.append(name)
            help_width: int = formatter.width - help_position
            help_lines: list[str] = textwrap.wrap(subcommand.help, help_width)
            help_line: str = help_lines[0] if help_lines else ""
            result.append(f"{' ' * indent_first}{help_line}\n")
            result.extend(
                [f"{' ' * help_position}{line}\n" for line in help_lines[1:]]
            )
        formatter.dedent()

        # Concatenate the original help message with the subcommand
        # list.
        return f"{out}{''.join(result)}"

    def _subcommand_for_name(self, name: str) -> Subcommand | None:
        """Return the subcommand in self.subcommands matching the
        given name. The name may either be the name of a subcommand or
        an alias. If no subcommand matches, returns None.
        """
        return next(
            (
                subcommand
                for subcommand in self.subcommands
                if name == subcommand.name or name in subcommand.aliases
            ),
            None,
        )

    def parse_global_options(self, args: list[str]):
        """Parse options up to the subcommand argument. Returns a tuple
        of the options object and the remaining arguments.
        """
        options: optparse.Values
        subargs: list[str]
        options, subargs = self.parse_args(args)

        # Force the help command
        if options.help:
            subargs = ["help"]
        elif options.version:
            subargs = ["version"]
        return options, subargs

    def parse_subcommand(self, args: list[str]):
        """Given the `args` left unused by a `parse_global_options`,
        return the invoked subcommand, the subcommand options, and the
        subcommand arguments.
        """
        # Help is default command
        if not args:
            args = ["help"]

        cmdname: str = args.pop(0)
        subcommand: Subcommand | None = self._subcommand_for_name(cmdname)
        if not subcommand:
            raise UserError(f"unknown command '{cmdname}'")

        suboptions: optparse.Values
        subargs: list[str]
        suboptions, subargs = subcommand.parse_args(args)
        return subcommand, suboptions, subargs
