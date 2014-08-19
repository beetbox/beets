# This file is part of beets.
# Copyright 2014, Adrian Sampson.
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

"""This module contains all of the core logic for beets' command-line
interface. To invoke the CLI, just call beets.ui.main(). The actual
CLI commands are implemented in the ui.commands module.
"""
from __future__ import print_function

import locale
import optparse
import textwrap
import sys
from difflib import SequenceMatcher
import logging
import sqlite3
import errno
import re
import struct
import traceback
import os.path

from beets import library
from beets import plugins
from beets import util
from beets.util.functemplate import Template
from beets import config
from beets.util import confit
from beets.autotag import mb

# On Windows platforms, use colorama to support "ANSI" terminal colors.
if sys.platform == 'win32':
    try:
        import colorama
    except ImportError:
        pass
    else:
        colorama.init()


log = logging.getLogger('beets')
if not log.handlers:
    log.addHandler(logging.StreamHandler())
log.propagate = False  # Don't propagate to root handler.


PF_KEY_QUERIES = {
    'comp': 'comp:true',
    'singleton': 'singleton:true',
}


class UserError(Exception):
    """UI exception. Commands should throw this in order to display
    nonrecoverable errors to the user.
    """


# Utilities.

def _encoding():
    """Tries to guess the encoding used by the terminal."""
    # Configured override?
    encoding = config['terminal_encoding'].get()
    if encoding:
        return encoding

    # Determine from locale settings.
    try:
        return locale.getdefaultlocale()[1] or 'utf8'
    except ValueError:
        # Invalid locale environment variable setting. To avoid
        # failing entirely for no good reason, assume UTF-8.
        return 'utf8'


def decargs(arglist):
    """Given a list of command-line argument bytestrings, attempts to
    decode them to Unicode strings.
    """
    return [s.decode(_encoding()) for s in arglist]


def print_(*strings):
    """Like print, but rather than raising an error when a character
    is not in the terminal's encoding's character set, just silently
    replaces it.
    """
    if strings:
        if isinstance(strings[0], unicode):
            txt = u' '.join(strings)
        else:
            txt = ' '.join(strings)
    else:
        txt = u''
    if isinstance(txt, unicode):
        txt = txt.encode(_encoding(), 'replace')
    print(txt)


def input_(prompt=None):
    """Like `raw_input`, but decodes the result to a Unicode string.
    Raises a UserError if stdin is not available. The prompt is sent to
    stdout rather than stderr. A printed between the prompt and the
    input cursor.
    """
    # raw_input incorrectly sends prompts to stderr, not stdout, so we
    # use print() explicitly to display prompts.
    # http://bugs.python.org/issue1927
    if prompt:
        if isinstance(prompt, unicode):
            prompt = prompt.encode(_encoding(), 'replace')
        print(prompt, end=' ')

    try:
        resp = raw_input()
    except EOFError:
        raise UserError('stdin stream ended while input required')

    return resp.decode(sys.stdin.encoding or 'utf8', 'ignore')


def input_options(options, require=False, prompt=None, fallback_prompt=None,
                  numrange=None, default=None, max_width=72):
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
    letters = {}
    display_letters = []
    capitalized = []
    first = True
    for option in options:
        # Is a letter already capitalized?
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
                raise ValueError('no unambiguous lettering found')

        letters[found_letter.lower()] = option
        index = option.index(found_letter)

        # Mark the option's shortcut letter for display.
        if not require and (
            (default is None and not numrange and first) or
            (isinstance(default, basestring) and
             found_letter.lower() == default.lower())):
            # The first option is the default; mark it.
            show_letter = '[%s]' % found_letter.upper()
            is_default = True
        else:
            show_letter = found_letter.upper()
            is_default = False

        # Colorize the letter shortcut.
        show_letter = colorize('turquoise' if is_default else 'blue',
                               show_letter)

        # Insert the highlighted letter back into the word.
        capitalized.append(
            option[:index] + show_letter + option[index + 1:]
        )
        display_letters.append(found_letter.upper())

        first = False

    # The default is just the first option if unspecified.
    if require:
        default = None
    elif default is None:
        if numrange:
            default = numrange[0]
        else:
            default = display_letters[0].lower()

    # Make a prompt if one is not provided.
    if not prompt:
        prompt_parts = []
        prompt_part_lengths = []
        if numrange:
            if isinstance(default, int):
                default_name = str(default)
                default_name = colorize('turquoise', default_name)
                tmpl = '# selection (default %s)'
                prompt_parts.append(tmpl % default_name)
                prompt_part_lengths.append(len(tmpl % str(default)))
            else:
                prompt_parts.append('# selection')
                prompt_part_lengths.append(len(prompt_parts[-1]))
        prompt_parts += capitalized
        prompt_part_lengths += [len(s) for s in options]

        # Wrap the query text.
        prompt = ''
        line_length = 0
        for i, (part, length) in enumerate(zip(prompt_parts,
                                               prompt_part_lengths)):
            # Add punctuation.
            if i == len(prompt_parts) - 1:
                part += '?'
            else:
                part += ','
            length += 1

            # Choose either the current line or the beginning of the next.
            if line_length + length + 1 > max_width:
                prompt += '\n'
                line_length = 0

            if line_length != 0:
                # Not the beginning of the line; need a space.
                part = ' ' + part
                length += 1

            prompt += part
            line_length += length

    # Make a fallback prompt too. This is displayed if the user enters
    # something that is not recognized.
    if not fallback_prompt:
        fallback_prompt = 'Enter one of '
        if numrange:
            fallback_prompt += '%i-%i, ' % numrange
        fallback_prompt += ', '.join(display_letters) + ':'

    resp = input_(prompt)
    while True:
        resp = resp.strip().lower()

        # Try default option.
        if default is not None and not resp:
            resp = default

        # Try an integer input if available.
        if numrange:
            try:
                resp = int(resp)
            except ValueError:
                pass
            else:
                low, high = numrange
                if low <= resp <= high:
                    return resp
                else:
                    resp = None

        # Try a normal letter input.
        if resp:
            resp = resp[0]
            if resp in letters:
                return resp

        # Prompt for new input.
        resp = input_(fallback_prompt)


def input_yn(prompt, require=False):
    """Prompts the user for a "yes" or "no" response. The default is
    "yes" unless `require` is `True`, in which case there is no default.
    """
    sel = input_options(
        ('y', 'n'), require, prompt, 'Enter Y or N:'
    )
    return sel == 'y'


def human_bytes(size):
    """Formats size, a number of bytes, in a human-readable way."""
    suffices = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB', 'HB']
    for suffix in suffices:
        if size < 1024:
            return "%3.1f %s" % (size, suffix)
        size /= 1024.0
    return "big"


def human_seconds(interval):
    """Formats interval, a number of seconds, as a human-readable time
    interval using English words.
    """
    units = [
        (1, 'second'),
        (60, 'minute'),
        (60, 'hour'),
        (24, 'day'),
        (7, 'week'),
        (52, 'year'),
        (10, 'decade'),
    ]
    for i in range(len(units) - 1):
        increment, suffix = units[i]
        next_increment, _ = units[i + 1]
        interval /= float(increment)
        if interval < next_increment:
            break
    else:
        # Last unit.
        increment, suffix = units[-1]
        interval /= float(increment)

    return "%3.1f %ss" % (interval, suffix)


def human_seconds_short(interval):
    """Formats a number of seconds as a short human-readable M:SS
    string.
    """
    interval = int(interval)
    return u'%i:%02i' % (interval // 60, interval % 60)


# ANSI terminal colorization code heavily inspired by pygments:
# http://dev.pocoo.org/hg/pygments-main/file/b2deea5b5030/pygments/console.py
# (pygments is by Tim Hatch, Armin Ronacher, et al.)
COLOR_ESCAPE = "\x1b["
DARK_COLORS = ["black", "darkred", "darkgreen", "brown", "darkblue",
               "purple", "teal", "lightgray"]
LIGHT_COLORS = ["darkgray", "red", "green", "yellow", "blue",
                "fuchsia", "turquoise", "white"]
RESET_COLOR = COLOR_ESCAPE + "39;49;00m"


def _colorize(color, text):
    """Returns a string that prints the given text in the given color
    in a terminal that is ANSI color-aware. The color must be something
    in DARK_COLORS or LIGHT_COLORS.
    """
    if color in DARK_COLORS:
        escape = COLOR_ESCAPE + "%im" % (DARK_COLORS.index(color) + 30)
    elif color in LIGHT_COLORS:
        escape = COLOR_ESCAPE + "%i;01m" % (LIGHT_COLORS.index(color) + 30)
    else:
        raise ValueError('no such color %s', color)
    return escape + text + RESET_COLOR


def colorize(color, text):
    """Colorize text if colored output is enabled. (Like _colorize but
    conditional.)
    """
    if config['color']:
        return _colorize(color, text)
    else:
        return text


def _colordiff(a, b, highlight='red', minor_highlight='lightgray'):
    """Given two values, return the same pair of strings except with
    their differences highlighted in the specified color. Strings are
    highlighted intelligently to show differences; other values are
    stringified and highlighted in their entirety.
    """
    if not isinstance(a, basestring) or not isinstance(b, basestring):
        # Non-strings: use ordinary equality.
        a = unicode(a)
        b = unicode(b)
        if a == b:
            return a, b
        else:
            return colorize(highlight, a), colorize(highlight, b)

    if isinstance(a, bytes) or isinstance(b, bytes):
        # A path field.
        a = util.displayable_path(a)
        b = util.displayable_path(b)

    a_out = []
    b_out = []

    matcher = SequenceMatcher(lambda x: False, a, b)
    for op, a_start, a_end, b_start, b_end in matcher.get_opcodes():
        if op == 'equal':
            # In both strings.
            a_out.append(a[a_start:a_end])
            b_out.append(b[b_start:b_end])
        elif op == 'insert':
            # Right only.
            b_out.append(colorize(highlight, b[b_start:b_end]))
        elif op == 'delete':
            # Left only.
            a_out.append(colorize(highlight, a[a_start:a_end]))
        elif op == 'replace':
            # Right and left differ. Colorise with second highlight if
            # it's just a case change.
            if a[a_start:a_end].lower() != b[b_start:b_end].lower():
                color = highlight
            else:
                color = minor_highlight
            a_out.append(colorize(color, a[a_start:a_end]))
            b_out.append(colorize(color, b[b_start:b_end]))
        else:
            assert(False)

    return u''.join(a_out), u''.join(b_out)


def colordiff(a, b, highlight='red'):
    """Colorize differences between two values if color is enabled.
    (Like _colordiff but conditional.)
    """
    if config['color']:
        return _colordiff(a, b, highlight)
    else:
        return unicode(a), unicode(b)


def color_diff_suffix(a, b, highlight='red'):
    """Colorize the differing suffix between two strings."""
    a, b = unicode(a), unicode(b)
    if not config['color']:
        return a, b

    # Fast path.
    if a == b:
        return a, b

    # Find the longest common prefix.
    first_diff = None
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            first_diff = i
            break
    else:
        first_diff = min(len(a), len(b))

    # Colorize from the first difference on.
    return (a[:first_diff] + colorize(highlight, a[first_diff:]),
            b[:first_diff] + colorize(highlight, b[first_diff:]))


def get_path_formats(subview=None):
    """Get the configuration's path formats as a list of query/template
    pairs.
    """
    path_formats = []
    subview = subview or config['paths']
    for query, view in subview.items():
        query = PF_KEY_QUERIES.get(query, query)  # Expand common queries.
        path_formats.append((query, Template(view.get(unicode))))
    return path_formats


def get_replacements():
    """Confit validation function that reads regex/string pairs.
    """
    replacements = []
    for pattern, repl in config['replace'].get(dict).items():
        repl = repl or ''
        try:
            replacements.append((re.compile(pattern), repl))
        except re.error:
            raise UserError(
                u'malformed regular expression in replace: {0}'.format(
                    pattern
                )
            )
    return replacements


def get_plugin_paths():
    """Get the list of search paths for plugins from the config file.
    The value for "pluginpath" may be a single string or a list of
    strings.
    """
    pluginpaths = config['pluginpath'].get()
    if isinstance(pluginpaths, basestring):
        pluginpaths = [pluginpaths]
    if not isinstance(pluginpaths, list):
        raise confit.ConfigTypeError(
            u'pluginpath must be string or a list of strings'
        )
    return map(util.normpath, pluginpaths)


def _pick_format(album, fmt=None):
    """Pick a format string for printing Album or Item objects,
    falling back to config options and defaults.
    """
    if fmt:
        return fmt
    if album:
        return config['list_format_album'].get(unicode)
    else:
        return config['list_format_item'].get(unicode)


def print_obj(obj, lib, fmt=None):
    """Print an Album or Item object. If `fmt` is specified, use that
    format string. Otherwise, use the configured template.
    """
    album = isinstance(obj, library.Album)
    fmt = _pick_format(album, fmt)
    if isinstance(fmt, Template):
        template = fmt
    else:
        template = Template(fmt)
    print_(obj.evaluate_template(template))


def term_width():
    """Get the width (columns) of the terminal."""
    fallback = config['ui']['terminal_width'].get(int)

    # The fcntl and termios modules are not available on non-Unix
    # platforms, so we fall back to a constant.
    try:
        import fcntl
        import termios
    except ImportError:
        return fallback

    try:
        buf = fcntl.ioctl(0, termios.TIOCGWINSZ, ' ' * 4)
    except IOError:
        return fallback
    try:
        height, width = struct.unpack('hh', buf)
    except struct.error:
        return fallback
    return width


FLOAT_EPSILON = 0.01


def _field_diff(field, old, new):
    """Given two Model objects, format their values for `field` and
    highlight changes among them. Return a human-readable string. If the
    value has not changed, return None instead.
    """
    oldval = old.get(field)
    newval = new.get(field)

    # If no change, abort.
    if isinstance(oldval, float) and isinstance(newval, float) and \
            abs(oldval - newval) < FLOAT_EPSILON:
        return None
    elif oldval == newval:
        return None

    # Get formatted values for output.
    oldstr = old.formatted.get(field, u'')
    newstr = new.formatted.get(field, u'')

    # For strings, highlight changes. For others, colorize the whole
    # thing.
    if isinstance(oldval, basestring):
        oldstr, newstr = colordiff(oldval, newstr)
    else:
        oldstr, newstr = colorize('red', oldstr), colorize('red', newstr)

    return u'{0} -> {1}'.format(oldstr, newstr)


def show_model_changes(new, old=None, fields=None, always=False):
    """Given a Model object, print a list of changes from its pristine
    version stored in the database. Return a boolean indicating whether
    any changes were found.

    `old` may be the "original" object to avoid using the pristine
    version from the database. `fields` may be a list of fields to
    restrict the detection to. `always` indicates whether the object is
    always identified, regardless of whether any changes are present.
    """
    old = old or new._db._get(type(new), new.id)

    # Build up lines showing changed fields.
    changes = []
    for field in old:
        # Subset of the fields. Never show mtime.
        if field == 'mtime' or (fields and field not in fields):
            continue

        # Detect and show difference for this field.
        line = _field_diff(field, old, new)
        if line:
            changes.append(u'  {0}: {1}'.format(field, line))

    # New fields.
    for field in set(new) - set(old):
        if fields and field not in fields:
            continue

        changes.append(u'  {0}: {1}'.format(
            field,
            colorize('red', new.formatted[field])
        ))

    # Print changes.
    if changes or always:
        print_obj(old, old._db)
    if changes:
        print_(u'\n'.join(changes))

    return bool(changes)


# Subcommand parsing infrastructure.
#
# This is a fairly generic subcommand parser for optparse. It is
# maintained externally here:
# http://gist.github.com/462717
# There you will also find a better description of the code and a more
# succinct example program.

class Subcommand(object):
    """A subcommand of a root command-line application that may be
    invoked by a SubcommandOptionParser.
    """
    def __init__(self, name, parser=None, help='', aliases=(), hide=False):
        """Creates a new subcommand. name is the primary way to invoke
        the subcommand; aliases are alternate names. parser is an
        OptionParser responsible for parsing the subcommand's options.
        help is a short description of the command. If no parser is
        given, it defaults to a new, empty OptionParser.
        """
        self.name = name
        self.parser = parser or optparse.OptionParser()
        self.aliases = aliases
        self.help = help
        self.hide = hide
        self._root_parser = None

    def print_help(self):
        self.parser.print_help()

    def parse_args(self, args):
        return self.parser.parse_args(args)

    @property
    def root_parser(self):
        return self._root_parser

    @root_parser.setter
    def root_parser(self, root_parser):
        self._root_parser = root_parser
        self.parser.prog = '{0} {1}'.format(root_parser.get_prog_name(),
                                            self.name)


class SubcommandsOptionParser(optparse.OptionParser):
    """A variant of OptionParser that parses subcommands and their
    arguments.
    """

    def __init__(self, *args, **kwargs):
        """Create a new subcommand-aware option parser. All of the
        options to OptionParser.__init__ are supported in addition
        to subcommands, a sequence of Subcommand objects.
        """
        # A more helpful default usage.
        if 'usage' not in kwargs:
            kwargs['usage'] = """
  %prog COMMAND [ARGS...]
  %prog help COMMAND"""
        kwargs['add_help_option'] = False

        # Super constructor.
        optparse.OptionParser.__init__(self, *args, **kwargs)

        # Our root parser needs to stop on the first unrecognized argument.
        self.disable_interspersed_args()

        self.subcommands = []

    def add_subcommand(self, *cmds):
        """Adds a Subcommand object to the parser's list of commands.
        """
        for cmd in cmds:
            cmd.root_parser = self
            self.subcommands.append(cmd)

    # Add the list of subcommands to the help message.
    def format_help(self, formatter=None):
        # Get the original help message, to which we will append.
        out = optparse.OptionParser.format_help(self, formatter)
        if formatter is None:
            formatter = self.formatter

        # Subcommands header.
        result = ["\n"]
        result.append(formatter.format_heading('Commands'))
        formatter.indent()

        # Generate the display names (including aliases).
        # Also determine the help position.
        disp_names = []
        help_position = 0
        subcommands = [c for c in self.subcommands if not c.hide]
        subcommands.sort(key=lambda c: c.name)
        for subcommand in subcommands:
            name = subcommand.name
            if subcommand.aliases:
                name += ' (%s)' % ', '.join(subcommand.aliases)
            disp_names.append(name)

            # Set the help position based on the max width.
            proposed_help_position = len(name) + formatter.current_indent + 2
            if proposed_help_position <= formatter.max_help_position:
                help_position = max(help_position, proposed_help_position)

        # Add each subcommand to the output.
        for subcommand, name in zip(subcommands, disp_names):
            # Lifted directly from optparse.py.
            name_width = help_position - formatter.current_indent - 2
            if len(name) > name_width:
                name = "%*s%s\n" % (formatter.current_indent, "", name)
                indent_first = help_position
            else:
                name = "%*s%-*s  " % (formatter.current_indent, "",
                                      name_width, name)
                indent_first = 0
            result.append(name)
            help_width = formatter.width - help_position
            help_lines = textwrap.wrap(subcommand.help, help_width)
            result.append("%*s%s\n" % (indent_first, "", help_lines[0]))
            result.extend(["%*s%s\n" % (help_position, "", line)
                           for line in help_lines[1:]])
        formatter.dedent()

        # Concatenate the original help message with the subcommand
        # list.
        return out + "".join(result)

    def _subcommand_for_name(self, name):
        """Return the subcommand in self.subcommands matching the
        given name. The name may either be the name of a subcommand or
        an alias. If no subcommand matches, returns None.
        """
        for subcommand in self.subcommands:
            if name == subcommand.name or \
               name in subcommand.aliases:
                return subcommand
        return None

    def parse_global_options(self, args):
        """Parse options up to the subcommand argument. Returns a tuple
        of the options object and the remaining arguments.
        """
        options, subargs = self.parse_args(args)

        # Force the help command
        if options.help:
            subargs = ['help']
        return options, subargs

    def parse_subcommand(self, args):
        """Given the `args` left unused by a `parse_global_options`,
        return the invoked subcommand, the subcommand options, and the
        subcommand arguments.
        """
        # Help is default command
        if not args:
            args = ['help']

        cmdname = args.pop(0)
        subcommand = self._subcommand_for_name(cmdname)
        if not subcommand:
            raise UserError("unknown command '{0}'".format(cmdname))

        suboptions, subargs = subcommand.parse_args(args)
        return subcommand, suboptions, subargs


optparse.Option.ALWAYS_TYPED_ACTIONS += ('callback',)


def vararg_callback(option, opt_str, value, parser):
    """Callback for an option with variable arguments.
    Manually collect arguments right of a callback-action
    option (ie. with action="callback"), and add the resulting
    list to the destination var.

    Usage:
    parser.add_option("-c", "--callback", dest="vararg_attr",
                      action="callback", callback=vararg_callback)

    Details:
    http://docs.python.org/2/library/optparse.html#callback-example-6-variable
    -arguments
    """
    value = [value]

    def floatable(str):
        try:
            float(str)
            return True
        except ValueError:
            return False

    for arg in parser.rargs:
        # stop on --foo like options
        if arg[:2] == "--" and len(arg) > 2:
            break
        # stop on -a, but not on -3 or -3.0
        if arg[:1] == "-" and len(arg) > 1 and not floatable(arg):
            break
        value.append(arg)

    del parser.rargs[:len(value) - 1]
    setattr(parser.values, option.dest, value)


# The main entry point and bootstrapping.

def _load_plugins():
    """Load the plugins specified in the configuration.
    """
    # Add plugin paths.
    import beetsplug
    beetsplug.__path__ = get_plugin_paths() + beetsplug.__path__

    # For backwards compatibility.
    sys.path += get_plugin_paths()

    # Load requested plugins.
    plugins.load_plugins(config['plugins'].as_str_seq())
    plugins.send("pluginload")


def _configure(args):
    """Parse the command line, load configuration files (including
    loading any indicated plugins), and return the invoked subcomand,
    the subcommand options, and the subcommand arguments.
    """
    # Temporary: Migrate from 1.0-style configuration.
    from beets.ui import migrate
    migrate.automigrate()

    # Get the default subcommands.
    from beets.ui.commands import default_commands

    # Construct the root parser.
    parser = SubcommandsOptionParser()
    parser.add_option('-l', '--library', dest='library',
                      help='library database file to use')
    parser.add_option('-d', '--directory', dest='directory',
                      help="destination music directory")
    parser.add_option('-v', '--verbose', dest='verbose', action='store_true',
                      help='print debugging information')
    parser.add_option('-c', '--config', dest='config',
                      help='path to configuration file')
    parser.add_option('-h', '--help', dest='help', action='store_true',
                      help='how this help message and exit')

    # Parse the command-line!
    options, subargs = parser.parse_global_options(args)

    # Add any additional config files specified with --config. This
    # special handling lets specified plugins get loaded before we
    # finish parsing the command line.
    if getattr(options, 'config', None) is not None:
        config_path = options.config
        del options.config
        config.set_file(config_path)
    config.set_args(options)

    # Configure the logger.
    if config['verbose'].get(bool):
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)

    config_path = config.user_config_path()
    if os.path.isfile(config_path):
        log.debug('user configuration: {0}'.format(
            util.displayable_path(config_path)))
    else:
        log.debug('no user configuration found at {0}'.format(
            util.displayable_path(config_path)))

    # Add builtin subcommands
    parser.add_subcommand(*default_commands)
    parser.add_subcommand(migrate.migrate_cmd)

    # Now add the plugin commands to the parser.
    _load_plugins()
    for cmd in plugins.commands():
        parser.add_subcommand(cmd)

    # Parse the remainder of the command line with loaded plugins.
    return parser.parse_subcommand(subargs)


def _raw_main(args, lib=None):
    """A helper function for `main` without top-level exception
    handling.
    """
    subcommand, suboptions, subargs = _configure(args)

    if lib is None:
        # Open library file.
        dbpath = config['library'].as_filename()
        try:
            lib = library.Library(
                dbpath,
                config['directory'].as_filename(),
                get_path_formats(),
                get_replacements(),
            )
        except sqlite3.OperationalError:
            raise UserError(u"database file {0} could not be opened".format(
                util.displayable_path(dbpath)
            ))
        plugins.send("library_opened", lib=lib)

    log.debug(u'data directory: {0}\n'
              u'library database: {1}\n'
              u'library directory: {2}'
              .format(
                  util.displayable_path(config.config_dir()),
                  util.displayable_path(lib.path),
                  util.displayable_path(lib.directory),
              ))

    # Configure the MusicBrainz API.
    mb.configure()

    # Invoke the subcommand.
    subcommand.func(lib, suboptions, subargs)
    plugins.send('cli_exit', lib=lib)


def main(args=None):
    """Run the main command-line interface for beets. Includes top-level
    exception handlers that print friendly error messages.
    """
    try:
        _raw_main(args)
    except UserError as exc:
        message = exc.args[0] if exc.args else None
        log.error(u'error: {0}'.format(message))
        sys.exit(1)
    except util.HumanReadableException as exc:
        exc.log(log)
        sys.exit(1)
    except library.FileOperationError as exc:
        # These errors have reasonable human-readable descriptions, but
        # we still want to log their tracebacks for debugging.
        log.debug(traceback.format_exc())
        log.error(exc)
        sys.exit(1)
    except confit.ConfigError as exc:
        log.error(u'configuration error: {0}'.format(exc))
        sys.exit(1)
    except IOError as exc:
        if exc.errno == errno.EPIPE:
            # "Broken pipe". End silently.
            pass
        else:
            raise
    except KeyboardInterrupt:
        # Silently ignore ^C except in verbose mode.
        log.debug(traceback.format_exc())
