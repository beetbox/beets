# This file is part of beets.
# Copyright 2011, Adrian Sampson.
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
import os
import locale
import optparse
import textwrap
import ConfigParser
import sys
from difflib import SequenceMatcher
import logging
import sqlite3
import errno
import re

from beets import library
from beets import plugins
from beets import util

# Constants.
CONFIG_PATH_VAR = 'BEETSCONFIG'
DEFAULT_CONFIG_FILENAME_UNIX = '.beetsconfig'
DEFAULT_CONFIG_FILENAME_WINDOWS = 'beetsconfig.ini'
DEFAULT_LIBRARY_FILENAME_UNIX = '.beetsmusic.blb'
DEFAULT_LIBRARY_FILENAME_WINDOWS = 'beetsmusic.blb'
DEFAULT_DIRECTORY_NAME = 'Music'
WINDOWS_BASEDIR = os.environ.get('APPDATA') or '~'
PF_KEY_QUERIES = {
    'comp': 'comp:true',
    'singleton': 'singleton:true',
}
DEFAULT_PATH_FORMATS = [
    (library.PF_KEY_DEFAULT,      '$albumartist/$album/$track $title'),
    (PF_KEY_QUERIES['singleton'], 'Non-Album/$artist/$title'),
    (PF_KEY_QUERIES['comp'],      'Compilations/$album/$track $title'),
]
DEFAULT_ART_FILENAME = 'cover'
DEFAULT_TIMEOUT = 5.0

# UI exception. Commands should throw this in order to display
# nonrecoverable errors to the user.
class UserError(Exception):
    pass


# Utilities.

def _encoding():
    """Tries to guess the encoding uses by the terminal."""
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
    print txt

def input_options(options, require=False, prompt=None, fallback_prompt=None,
                  numrange=None, default=None, color=False, max_width=72):
    """Prompts a user for input. The sequence of `options` defines the
    choices the user has. A single-letter shortcut is inferred for each
    option; the user's choice is returned as that single, lower-case
    letter. The options should be provided as lower-case strings unless
    a particular shortcut is desired; in that case, only that letter
    should be capitalized.

    By default, the first option is the default. If `require` is
    provided, then there is no default. `default` can be provided to
    override this. The prompt and fallback prompt are also inferred but
    can be overridden.

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
                    continue # Don't use punctuation.
                if letter not in letters:
                    found_letter = letter
                    break
            else:
                raise ValueError('no unambiguous lettering found')

        letters[found_letter.lower()] = option
        index = option.index(found_letter)

        # Mark the option's shortcut letter for display.
        if (default is None and not numrange and first) \
           or (isinstance(default, basestring) and 
               found_letter.lower() == default.lower()):
            # The first option is the default; mark it.
            show_letter = '[%s]' % found_letter.upper()
            is_default = True
        else:
            show_letter = found_letter.upper()
            is_default = False

        # Possibly colorize the letter shortcut.
        if color:
            color = 'turquoise' if is_default else 'blue'
            show_letter = colorize(color, show_letter)

        # Insert the highlighted letter back into the word.
        capitalized.append(
            option[:index] + show_letter + option[index+1:]
        )
        display_letters.append(found_letter.upper())

        first = False

    # The default is just the first option if unspecified.
    if default is None:
        if require:
            default = None
        elif numrange:
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
                if color:
                    default_name = colorize('turquoise', default_name)
                tmpl = '# selection (default %s)'
                prompt_parts.append(tmpl % default_name)
                prompt_part_lengths.append(len(tmpl % str(default)))
            else:
                prompt_parts.append('# selection')
                prompt_part_lengths.append(prompt_parts[-1])
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

    # (raw_input(prompt) was causing problems with colors.)
    print prompt,
    resp = raw_input()
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
        print fallback_prompt,
        resp = raw_input()

def input_yn(prompt, require=False, color=False):
    """Prompts the user for a "yes" or "no" response. The default is
    "yes" unless `require` is `True`, in which case there is no default.
    """
    sel = input_options(
        ('y', 'n'), require, prompt, 'Enter Y or N:', color=color
    )
    return sel == 'y'

def config_val(config, section, name, default, vtype=None):
    """Queries the configuration file for a value (given by the section
    and name). If no value is present, returns default.  vtype
    optionally specifies the return type (although only ``bool`` and
    ``list`` are supported for now).
    """
    if not config.has_section(section):
        config.add_section(section)
    
    try:
        if vtype is bool:
            return config.getboolean(section, name)
        elif vtype is list:
            # Whitespace-separated strings.
            strval = config.get(section, name, True)
            return strval.split()
        else:
            return config.get(section, name, True)
    except ConfigParser.NoOptionError:
        return default

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
    interval.
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
    for i in range(len(units)-1):
        increment, suffix = units[i]
        next_increment, _ = units[i+1]
        interval /= float(increment)
        if interval < next_increment:
            break
    else:
        # Last unit.
        increment, suffix = units[-1]
        interval /= float(increment)

    return "%3.1f %ss" % (interval, suffix)

# ANSI terminal colorization code heavily inspired by pygments:
# http://dev.pocoo.org/hg/pygments-main/file/b2deea5b5030/pygments/console.py
# (pygments is by Tim Hatch, Armin Ronacher, et al.)
COLOR_ESCAPE = "\x1b["
DARK_COLORS  = ["black", "darkred", "darkgreen", "brown", "darkblue",
                "purple", "teal", "lightgray"]
LIGHT_COLORS = ["darkgray", "red", "green", "yellow", "blue",
                "fuchsia", "turquoise", "white"]
RESET_COLOR = COLOR_ESCAPE + "39;49;00m"
def colorize(color, text):
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

def colordiff(a, b, highlight='red'):
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
            # Right and left differ.
            a_out.append(colorize(highlight, a[a_start:a_end]))
            b_out.append(colorize(highlight, b[b_start:b_end]))
        else:
            assert(False)
    
    return u''.join(a_out), u''.join(b_out)

def default_paths(pathmod=None):
    """Produces the appropriate default config, library, and directory
    paths for the current system. On Unix, this is always in ~. On
    Windows, tries ~ first and then $APPDATA for the config and library
    files (for backwards compatibility).
    """
    pathmod = pathmod or os.path
    windows = pathmod.__name__ == 'ntpath'
    if windows:
        windata = os.environ.get('APPDATA') or '~'

    # Shorthand for joining paths.
    def exp(*vals):
        return pathmod.expanduser(pathmod.join(*vals))

    config = exp('~', DEFAULT_CONFIG_FILENAME_UNIX)
    if windows and not pathmod.exists(config):
        config = exp(windata, DEFAULT_CONFIG_FILENAME_WINDOWS)

    libpath = exp('~', DEFAULT_LIBRARY_FILENAME_UNIX)
    if windows and not pathmod.exists(libpath):
        libpath = exp(windata, DEFAULT_LIBRARY_FILENAME_WINDOWS)

    libdir = exp('~', DEFAULT_DIRECTORY_NAME)

    return config, libpath, libdir

def _get_replacements(config):
    """Given a ConfigParser, get the list of replacement pairs. If no
    replacements are specified, returns None. Otherwise, returns a list
    of (compiled regex, replacement string) pairs.
    """
    repl_string = config_val(config, 'beets', 'replace', None)
    if not repl_string:
        return

    parts = repl_string.strip().split()
    if not parts:
        return
    if len(parts) % 2 != 0:
        # Must have an even number of parts.
        raise UserError(u'"replace" config value must consist of'
                        u' pattern/replacement pairs')

    out = []
    for index in xrange(0, len(parts), 2):
        pattern = parts[index]
        replacement = parts[index+1]
        out.append((re.compile(pattern), replacement))
    return out

def _get_path_formats(config):
    """Returns a list of path formats (query/template pairs); reflecting
    the config's specified path formats.
    """
    legacy_path_format = config_val(config, 'beets', 'path_format', None)
    if legacy_path_format:
        # Old path formats override the default values.
        path_formats = [(library.PF_KEY_DEFAULT, legacy_path_format)]
    else:
        # If no legacy path format, use the defaults instead.
        path_formats = DEFAULT_PATH_FORMATS
    if config.has_section('paths'):
        custom_path_formats = []
        for key, value in config.items('paths', True):
            if key in PF_KEY_QUERIES:
                # Special values that indicate simple queries.
                key = PF_KEY_QUERIES[key]
            elif key != library.PF_KEY_DEFAULT:
                # For non-special keys (literal queries), the _
                # character denotes a :.
                key = key.replace('_', ':')
            custom_path_formats.append((key, value))
        path_formats = custom_path_formats + path_formats
    return path_formats


# Subcommand parsing infrastructure.

# This is a fairly generic subcommand parser for optparse. It is
# maintained externally here:
# http://gist.github.com/462717
# There you will also find a better description of the code and a more
# succinct example program.

class Subcommand(object):
    """A subcommand of a root command-line application that may be
    invoked by a SubcommandOptionParser.
    """
    def __init__(self, name, parser=None, help='', aliases=()):
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

class SubcommandsOptionParser(optparse.OptionParser):
    """A variant of OptionParser that parses subcommands and their
    arguments.
    """
    # A singleton command used to give help on other subcommands.
    _HelpSubcommand = Subcommand('help', optparse.OptionParser(),
        help='give detailed help on a specific sub-command',
        aliases=('?',))
    
    def __init__(self, *args, **kwargs):
        """Create a new subcommand-aware option parser. All of the
        options to OptionParser.__init__ are supported in addition
        to subcommands, a sequence of Subcommand objects.
        """
        # The subcommand array, with the help command included.
        self.subcommands = list(kwargs.pop('subcommands', []))
        self.subcommands.append(self._HelpSubcommand)
        
        # A more helpful default usage.
        if 'usage' not in kwargs:
            kwargs['usage'] = """
  %prog COMMAND [ARGS...]
  %prog help COMMAND"""
        
        # Super constructor.
        optparse.OptionParser.__init__(self, *args, **kwargs)
        
        # Adjust the help-visible name of each subcommand.
        for subcommand in self.subcommands:
            subcommand.parser.prog = '%s %s' % \
                    (self.get_prog_name(), subcommand.name)
        
        # Our root parser needs to stop on the first unrecognized argument.  
        self.disable_interspersed_args()
    
    def add_subcommand(self, cmd):
        """Adds a Subcommand object to the parser's list of commands.
        """
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
        for subcommand in self.subcommands:
            name = subcommand.name
            if subcommand.aliases:
                name += ' (%s)' % ', '.join(subcommand.aliases)
            disp_names.append(name)
                
            # Set the help position based on the max width.
            proposed_help_position = len(name) + formatter.current_indent + 2
            if proposed_help_position <= formatter.max_help_position:
                help_position = max(help_position, proposed_help_position)        
        
        # Add each subcommand to the output.
        for subcommand, name in zip(self.subcommands, disp_names):
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
    
    def parse_args(self, a=None, v=None):
        """Like OptionParser.parse_args, but returns these four items:
        - options: the options passed to the root parser
        - subcommand: the Subcommand object that was invoked
        - suboptions: the options passed to the subcommand parser
        - subargs: the positional arguments passed to the subcommand
        """  
        options, args = optparse.OptionParser.parse_args(self, a, v)
        
        if not args:
            # No command given.
            self.print_help()
            self.exit()
        else:
            cmdname = args.pop(0)
            subcommand = self._subcommand_for_name(cmdname)
            if not subcommand:
                self.error('unknown command ' + cmdname)
        
        suboptions, subargs = subcommand.parser.parse_args(args)

        if subcommand is self._HelpSubcommand:
            if subargs:
                # particular
                cmdname = subargs[0]
                helpcommand = self._subcommand_for_name(cmdname)
                helpcommand.parser.print_help()
                self.exit()
            else:
                # general
                self.print_help()
                self.exit()
        
        return options, subcommand, suboptions, subargs


# The root parser and its main function.

def main(args=None, configfh=None):
    """Run the main command-line interface for beets."""
    # Get the default subcommands.
    from beets.ui.commands import default_commands

    # Get default file paths.
    default_config, default_libpath, default_dir = default_paths()

    # Read defaults from config file.
    config = ConfigParser.SafeConfigParser()
    if configfh:
        configpath = None
    elif CONFIG_PATH_VAR in os.environ:
        configpath = os.path.expanduser(os.environ[CONFIG_PATH_VAR])
    else:
        configpath = default_config
    if configpath:
        configpath = util.syspath(configpath)
        if os.path.exists(util.syspath(configpath)):
            configfh = open(configpath)
        else:
            configfh = None
    if configfh:
        config.readfp(configfh)

    # Add plugin paths.
    plugpaths = config_val(config, 'beets', 'pluginpath', '')
    for plugpath in plugpaths.split(':'):
        sys.path.append(os.path.expanduser(plugpath))
    # Load requested plugins.
    plugnames = config_val(config, 'beets', 'plugins', '')
    plugins.load_plugins(plugnames.split())
    plugins.load_listeners()
    plugins.send("pluginload")
    plugins.configure(config)

    # Construct the root parser.
    commands = list(default_commands)
    commands += plugins.commands()
    parser = SubcommandsOptionParser(subcommands=commands)
    parser.add_option('-l', '--library', dest='libpath',
                      help='library database file to use')
    parser.add_option('-d', '--directory', dest='directory',
                      help="destination music directory")
    parser.add_option('-v', '--verbose', dest='verbose', action='store_true',
                      help='print debugging information')
    
    # Parse the command-line!
    options, subcommand, suboptions, subargs = parser.parse_args(args)
    
    # Open library file.
    libpath = options.libpath or \
        config_val(config, 'beets', 'library', default_libpath)
    directory = options.directory or \
        config_val(config, 'beets', 'directory', default_dir)
    path_formats = _get_path_formats(config)
    art_filename = \
        config_val(config, 'beets', 'art_filename', DEFAULT_ART_FILENAME)
    lib_timeout = config_val(config, 'beets', 'timeout', DEFAULT_TIMEOUT)
    replacements = _get_replacements(config)
    try:
        lib_timeout = float(lib_timeout)
    except ValueError:
        lib_timeout = DEFAULT_TIMEOUT
    db_path = os.path.expanduser(libpath)
    try:
        lib = library.Library(db_path,
                              directory,
                              path_formats,
                              art_filename,
                              lib_timeout,
                              replacements)
    except sqlite3.OperationalError:
        raise UserError("database file %s could not be opened" % db_path)
    
    # Configure the logger.
    log = logging.getLogger('beets')
    if options.verbose:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)
    log.debug(u'config file: %s' % configpath)
    log.debug(u'library database: %s' % lib.path)
    log.debug(u'library directory: %s' % lib.directory)
    
    # Invoke the subcommand.
    try:
        subcommand.func(lib, config, suboptions, subargs)
    except UserError, exc:
        message = exc.args[0] if exc.args else None
        subcommand.parser.error(message)
    except IOError, exc:
        if exc.errno == errno.EPIPE:
            # "Broken pipe". End silently.
            pass
        else:
            raise
