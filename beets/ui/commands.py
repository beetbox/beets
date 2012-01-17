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

"""This module provides the default commands for beets' command-line
interface.
"""
from __future__ import with_statement # Python 2.5
import logging
import sys
import os
import time
import itertools
import re

from beets import ui
from beets.ui import print_, decargs
from beets import autotag
import beets.autotag.art
from beets import plugins
from beets import importer
from beets.util import syspath, normpath, ancestry, displayable_path
from beets import library

# Global logger.
log = logging.getLogger('beets')

# The list of default subcommands. This is populated with Subcommand
# objects that can be fed to a SubcommandsOptionParser.
default_commands = []

# Utility.

def _do_query(lib, query, album, also_items=True):
    """For commands that operate on matched items, performs a query
    and returns a list of matching items and a list of matching
    albums. (The latter is only nonempty when album is True.) Raises
    a UserError if no items match. also_items controls whether, when
    fetching albums, the associated items should be fetched also.
    """
    if album:
        albums = list(lib.albums(query))
        items = []
        if also_items:
            for al in albums:
                items += al.items()

    else:
        albums = []
        items = list(lib.items(query))

    if album and not albums:
        raise ui.UserError('No matching albums found.')
    elif not album and not items:
        raise ui.UserError('No matching items found.')
    
    return items, albums

FLOAT_EPSILON = 0.01
def _showdiff(field, oldval, newval, color):
    """Prints out a human-readable field difference line."""
    # Considering floats incomparable for perfect equality, introduce
    # an epsilon tolerance.
    if isinstance(oldval, float) and isinstance(newval, float) and \
            abs(oldval - newval) < FLOAT_EPSILON:
        return

    if newval != oldval:
        if color:
            oldval, newval = ui.colordiff(oldval, newval)
        else:
            oldval, newval = unicode(oldval), unicode(newval)
        print_(u'  %s: %s -> %s' % (field, oldval, newval))


# import: Autotagger and importer.

DEFAULT_IMPORT_COPY           = True
DEFAULT_IMPORT_WRITE          = True
DEFAULT_IMPORT_DELETE         = False
DEFAULT_IMPORT_AUTOT          = True
DEFAULT_IMPORT_TIMID          = False
DEFAULT_IMPORT_ART            = True
DEFAULT_IMPORT_QUIET          = False
DEFAULT_IMPORT_QUIET_FALLBACK = 'skip'
DEFAULT_IMPORT_RESUME         = None # "ask"
DEFAULT_IMPORT_INCREMENTAL    = False
DEFAULT_THREADED              = True
DEFAULT_COLOR                 = True
DEFAULT_IGNORE                = [
    '.*', '*~',
]

VARIOUS_ARTISTS = u'Various Artists'

PARTIAL_MATCH_MESSAGE = u'(partial match!)'

# Importer utilities and support.

def dist_string(dist, color):
    """Formats a distance (a float) as a similarity percentage string.
    The string is colorized if color is True.
    """
    out = '%.1f%%' % ((1 - dist) * 100)
    if color:
        if dist <= autotag.STRONG_REC_THRESH:
            out = ui.colorize('green', out)
        elif dist <= autotag.MEDIUM_REC_THRESH:
            out = ui.colorize('yellow', out)
        else:
            out = ui.colorize('red', out)
    return out

def show_change(cur_artist, cur_album, items, info, dist, color=True):
    """Print out a representation of the changes that will be made if
    tags are changed from (cur_artist, cur_album, items) to info with
    distance dist.
    """
    def show_album(artist, album, partial=False):
        if artist:
            album_description = u'    %s - %s' % (artist, album)
        elif album:
            album_description = u'    %s' % album
        else:
            album_description = u'    (unknown album)'

        # Add a suffix if this is a partial match.
        if partial:
            warning = PARTIAL_MATCH_MESSAGE
        else:
            warning = None
        if color and warning:
            warning = ui.colorize('yellow', warning)

        out = album_description
        if warning:
            out += u' ' + warning
        print_(out)

    # Record if the match is partial or not.
    partial_match = None in items

    # Identify the album in question.
    if cur_artist != info.artist or \
            (cur_album != info.album and info.album != VARIOUS_ARTISTS):
        artist_l, artist_r = cur_artist or '', info.artist
        album_l,  album_r  = cur_album  or '', info.album
        if artist_r == VARIOUS_ARTISTS:
            # Hide artists for VA releases.
            artist_l, artist_r = u'', u''

        if color:
            artist_l, artist_r = ui.colordiff(artist_l, artist_r)
            album_l, album_r   = ui.colordiff(album_l, album_r)

        print_("Correcting tags from:")
        show_album(artist_l, album_l)
        print_("To:")
        show_album(artist_r, album_r)
    else:
        message = u"Tagging: %s - %s" % (info.artist, info.album)
        if partial_match:
            warning = PARTIAL_MATCH_MESSAGE
            if color:
                warning = ui.colorize('yellow', PARTIAL_MATCH_MESSAGE)
            message += u' ' + warning
        print_(message)

    # Distance/similarity.
    print_('(Similarity: %s)' % dist_string(dist, color))

    # Tracks.
    missing_tracks = []
    for i, (item, track_info) in enumerate(zip(items, info.tracks)):
        if not item:
            missing_tracks.append((i, track_info))
            continue
        cur_track = unicode(item.track)
        new_track = unicode(i+1)
        cur_title = item.title
        new_title = track_info.title
        
        # Possibly colorize changes.
        if color:
            cur_title, new_title = ui.colordiff(cur_title, new_title)
            if cur_track != new_track:
                cur_track = ui.colorize('red', cur_track)
                new_track = ui.colorize('red', new_track)

        # Show filename (non-colorized) when title is not set.
        if not item.title.strip():
            cur_title = displayable_path(os.path.basename(item.path))
        
        if cur_title != new_title and cur_track != new_track:
            print_(u" * %s (%s) -> %s (%s)" % (
                cur_title, cur_track, new_title, new_track
            ))
        elif cur_title != new_title:
            print_(u" * %s -> %s" % (cur_title, new_title))
        elif cur_track != new_track:
            print_(u" * %s (%s -> %s)" % (item.title, cur_track, new_track))
    for i, track_info in missing_tracks:
        line = u' * Missing track: %s (%d)' % (track_info.title, i+1)
        if color:
            line = ui.colorize('yellow', line)
        print_(line)

def show_item_change(item, info, dist, color):
    """Print out the change that would occur by tagging `item` with the
    metadata from `info`.
    """
    cur_artist, new_artist = item.artist, info.artist
    cur_title, new_title = item.title, info.title

    if cur_artist != new_artist or cur_title != new_title:
        if color:
            cur_artist, new_artist = ui.colordiff(cur_artist, new_artist)
            cur_title, new_title = ui.colordiff(cur_title, new_title)

        print_("Correcting track tags from:")
        print_("    %s - %s" % (cur_artist, cur_title))
        print_("To:")
        print_("    %s - %s" % (new_artist, new_title))

    else:
        print_("Tagging track: %s - %s" % (cur_artist, cur_title))

    print_('(Similarity: %s)' % dist_string(dist, color))

def should_resume(config, path):
    return ui.input_yn("Import of the directory:\n%s"
                       "\nwas interrupted. Resume (Y/n)?" % path)

def _quiet_fall_back(config):
    """Show the user that the default action is being taken because
    we're in quiet mode and the recommendation is not strong.
    """
    if config.quiet_fallback == importer.action.SKIP:
        print_('Skipping.')
    elif config.quiet_fallback == importer.action.ASIS:
        print_('Importing as-is.')
    else:
        assert(False)
    return config.quiet_fallback

def choose_candidate(candidates, singleton, rec, color, timid,
                     cur_artist=None, cur_album=None, item=None):
    """Given a sorted list of candidates, ask the user for a selection
    of which candidate to use. Applies to both full albums and 
    singletons  (tracks). For albums, the candidates are `(dist, items,
    info)` triples and `cur_artist` and `cur_album` must be provided.
    For singletons, the candidates are `(dist, info)` pairs and `item`
    must be provided.

    Returns the result of the choice, which may SKIP, ASIS, TRACKS, or
    MANUAL or a candidate. For albums, a candidate is a `(info, items)`
    pair; for items, it is just a TrackInfo object.
    """
    # Sanity check.
    if singleton:
        assert item is not None
    else:
        assert cur_artist is not None
        assert cur_album is not None

    # Zero candidates.
    if not candidates:
        print_("No match found.")
        if singleton:
            opts = ('Use as-is', 'Skip', 'Enter search', 'enter Id',
                    'aBort')
        else:
            opts = ('Use as-is', 'as Tracks', 'Skip', 'Enter search',
                    'enter Id', 'aBort')
        sel = ui.input_options(opts, color=color)
        if sel == 'u':
            return importer.action.ASIS
        elif sel == 't':
            assert not singleton
            return importer.action.TRACKS
        elif sel == 'e':
            return importer.action.MANUAL
        elif sel == 's':
            return importer.action.SKIP
        elif sel == 'b':
            raise importer.ImportAbort()
        elif sel == 'i':
            return importer.action.MANUAL_ID
        else:
            assert False

    # Is the change good enough?
    bypass_candidates = False
    if rec != autotag.RECOMMEND_NONE:
        if singleton:
            dist, info = candidates[0]
        else:
            dist, items, info = candidates[0]
        bypass_candidates = True
        
    while True:
        # Display and choose from candidates.
        if not bypass_candidates:
            # Display list of candidates.
            if singleton:
                print_('Finding tags for track "%s - %s".' %
                       (item.artist, item.title))
                print_('Candidates:')
                for i, (dist, info) in enumerate(candidates):
                    print_('%i. %s - %s (%s)' % (i+1, info.artist,
                           info.title, dist_string(dist, color)))
            else:
                print_('Finding tags for album "%s - %s".' %
                       (cur_artist, cur_album))
                print_('Candidates:')
                for i, (dist, items, info) in enumerate(candidates):
                    line = '%i. %s - %s' % (i+1, info.artist, info.album)

                    # Label and year disambiguation, if available.
                    label, year = None, None
                    if info.label:
                        label = info.label
                    if info.year:
                        year = unicode(info.year)
                    if label and year:
                        line += u' [%s, %s]' % (label, year)
                    elif label:
                        line += u' [%s]' % label
                    elif year:
                        line += u' [%s]' % year

                    line += ' (%s)' % dist_string(dist, color)

                    # Point out the partial matches.
                    if None in items:
                        warning = PARTIAL_MATCH_MESSAGE
                        if color:
                            warning = ui.colorize('yellow', warning)
                        line += u' %s' % warning

                    print_(line)
                                            
            # Ask the user for a choice.
            if singleton:
                opts = ('Skip', 'Use as-is', 'Enter search', 'enter Id',
                        'aBort')
            else:
                opts = ('Skip', 'Use as-is', 'as Tracks', 'Enter search',
                        'enter Id', 'aBort')
            sel = ui.input_options(opts, numrange=(1, len(candidates)),
                                   color=color)
            if sel == 's':
                return importer.action.SKIP
            elif sel == 'u':
                return importer.action.ASIS
            elif sel == 'e':
                return importer.action.MANUAL
            elif sel == 't':
                assert not singleton
                return importer.action.TRACKS
            elif sel == 'b':
                raise importer.ImportAbort()
            elif sel == 'i':
                return importer.action.MANUAL_ID
            else: # Numerical selection.
                if singleton:
                    dist, info = candidates[sel-1]
                else:
                    dist, items, info = candidates[sel-1]
        bypass_candidates = False
    
        # Show what we're about to do.
        if singleton:
            show_item_change(item, info, dist, color)
        else:
            show_change(cur_artist, cur_album, items, info, dist, color)
    
        # Exact match => tag automatically if we're not in timid mode.
        if rec == autotag.RECOMMEND_STRONG and not timid:
            if singleton:
                return info
            else:
                return info, items
        
        # Ask for confirmation.
        if singleton:
            opts = ('Apply', 'More candidates', 'Skip', 'Use as-is',
                    'Enter search', 'enter Id', 'aBort')
        else:
            opts = ('Apply', 'More candidates', 'Skip', 'Use as-is',
                    'as Tracks', 'Enter search', 'enter Id', 'aBort')
        sel = ui.input_options(opts, color=color)
        if sel == 'a':
            if singleton:
                return info
            else:
                return info, items
        elif sel == 'm':
            pass
        elif sel == 's':
            return importer.action.SKIP
        elif sel == 'u':
            return importer.action.ASIS
        elif sel == 't':
            assert not singleton
            return importer.action.TRACKS
        elif sel == 'e':
            return importer.action.MANUAL
        elif sel == 'b':
            raise importer.ImportAbort()
        elif sel == 'i':
            return importer.action.MANUAL_ID

def manual_search(singleton):
    """Input either an artist and album (for full albums) or artist and
    track name (for singletons) for manual search.
    """
    artist = raw_input('Artist: ').decode(sys.stdin.encoding)
    name = raw_input('Track: ' if singleton else 'Album: ') \
           .decode(sys.stdin.encoding)
    return artist.strip(), name.strip()

def manual_id(singleton):
    """Input a MusicBrainz ID, either for an album ("release") or a
    track ("recording"). If no valid ID is entered, returns None.
    """
    prompt = 'Enter MusicBrainz %s ID: ' % \
             ('recording' if singleton else 'release')
    entry = raw_input(prompt).decode(sys.stdin.encoding).strip()

    # Find the first thing that looks like a UUID/MBID.
    match = re.search('[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}', entry)
    if match:
       return match.group()
    else:
        log.error('Invalid MBID.')
        return None

def choose_match(task, config):
    """Given an initial autotagging of items, go through an interactive
    dance with the user to ask for a choice of metadata. Returns an
    (info, items) pair, ASIS, or SKIP.
    """
    # Show what we're tagging.
    print_()
    print_(task.path)

    if config.quiet:
        # No input; just make a decision.
        if task.rec == autotag.RECOMMEND_STRONG:
            dist, items, info = task.candidates[0]
            show_change(task.cur_artist, task.cur_album, items, info, dist,
                        config.color)
            return info, items
        else:
            return _quiet_fall_back(config)

    # Loop until we have a choice.
    candidates, rec = task.candidates, task.rec
    while True:
        # Ask for a choice from the user.
        choice = choose_candidate(candidates, False, rec, config.color, 
                                  config.timid, task.cur_artist,
                                  task.cur_album)
    
        # Choose which tags to use.
        if choice in (importer.action.SKIP, importer.action.ASIS,
                      importer.action.TRACKS):
            # Pass selection to main control flow.
            return choice
        elif choice is importer.action.MANUAL:
            # Try again with manual search terms.
            search_artist, search_album = manual_search(False)
            try:
                _, _, candidates, rec = \
                    autotag.tag_album(task.items, config.timid, search_artist,
                                      search_album)
            except autotag.AutotagError:
                candidates, rec = None, None
        elif choice is importer.action.MANUAL_ID:
            # Try a manually-entered ID.
            search_id = manual_id(False)
            if search_id:
                try:
                    _, _, candidates, rec = \
                        autotag.tag_album(task.items, config.timid,
                                        search_id=search_id)
                except autotag.AutotagError:
                    candidates, rec = None, None
        else:
            # We have a candidate! Finish tagging. Here, choice is
            # an (info, items) pair as desired.
            assert not isinstance(choice, importer.action)
            return choice

def choose_item(task, config):
    """Ask the user for a choice about tagging a single item. Returns
    either an action constant or a TrackInfo object.
    """
    print_()
    print_(task.item.path)
    candidates, rec = task.item_match

    if config.quiet:
        # Quiet mode; make a decision.
        if rec == autotag.RECOMMEND_STRONG:
            dist, track_info = candidates[0]
            show_item_change(task.item, track_info, dist, config.color)
            return track_info
        else:
            return _quiet_fall_back(config)

    while True:
        # Ask for a choice.
        choice = choose_candidate(candidates, True, rec, config.color,
                                  config.timid, item=task.item)

        if choice in (importer.action.SKIP, importer.action.ASIS):
            return choice
        elif choice == importer.action.TRACKS:
            assert False # TRACKS is only legal for albums.
        elif choice == importer.action.MANUAL:
            # Continue in the loop with a new set of candidates.
            search_artist, search_title = manual_search(True)
            candidates, rec = autotag.tag_item(task.item, config.timid,
                                               search_artist, search_title)
        elif choice == importer.action.MANUAL_ID:
            # Ask for a track ID.
            search_id = manual_id(True)
            if search_id:
                candidates, rec = autotag.tag_item(task.item, config.timid,
                                                search_id=search_id)
        else:
            # Chose a candidate.
            assert not isinstance(choice, importer.action)
            return choice

# The import command.

def import_files(lib, paths, copy, write, autot, logpath, art, threaded,
                 color, delete, quiet, resume, quiet_fallback, singletons,
                 timid, query, incremental, ignore):
    """Import the files in the given list of paths, tagging each leaf
    directory as an album. If copy, then the files are copied into
    the library folder. If write, then new metadata is written to the
    files themselves. If not autot, then just import the files
    without attempting to tag. If logpath is provided, then untaggable
    albums will be logged there. If art, then attempt to download
    cover art for each album. If threaded, then accelerate autotagging
    imports by running them in multiple threads. If color, then
    ANSI-colorize some terminal output. If delete, then old files are
    deleted when they are copied. If quiet, then the user is
    never prompted for input; instead, the tagger just skips anything
    it is not confident about. resume indicates whether interrupted
    imports can be resumed and is either a boolean or None.
    quiet_fallback should be either ASIS or SKIP and indicates what
    should happen in quiet mode when the recommendation is not strong.
    """
    # Check the user-specified directories.
    for path in paths:
        if not singletons and not os.path.isdir(syspath(path)):
            raise ui.UserError('not a directory: ' + path)
        elif singletons and not os.path.exists(syspath(path)):
            raise ui.UserError('no such file: ' + path)

    # Check parameter consistency.
    if quiet and timid:
        raise ui.UserError("can't be both quiet and timid")

    # Open the log.
    if logpath:
        logpath = normpath(logpath)
        logfile = open(syspath(logpath), 'a')
        print >>logfile, 'import started', time.asctime()
    else:
        logfile = None

    # Never ask for input in quiet mode.
    if resume is None and quiet:
        resume = False

    # Perform the import.
    importer.run_import(
        lib = lib,
        paths = paths,
        resume = resume,
        logfile = logfile,
        color = color,
        quiet = quiet,
        quiet_fallback = quiet_fallback,
        copy = copy,
        write = write,
        art = art,
        delete = delete,
        threaded = threaded,
        autot = autot,
        choose_match_func = choose_match,
        should_resume_func = should_resume,
        singletons = singletons,
        timid = timid,
        choose_item_func = choose_item,
        query = query,
        incremental = incremental,
        ignore = ignore,
    )
    
    # If we were logging, close the file.
    if logfile:
        print >>logfile, ''
        logfile.close()

    # Emit event.
    plugins.send('import', lib=lib, paths=paths)

import_cmd = ui.Subcommand('import', help='import new music',
    aliases=('imp', 'im'))
import_cmd.parser.add_option('-c', '--copy', action='store_true',
    default=None, help="copy tracks into library directory (default)")
import_cmd.parser.add_option('-C', '--nocopy', action='store_false',
    dest='copy', help="don't copy tracks (opposite of -c)")
import_cmd.parser.add_option('-w', '--write', action='store_true',
    default=None, help="write new metadata to files' tags (default)")
import_cmd.parser.add_option('-W', '--nowrite', action='store_false',
    dest='write', help="don't write metadata (opposite of -w)")
import_cmd.parser.add_option('-a', '--autotag', action='store_true',
    dest='autotag', help="infer tags for imported files (default)")
import_cmd.parser.add_option('-A', '--noautotag', action='store_false',
    dest='autotag',
    help="don't infer tags for imported files (opposite of -a)")
import_cmd.parser.add_option('-p', '--resume', action='store_true',
    default=None, help="resume importing if interrupted")
import_cmd.parser.add_option('-P', '--noresume', action='store_false',
    dest='resume', help="do not try to resume importing")
import_cmd.parser.add_option('-r', '--art', action='store_true',
    default=None, help="try to download album art")
import_cmd.parser.add_option('-R', '--noart', action='store_false',
    dest='art', help="don't album art (opposite of -r)")
import_cmd.parser.add_option('-q', '--quiet', action='store_true',
    dest='quiet', help="never prompt for input: skip albums instead")
import_cmd.parser.add_option('-l', '--log', dest='logpath',
    help='file to log untaggable albums for later review')
import_cmd.parser.add_option('-s', '--singletons', action='store_true',
    help='import individual tracks instead of full albums')
import_cmd.parser.add_option('-t', '--timid', dest='timid',
    action='store_true', help='always confirm all actions')
import_cmd.parser.add_option('-L', '--library', dest='library',
    action='store_true', help='retag items matching a query')
import_cmd.parser.add_option('-i', '--incremental', dest='incremental',
    action='store_true', help='skip already-imported directories')
def import_func(lib, config, opts, args):
    copy  = opts.copy  if opts.copy  is not None else \
        ui.config_val(config, 'beets', 'import_copy',
            DEFAULT_IMPORT_COPY, bool)
    write = opts.write if opts.write is not None else \
        ui.config_val(config, 'beets', 'import_write',
            DEFAULT_IMPORT_WRITE, bool)
    delete = ui.config_val(config, 'beets', 'import_delete',
            DEFAULT_IMPORT_DELETE, bool)
    autot = opts.autotag if opts.autotag is not None else DEFAULT_IMPORT_AUTOT
    art = opts.art if opts.art is not None else \
        ui.config_val(config, 'beets', 'import_art',
            DEFAULT_IMPORT_ART, bool)
    threaded = ui.config_val(config, 'beets', 'threaded',
            DEFAULT_THREADED, bool)
    color = ui.config_val(config, 'beets', 'color', DEFAULT_COLOR, bool)
    quiet = opts.quiet if opts.quiet is not None else DEFAULT_IMPORT_QUIET
    quiet_fallback_str = ui.config_val(config, 'beets', 'import_quiet_fallback',
            DEFAULT_IMPORT_QUIET_FALLBACK)
    singletons = opts.singletons
    timid = opts.timid if opts.timid is not None else \
        ui.config_val(config, 'beets', 'import_timid',
            DEFAULT_IMPORT_TIMID, bool)
    logpath = opts.logpath if opts.logpath is not None else \
        ui.config_val(config, 'beets', 'import_log', None)
    incremental = opts.incremental if opts.incremental is not None else \
        ui.config_val(config, 'beets', 'import_incremental',
            DEFAULT_IMPORT_INCREMENTAL, bool)
    ignore = ui.config_val(config, 'beets', 'ignore', DEFAULT_IGNORE, list)

    # Resume has three options: yes, no, and "ask" (None).
    resume = opts.resume if opts.resume is not None else \
        ui.config_val(config, 'beets', 'import_resume', DEFAULT_IMPORT_RESUME)
    if isinstance(resume, basestring):
        if resume.lower() in ('yes', 'true', 't', 'y', '1'):
            resume = True
        elif resume.lower() in ('no', 'false', 'f', 'n', '0'):
            resume = False
        else:
            resume = None

    if quiet_fallback_str == 'asis':
        quiet_fallback = importer.action.ASIS
    else:
        quiet_fallback = importer.action.SKIP

    if opts.library:
        query = args
        paths = []
    else:
        query = None
        paths = args

    import_files(lib, paths, copy, write, autot, logpath, art, threaded,
                 color, delete, quiet, resume, quiet_fallback, singletons,
                 timid, query, incremental, ignore)
import_cmd.func = import_func
default_commands.append(import_cmd)


# list: Query and show library contents.

def list_items(lib, query, album, path):
    """Print out items in lib matching query. If album, then search for
    albums instead of single items. If path, print the matched objects'
    paths instead of human-readable information about them.
    """
    if album:
        for album in lib.albums(query):
            if path:
                print_(album.item_dir())
            else:
                print_(album.albumartist + u' - ' + album.album)
    else:
        for item in lib.items(query):
            if path:
                print_(item.path)
            else:
                print_(item.artist + u' - ' + item.album + u' - ' + item.title)

list_cmd = ui.Subcommand('list', help='query the library', aliases=('ls',))
list_cmd.parser.add_option('-a', '--album', action='store_true',
    help='show matching albums instead of tracks')
list_cmd.parser.add_option('-p', '--path', action='store_true',
    help='print paths for matched items or albums')
def list_func(lib, config, opts, args):
    list_items(lib, decargs(args), opts.album, opts.path)
list_cmd.func = list_func
default_commands.append(list_cmd)


# update: Update library contents according to on-disk tags.

def update_items(lib, query, album, move, color, pretend):
    """For all the items matched by the query, update the library to
    reflect the item's embedded tags.
    """
    items, _ = _do_query(lib, query, album)

    # Walk through the items and pick up their changes.
    affected_albums = set()
    for item in items:
        # Item deleted?
        if not os.path.exists(syspath(item.path)):
            print_(u'X %s - %s' % (item.artist, item.title))
            if not pretend:
                lib.remove(item, True)
            affected_albums.add(item.album_id)
            continue

        # Did the item change since last checked?
        if item.current_mtime() <= item.mtime:
            log.debug(u'skipping %s because mtime is up to date (%i)' %
                      (displayable_path(item.path), item.mtime))
            continue

        # Read new data.
        old_data = dict(item.record)
        item.read()

        # Special-case album artist when it matches track artist. (Hacky
        # but necessary for preserving album-level metadata for non-
        # autotagged imports.)
        if not item.albumartist and \
                old_data['albumartist'] == old_data['artist'] == item.artist:
            item.albumartist = old_data['albumartist']
            item.dirty['albumartist'] = False

        # Get and save metadata changes.
        changes = {}
        for key in library.ITEM_KEYS_META:
            if item.dirty[key]:
                changes[key] = old_data[key], getattr(item, key)
        if changes:
            # Something changed.
            print_(u'* %s - %s' % (item.artist, item.title))
            for key, (oldval, newval) in changes.iteritems():
                _showdiff(key, oldval, newval, color)

            # If we're just pretending, then don't move or save.
            if pretend:
                continue

            # Move the item if it's in the library.
            if move and lib.directory in ancestry(item.path):
                lib.move(item)

            lib.store(item)
            affected_albums.add(item.album_id)
        elif not pretend:
            # The file's mtime was different, but there were no changes
            # to the metadata. Store the new mtime, which is set in the
            # call to read(), so we don't check this again in the
            # future.
            lib.store(item)

    # Skip album changes while pretending.
    if pretend:
        return

    # Modify affected albums to reflect changes in their items.
    for album_id in affected_albums:
        if album_id is None: # Singletons.
            continue
        album = lib.get_album(album_id)
        if not album: # Empty albums have already been removed.
            log.debug('emptied album %i' % album_id)
            continue
        al_items = list(album.items())

        # Update album structure to reflect an item in it.
        for key in library.ALBUM_KEYS_ITEM:
            setattr(album, key, getattr(al_items[0], key))

        # Move album art (and any inconsistent items).
        if move and lib.directory in ancestry(al_items[0].path):
            log.debug('moving album %i' % album_id)
            album.move()

    lib.save()

update_cmd = ui.Subcommand('update',
    help='update the library', aliases=('upd','up',))
update_cmd.parser.add_option('-a', '--album', action='store_true',
    help='show matching albums instead of tracks')
update_cmd.parser.add_option('-M', '--nomove', action='store_false',
    default=True, dest='move', help="don't move files in library")
update_cmd.parser.add_option('-p', '--pretend', action='store_true',
    help="show all changes but do nothing")
def update_func(lib, config, opts, args):
    color = ui.config_val(config, 'beets', 'color', DEFAULT_COLOR, bool)
    update_items(lib, decargs(args), opts.album, opts.move, color, opts.pretend)
update_cmd.func = update_func
default_commands.append(update_cmd)


# remove: Remove items from library, delete files.

def remove_items(lib, query, album, delete=False):
    """Remove items matching query from lib. If album, then match and
    remove whole albums. If delete, also remove files from disk.
    """
    # Get the matching items.
    items, albums = _do_query(lib, query, album)

    # Show all the items.
    for item in items:
        print_(item.artist + ' - ' + item.album + ' - ' + item.title)

    # Confirm with user.
    print_()
    if delete:
        prompt = 'Really DELETE %i files (y/n)?' % len(items)
    else:
        prompt = 'Really remove %i items from the library (y/n)?' % \
                 len(items)
    if not ui.input_yn(prompt, True):
        return

    # Remove (and possibly delete) items.
    if album:
        for al in albums:
            al.remove(delete)
    else:
        for item in items:
            lib.remove(item, delete)

    lib.save()

remove_cmd = ui.Subcommand('remove',
    help='remove matching items from the library', aliases=('rm',))
remove_cmd.parser.add_option("-d", "--delete", action="store_true",
    help="also remove files from disk")
remove_cmd.parser.add_option('-a', '--album', action='store_true',
    help='match albums instead of tracks')
def remove_func(lib, config, opts, args):
    remove_items(lib, decargs(args), opts.album, opts.delete)
remove_cmd.func = remove_func
default_commands.append(remove_cmd)


# stats: Show library/query statistics.

def show_stats(lib, query):
    """Shows some statistics about the matched items."""
    items = lib.items(query)

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

    print_("""Tracks: %i
Total time: %s
Total size: %s
Artists: %i
Albums: %i""" % (
        total_items,
        ui.human_seconds(total_time),
        ui.human_bytes(total_size),
        len(artists), len(albums)
    ))

stats_cmd = ui.Subcommand('stats',
    help='show statistics about the library or a query')
def stats_func(lib, config, opts, args):
    show_stats(lib, decargs(args))
stats_cmd.func = stats_func
default_commands.append(stats_cmd)


# version: Show current beets version.

def show_version(lib, config, opts, args):
    print 'beets version %s' % beets.__version__
    # Show plugins.
    names = []
    for plugin in plugins.find_plugins():
        modname = plugin.__module__
        names.append(modname.split('.')[-1])
    if names:
        print 'plugins:', ', '.join(names)
    else:
        print 'no plugins loaded'
version_cmd = ui.Subcommand('version',
    help='output version information')
version_cmd.func = show_version
default_commands.append(version_cmd)


# modify: Declaratively change metadata.

def modify_items(lib, mods, query, write, move, album, color, confirm):
    """Modifies matching items according to key=value assignments."""
    # Parse key=value specifications into a dictionary.
    allowed_keys = library.ALBUM_KEYS if album else library.ITEM_KEYS_WRITABLE
    fsets = {}
    for mod in mods:
        key, value = mod.split('=', 1)
        if key not in allowed_keys:
            raise ui.UserError('"%s" is not a valid field' % key)
        fsets[key] = value

    # Get the items to modify.
    items, albums = _do_query(lib, query, album, False)
    objs = albums if album else items

    # Preview change.
    print_('Modifying %i %ss.' % (len(objs), 'album' if album else 'item'))
    for obj in objs:
        # Identify the changed object.
        if album:
            print_(u'* %s - %s' % (obj.albumartist, obj.album))
        else:
            print_(u'* %s - %s' % (obj.artist, obj.title))

        # Show each change.
        for field, value in fsets.iteritems():
            curval = getattr(obj, field)
            _showdiff(field, curval, value, color)

    # Confirm.
    if confirm:
        extra = ' and write tags' if write else ''
        if not ui.input_yn('Really modify%s (Y/n)?' % extra):
            return

    # Apply changes to database.
    for obj in objs:
        for field, value in fsets.iteritems():
            setattr(obj, field, value)

        if move:
            cur_path = obj.item_dir() if album else obj.path
            if lib.directory in ancestry(cur_path): # In library?
                log.debug('moving object %s' % cur_path)
                if album:
                    obj.move()
                else:
                    lib.move(obj)

        # When modifying items, we have to store them to the database.
        if not album:
            lib.store(obj)
    lib.save()

    # Apply tags if requested.
    if write:
        if album:
            items = itertools.chain(*(a.items() for a in albums))
        for item in items:
            item.write()

modify_cmd = ui.Subcommand('modify',
    help='change metadata fields', aliases=('mod',))
modify_cmd.parser.add_option('-M', '--nomove', action='store_false',
    default=True, dest='move', help="don't move files in library")
modify_cmd.parser.add_option('-w', '--write', action='store_true',
    default=None, help="write new metadata to files' tags (default)")
modify_cmd.parser.add_option('-W', '--nowrite', action='store_false',
    dest='write', help="don't write metadata (opposite of -w)")
modify_cmd.parser.add_option('-a', '--album', action='store_true',
    help='modify whole albums instead of tracks')
modify_cmd.parser.add_option('-y', '--yes', action='store_true',
    help='skip confirmation')
def modify_func(lib, config, opts, args):
    args = decargs(args)
    mods = [a for a in args if '=' in a]
    query = [a for a in args if '=' not in a]
    if not mods:
        raise ui.UserError('no modifications specified')
    write = opts.write if opts.write is not None else \
        ui.config_val(config, 'beets', 'import_write',
            DEFAULT_IMPORT_WRITE, bool)
    color = ui.config_val(config, 'beets', 'color', DEFAULT_COLOR, bool)
    modify_items(lib, mods, query, write, opts.move, opts.album, color,
                 not opts.yes)
modify_cmd.func = modify_func
default_commands.append(modify_cmd)


# move: Move/copy files to the library or a new base directory.

def move_items(lib, dest, query, copy, album):
    """Moves or copies items to a new base directory, given by dest. If
    dest is None, then the library's base directory is used, making the
    command "consolidate" files.
    """
    items, albums = _do_query(lib, query, album, False)
    objs = albums if album else items

    action = 'Copying' if copy else 'Moving'
    entity = 'album' if album else 'item'
    logging.info('%s %i %ss.' % (action, len(objs), entity))
    for obj in objs:
        old_path = obj.item_dir() if album else obj.path
        logging.debug('moving: %s' % old_path)

        if album:
            obj.move(copy, basedir=dest)
        else:
            lib.move(obj, copy, basedir=dest)
            lib.store(obj)
    lib.save()

move_cmd = ui.Subcommand('move',
    help='move or copy items', aliases=('mv',))
move_cmd.parser.add_option('-d', '--dest', metavar='DIR', dest='dest',
    help='destination directory')
move_cmd.parser.add_option('-c', '--copy', default=False, action='store_true',
    help='copy instead of moving')
move_cmd.parser.add_option('-a', '--album', default=False, action='store_true',
    help='match whole albums instead of tracks')
def move_func(lib, config, opts, args):
    dest = opts.dest
    if dest is not None:
        dest = normpath(dest)
        if not os.path.isdir(dest):
            raise ui.UserError('no such directory: %s' % dest)

    move_items(lib, dest, decargs(args), opts.copy, opts.album)
move_cmd.func = move_func
default_commands.append(move_cmd)
