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

import os
import logging
import locale
import optparse
import textwrap
import ConfigParser

from beets import autotag
from beets import library
from beets.mediafile import UnreadableFileError, FileTypeError
from beets.player import bpd

# Global logger.
log = logging.getLogger('beets')


# Utilities.

def _print(txt=''):
    """Like print, but rather than raising an error when a character
    is not in the terminal's encoding's character set, just silently
    replaces it.
    """
    if isinstance(txt, unicode):
        encoding = locale.getdefaultlocale()[1]
        txt = txt.encode(encoding, 'replace')
    print txt

def _input_options(prompt, options, default=None,
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

def _input_yn(prompt, require=False):
    """Prompts user for a "yes" or "no" response where an empty response
    is treated as "yes". Keeps prompting until acceptable input is
    given; returns a boolean. If require is True, then an empty response
    is not accepted.
    """
    sel = _input_options(
        prompt,
        ('y', 'n'),
        None if require else 'y',
        "Type 'y' or 'n':"
    )
    return (sel == 'y')

def _human_bytes(size):
    """Formats size, a number of bytes, in a human-readable way."""
    suffices = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB', 'HB']
    for suffix in suffices:
        if size < 1024:
            return "%3.1f %s" % (size, suffix)
        size /= 1024.0
    return "big"

def _human_seconds(interval):
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
            if cmdname.startswith('-'):
                parser.error('unknown option ' + cmdname)
            else:
                subcommand = self._subcommand_for_name(cmdname)
                if not subcommand:
                    parser.error('unknown command ' + cmdname)
        
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


# Autotagging interface.

def show_change(cur_artist, cur_album, items, info, dist):
    """Print out a representation of the changes that will be made if
    tags are changed from (cur_artist, cur_album, items) to info with
    distance dist.
    """
    if cur_artist != info['artist'] or cur_album != info['album']:
        _print("Correcting tags from:")
        _print('     %s - %s' % (cur_artist or '', cur_album or ''))
        _print("To:")
        _print('     %s - %s' % (info['artist'], info['album']))
    else:
        _print("Tagging: %s - %s" % (info['artist'], info['album']))
    _print('(Distance: %f)' % dist)
    for i, (item, track_data) in enumerate(zip(items, info['tracks'])):
        cur_track = item.track
        new_track = i+1
        if item.title != track_data['title'] and cur_track != new_track:
            _print(" * %s (%i) -> %s (%i)" % (
                item.title, cur_track, track_data['title'], new_track
            ))
        elif item.title != track_data['title']:
            _print(" * %s -> %s" % (item.title, track_data['title']))
        elif cur_track != new_track:
            _print(" * %s (%i -> %i)" % (item.title, cur_track, new_track))

CHOICE_SKIP = 'CHOICE_SKIP'
CHOICE_ASIS = 'CHOICE_ASIS'
CHOICE_MANUAL = 'CHOICE_MANUAL'
def choose_candidate(cur_artist, cur_album, candidates, rec):
    """Given current metadata and a sorted list of
    (distance, candidate) pairs, ask the user for a selection
    of which candidate to use. Returns the selected candidate.
    If user chooses to skip, use as-is, or search manually, returns
    CHOICE_SKIP, CHOICE_ASIS, or CHOICE_MANUAL.
    """
    # Is the change good enough?
    top_dist, _, _ = candidates[0]
    bypass_candidates = False
    if rec != autotag.RECOMMEND_NONE:
        dist, items, info = candidates[0]
        bypass_candidates = True
        
    while True:
        # Display and choose from candidates.
        if not bypass_candidates:
            _print('Finding tags for "%s - %s".' % (cur_artist, cur_album))
            _print('Candidates:')
            for i, (dist, items, info) in enumerate(candidates):
                _print('%i. %s - %s (%f)' % (i+1, info['artist'],
                                             info['album'], dist))
                                            
            # Ask the user for a choice.
            sel = _input_options(
                '# selection (default 1), Skip, Use as-is, or '
                'Enter manual search?',
                ('s', 'u', 'e'), '1',
                'Enter a numerical selection, S, U, or E:',
                (1, len(candidates))
            )
            if sel == 's':
                return CHOICE_SKIP
            elif sel == 'u':
                return CHOICE_ASIS
            elif sel == 'e':
                return CHOICE_MANUAL
            else: # Numerical selection.
                dist, items, info = candidates[sel-1]
        bypass_candidates = False
    
        # Show what we're about to do.
        show_change(cur_artist, cur_album, items, info, dist)
    
        # Exact match => tag automatically.
        if rec == autotag.RECOMMEND_STRONG:
            return info
        
        # Ask for confirmation.
        sel = _input_options(
            '[A]pply, More candidates, Skip, Use as-is, or '
            'Enter manual search?',
            ('a', 'm', 's', 'u', 'e'), 'a',
            'Enter A, M, S, U, or E:'
        )
        if sel == 'a':
            return info
        elif sel == 'm':
            pass
        elif sel == 's':
            return CHOICE_SKIP
        elif sel == 'u':
            return CHOICE_ASIS
        elif sel == 'e':
            return CHOICE_MANUAL

def manual_search():
    """Input an artist and album for manual search."""
    artist = raw_input('Artist: ')
    album = raw_input('Album: ')
    return artist.strip(), album.strip()

def tag_log(logfile, status, items):
    """Log a message about a given album to logfile. The status should
    reflect the reason the album couldn't be tagged.
    """
    path = os.path.commonprefix([item.path for item in items])
    print >>logfile, status, os.path.dirname(path)

def tag_album(items, lib, copy=True, write=True, logfile=None):
    """Import items into lib, tagging them as an album. If copy, then
    items are copied into the destination directory. If write, then
    new metadata is written back to the files' tags. If logfile is
    provided, then a log message will be added there if the album is
    untaggable.
    """
    # Try to get candidate metadata.
    search_artist, search_album = None, None
    cur_artist, cur_album = None, None
    while True:
        # Infer tags.
        try:
            cur_artist, cur_album, candidates, rec = \
                    autotag.tag_album(items, search_artist, search_album)
        except autotag.AutotagError:
            cur_artist, cur_album, candidates, rec = None, None, None, None
            info = None
        else:
            if candidates:
                info = choose_candidate(cur_artist, cur_album, candidates, rec)
            else:
                info = None
        
        # Fallback: if either an error ocurred or no matches found.
        if not info:
            _print("No match found for:", os.path.dirname(items[0].path))
            sel = _input_options(
                "[U]se as-is, Skip, or Enter manual search?",
                ('u', 's', 'e'), 'u',
                'Enter U, S, or E:'
            )
            if sel == 'u':
                info = CHOICE_ASIS
            elif sel == 'e':
                info = CHOICE_MANUAL
            elif sel == 's':
                info = CHOICE_SKIP
    
        # Choose which tags to use.
        if info is CHOICE_SKIP:
            # Skip entirely.
            tag_log(logfile, 'skip', items)
            return
        elif info is CHOICE_MANUAL:
            # Try again with manual search terms.
            search_artist, search_album = manual_search()
        else:
            # Either ASIS or we have a candidate. Continue tagging.
            break
    
    # Ensure that we don't have the album already.
    if info is not CHOICE_ASIS or cur_artist is not None:
        if info is CHOICE_ASIS:
            artist = cur_artist
            album = cur_album
            tag_log(logfile, 'asis', items)
        else:
            artist = info['artist']
            album = info['album']
        q = library.AndQuery((library.MatchQuery('artist', artist),
                              library.MatchQuery('album',  album)))
        count, _ = q.count(lib)
        if count >= 1:
            _print("This album (%s - %s) is already in the library!" %
                   (artist, album))
            return
    
    # Change metadata, move, and copy.
    if info is not CHOICE_ASIS:
        autotag.apply_metadata(items, info)
    for item in items:
        if copy:
            item.move(lib, True)
        if write and info is not CHOICE_ASIS:
            item.write()

    # Add items to library. We consolidate this at the end to avoid
    # locking while we do the copying and tag updates.
    for item in items:
        lib.add(item)


# Top-level commands.

def import_files(lib, paths, copy=True, write=True, autot=True, logpath=None):
    """Import the files in the given list of paths, tagging each leaf
    directory as an album. If copy, then the files are copied into
    the library folder. If write, then new metadata is written to the
    files themselves. If not autot, then just import the files
    without attempting to tag. If logpath is provided, then untaggable
    albums will be logged there.
    """
    if logpath:
        logfile = open(logpath, 'w')
    else:
        logfile = None
    
    if autot:        
        # Make sure we have only directories.
        for path in paths:
            if not os.path.isdir(path):
                #fixme should show command usage
                _print('not a directory: ' + path)
                return
        
        # Crawl albums and tag them.
        first = True
        for path in paths:
            for album in autotag.albums_in_dir(os.path.expanduser(path)):
                if not first:
                    _print()
                first = False

                # Infer tags.
                tag_album(album, lib, copy, write, logfile)
                
                # Write the database after each album.
                lib.save()
    
    else:
        # No autotagging. Just walk the paths.
        for path in paths:
            if os.path.isdir(path):
                # Find all files in the directory.
                filepaths = []
                for root, dirs, files in autotag._sorted_walk(path):
                    for filename in files:
                        filepaths.append(os.path.join(root, filename))
            else:
                # Just add the file.
                filepaths = [path]
            
            # Add all the files.
            for filepath in filepaths:
                try:
                    item = library.Item.from_path(filepath)
                except FileTypeError:
                    continue
                except UnreadableFileError:
                    log.warn('unreadable file: ' + filepath)
                    continue
                
            
                # Add the item to the library, copying if requested.
                if copy:
                    item.move(lib, True)
                # Don't write tags because nothing changed.
                lib.add(item)
        
        # Save when completely finished.
        lib.save()
    
    # If we were logging, close the file.
    if logfile:
        logfile.close()

def list_items(lib, query, album):
    """Print out items in lib matching query. If album, then search for
    albums instead of single items.
    """
    if album:
        for artist, album in lib.albums(query=query):
            _print(artist + ' - ' + album)
    else:
        for item in lib.items(query=query):
            _print(item.artist + ' - ' + item.album + ' - ' + item.title)

def remove_items(lib, query, album, delete=False):
    """Remove items matching query from lib. If album, then match and
    remove whole albums. If delete, also remove files from disk.
    """
    # Get the matching items.
    if album:
        items = []
        for artist, album in lib.albums(query=query):
            items += list(lib.items(artist=artist, album=album))
    else:
        items = list(lib.items(query=query))

    if not items:
        _print('No matching items found.')
        return

    # Show all the items.
    for item in items:
        _print(item.artist + ' - ' + item.album + ' - ' + item.title)

    # Confirm with user.
    _print()
    if delete:
        prompt = 'Really DELETE %i files (y/n)?' % len(items)
    else:
        prompt = 'Really remove %i items from the library (y/n)?' % \
                 len(items)
    if not _input_yn(prompt, True):
        return

    # Remove and delete.
    for item in items:
        lib.remove(item)
        if delete:
            os.unlink(item.path)
    lib.save()

def device_add(lib, query, name):
    """Add items matching query from lib to a device with the given
    name.
    """
    items = lib.items(query=query)

    from beets import device
    pod = device.PodLibrary.by_name(name)
    for item in items:
        pod.add(item)
    pod.save()

def start_bpd(lib, host, port, password, debug):
    """Starts a BPD server."""
    log = logging.getLogger('beets.player.bpd')
    if debug:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.WARNING)
    try:
        bpd.Server(lib, host, port, password).run()    
    except bpd.NoGstreamerError:
        _print('Gstreamer Python bindings not found.')
        _print('Install "python-gst0.10", "py26-gst-python", or similar ' \
               'package to use BPD.')
        return

def show_stats(lib, query):
    """Shows some statistics about the matched items."""
    items = lib.items(query=query)

    total_size = 0
    total_time = 0.0
    total_items = 0
    artists = set()
    albums = set()

    for item in items:
        #fixme This is approximate, so people might complain that
        # this total size doesn't match "du -sh". Could fix this
        # by putting total file size in the database.
        total_size += int(item.length * item.bitrate / 8)
        total_time += item.length
        total_items += 1
        artists.add(item.artist)
        albums.add(item.album)

    _print("""Tracks: %i
Total time: %s
Total size: %s
Artists: %i
Albums: %i""" % (
        total_items,
        _human_seconds(total_time),
        _human_bytes(total_size),
        len(artists), len(albums)
    ))


# XXX
CONFIG_DEFAULTS = {
    'beets': {
        'library': '~/.beetsmusic.blb',
        'directory': '~/Music',
        'path_format': '$artist/$album/$track $title',
        'import_copy': True,
        'import_write': True,
    },

    'bpd': {
        'host': '',
        'port': '6600',
        'password': '',
    },
}
def _cfg_get(config, section, name, vtype=None):
    try:
        if vtype is bool:
            return config.getboolean(section, name)
        else:
            return config.get(section, name)
    except ConfigParser.NoOptionError:
        return CONFIG_DEFAULTS[section][name]
def make_query(criteria):
    """Make  query string for the list of criteria."""
    return ' '.join(criteria).strip() or None



# Default subcommands.

default_subcommands = []

import_cmd = Subcommand('import', help='import new music',
    aliases=('imp', 'im'))
import_cmd.parser.add_option('-c', '--copy', action='store_true',
    default=None, help="copy tracks into library directory (default)")
import_cmd.parser.add_option('-C', '--nocopy', action='store_false',
    dest='copy', help="don't copy tracks (opposite of -c)")
import_cmd.parser.add_option('-w', '--write', action='store_true',
    default=None, help="write new metadata to files' tags (default)")
import_cmd.parser.add_option('-W', '--nowrite', action='store_false',
    dest='write', help="don't write metadata (opposite of -s)")
import_cmd.parser.add_option('-a', '--autotag', action='store_true',
    dest='autotag', help="infer tags for imported files (default)")
import_cmd.parser.add_option('-A', '--noautotag', action='store_false',
    dest='autotag',
    help="don't infer tags for imported files (opposite of -a)")
import_cmd.parser.add_option('-l', '--log', dest='logpath',
    help='file to log untaggable albums for later review')
def import_func(lib, config, opts, args):
    copy  = opts.copy  if opts.copy  is not None else \
            self._cfg_get('beets', 'import_copy', bool)
    write = opts.write if opts.write is not None else \
            self._cfg_get('beets', 'import_write', bool)
    autot = opts.autotag if opts.autotag is not None else True
    import_files(lib, args, copy, write, autot, opts.logpath)
import_cmd.func = import_func
default_subcommands.append(import_cmd)

list_cmd = Subcommand('list', help='query the library', aliases=('ls',))
list_cmd.parser.add_option('-a', '--album', action='store_true',
    help='show matching albums instead of tracks')
def list_func(lib, config, opts, args):
    list_items(lib, make_query(args), opts.album)
list_cmd.func = list_func
default_subcommands.append(list_cmd)

remove_cmd = Subcommand('remove',
    help='remove matching items from the library', aliases=('rm',))
remove_cmd.parser.add_option("-d", "--delete", action="store_true",
    help="also remove files from disk")
remove_cmd.parser.add_option('-a', '--album', action='store_true',
    help='match albums instead of tracks')
def remove_func(lib, config, opts, args):
    remove_items(lib, make_query(args), opts.album, opts.delete)
remove_cmd.func = remove_func
default_subcommands.append(remove_cmd)

bpd_cmd = Subcommand('bpd', help='run an MPD-compatible music player server')
bpd_cmd.parser.add_option('-d', '--debug', action='store_true',
    help='dump all MPD traffic to stdout')
def bpd_func(lib, config, opts, args):
    host = args.pop(0) if args else _cfg_get(config, 'bpd', 'host')
    port = args.pop(0) if args else _cfg_get(config, 'bpd', 'port')
    password = _cfg_get(config, 'bpd', 'password')
    debug = opts.debug or False
    start_bpd(lib, host, int(port), password, debug)
bpd_cmd.func = bpd_func
default_subcommands.append(bpd_cmd)

dadd_cmd = Subcommand('dadd', help='add files to a device')
def dadd_func(lib, config, opts, args):
    name = args.pop(0)
    # fixme require exactly one arg
    device_add(lib, make_query(args), name)
dadd_cmd.func = dadd_func
default_subcommands.append(dadd_cmd)

stats_cmd = Subcommand('stats',
    help='show statistics about the library or a query')
def stats_func(lib, config, opts, args):
    show_stats(lib, make_query(args))
stats_cmd.func = stats_func
default_subcommands.append(stats_cmd)
