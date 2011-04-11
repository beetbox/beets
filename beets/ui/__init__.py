# This file is part of beets.
# Copyright 2010, Adrian Sampson.
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

from beets import library
from beets import plugins

# Constants.
CONFIG_PATH_VAR = 'BEETSCONFIG'
DEFAULT_CONFIG_FILE = os.path.expanduser('~/.beetsconfig')
DEFAULT_LIBRARY = '~/.beetsmusic.blb'
DEFAULT_DIRECTORY = '~/Music'
DEFAULT_PATH_FORMATS = {
    'default': '$albumartist/$album/$track $title',
    'comp': 'Compilations/$album/$track $title',
    'singleton': 'Non-Album/$artist/$title',
}
DEFAULT_ART_FILENAME = 'cover'


# UI exception. Commands should throw this in order to display
# nonrecoverable errors to the user.
class UserError(Exception):
    pass


# Utilities.

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
        try:
            encoding = locale.getdefaultlocale()[1] or 'utf8'
        except ValueError:
            # Invalid locale environment variable setting. To avoid
            # failing entirely for no good reason, assume UTF-8.
            encoding = 'utf8'
        txt = txt.encode(encoding, 'replace')
    print txt

def input_options(prompt, options, default=None,
                  fallback_prompt=None, numrange=None):
    """Prompts a user for input. The input must be one of the single
    letters in options, a list of single-letter strings, or an integer
    in numrange, which is a (low, high) tuple. If nothing is entered,
    assume the input is default (if provided). Returns the value
    entered, a single-letter string or an integer. If an incorrect
    input occurs, fallback_prompt is used (by default identical to
    the initial prompt).
    """
    fallback_prompt = fallback_prompt or prompt
    
    resp = raw_input(prompt + ' ')
    while True:
        resp = resp.strip().lower()
        
        # Try default option.
        if default is not None and not resp:
            resp = default
        
        # Try an integer input if available.
        if numrange is not None:
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
            if resp in options:
                return resp
        
        # Prompt for new input.
        resp = raw_input(fallback_prompt + ' ')

def input_yn(prompt, require=False):
    """Prompts user for a "yes" or "no" response where an empty response
    is treated as "yes". Keeps prompting until acceptable input is
    given; returns a boolean. If require is True, then an empty response
    is not accepted.
    """
    sel = input_options(
        prompt,
        ('y', 'n'),
        None if require else 'y',
        "Type 'y' or 'n':"
    )
    return (sel == 'y')

def make_query(criteria):
    """Make query string for the list of criteria."""
    return ' '.join(criteria).strip() or None

def config_val(config, section, name, default, vtype=None):
    """Queries the configuration file for a value (given by the
    section and name). If no value is present, returns default.
    vtype optionally specifies the return type (although only bool
    is supported for now).
    """
    if not config.has_section(section):
        config.add_section(section)
    
    try:
        if vtype is bool:
            return config.getboolean(section, name)
        else:
            return config.get(section, name)
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
    """Given two strings, return the same pair of strings except with
    their differences highlighted in the specified color.
    """
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
    
    return ''.join(a_out), ''.join(b_out)


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

    # Read defaults from config file.
    config = ConfigParser.SafeConfigParser()
    if configfh:
        pass
    elif CONFIG_PATH_VAR in os.environ:
        configfh = open(os.path.expanduser(os.environ[CONFIG_PATH_VAR]))
    else:
        configfh = open(DEFAULT_CONFIG_FILE)
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
    parser.add_option('-p', '--pathformat', dest='path_format',
                      help="destination path format string")
    parser.add_option('-v', '--verbose', dest='verbose', action='store_true',
                      help='print debugging information')
    
    # Parse the command-line!
    options, subcommand, suboptions, subargs = parser.parse_args(args)
    
    # Open library file.
    libpath = options.libpath or \
        config_val(config, 'beets', 'library', DEFAULT_LIBRARY)
    directory = options.directory or \
        config_val(config, 'beets', 'directory', DEFAULT_DIRECTORY)
    legacy_path_format = config_val(config, 'beets', 'path_format', None)
    if options.path_format:
        # If given, -p overrides all path format settings
        path_formats = {'default': options.path_format}
    else:
        if legacy_path_format:
            # Old path formats override the default values.
            path_formats = {'default': legacy_path_format}
        else:
            # If no legacy path format, use the defaults instead.
            path_formats = DEFAULT_PATH_FORMATS
        if config.has_section('paths'):
            path_formats.update(config.items('paths'))
    art_filename = \
        config_val(config, 'beets', 'art_filename', DEFAULT_ART_FILENAME)
    lib = library.Library(os.path.expanduser(libpath),
                          directory,
                          path_formats,
                          art_filename)
    
    # Configure the logger.
    log = logging.getLogger('beets')
    if options.verbose:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)
    
    # Invoke the subcommand.
    try:
        subcommand.func(lib, config, suboptions, subargs)
    except UserError, exc:
        message = exc.args[0] if exc.args else None
        subcommand.parser.error(message)
