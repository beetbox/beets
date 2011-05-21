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

from beets import ui
from beets.ui import print_
from beets import autotag
import beets.autotag.art
from beets import plugins
from beets import importer
from beets.util import syspath, normpath

# Global logger.
log = logging.getLogger('beets')

# The list of default subcommands. This is populated with Subcommand
# objects that can be fed to a SubcommandsOptionParser.
default_commands = []


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
DEFAULT_THREADED              = True
DEFAULT_COLOR                 = True

VARIOUS_ARTISTS = u'Various Artists'

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
    def show_album(artist, album):
        if artist:
            print_('    %s - %s' % (artist, album))
        elif album:
            print_('    %s' % album)
        else:
            print_('    (unknown album)')

    # Identify the album in question.
    if cur_artist != info['artist'] or \
            (cur_album != info['album'] and info['album'] != VARIOUS_ARTISTS):
        artist_l, artist_r = cur_artist or '', info['artist']
        album_l,  album_r  = cur_album  or '', info['album']
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
        print_("Tagging: %s - %s" % (info['artist'], info['album']))

    # Distance/similarity.
    print_('(Similarity: %s)' % dist_string(dist, color))

    # Tracks.
    for i, (item, track_data) in enumerate(zip(items, info['tracks'])):
        cur_track = str(item.track)
        new_track = str(i+1)
        cur_title = item.title
        new_title = track_data['title']
        
        # Possibly colorize changes.
        if color:
            cur_title, new_title = ui.colordiff(cur_title, new_title)
            if cur_track != new_track:
                cur_track = ui.colorize('red', cur_track)
                new_track = ui.colorize('red', new_track)
        
        if cur_title != new_title and cur_track != new_track:
            print_(" * %s (%s) -> %s (%s)" % (
                cur_title, cur_track, new_title, new_track
            ))
        elif cur_title != new_title:
            print_(" * %s -> %s" % (cur_title, new_title))
        elif cur_track != new_track:
            print_(" * %s (%s -> %s)" % (item.title, cur_track, new_track))

def show_item_change(item, info, dist, color):
    """Print out the change that would occur by tagging `item` with the
    metadata from `info`.
    """
    cur_artist, new_artist = item.artist, info['artist']
    cur_title, new_title = item.title, info['title']

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
    pair; for items, it is just an `info` dictionary.
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
            opts = ('Use as-is', 'Skip', 'Enter search', 'aBort')
        else:
            opts = ('Use as-is', 'as Tracks', 'Skip', 'Enter search', 'aBort')
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
                    print_('%i. %s - %s (%s)' % (i+1, info['artist'],
                           info['title'], dist_string(dist, color)))
            else:
                print_('Finding tags for album "%s - %s".' %
                       (cur_artist, cur_album))
                print_('Candidates:')
                for i, (dist, items, info) in enumerate(candidates):
                    print_('%i. %s - %s (%s)' % (i+1, info['artist'],
                        info['album'], dist_string(dist, color)))
                                            
            # Ask the user for a choice.
            if singleton:
                opts = ('Skip', 'Use as-is', 'Enter search', 'aBort')
            else:
                opts = ('Skip', 'Use as-is', 'as Tracks', 'Enter search',
                        'aBort')
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
                    'Enter search', 'aBort')
        else:
            opts = ('Apply', 'More candidates', 'Skip', 'Use as-is',
                    'as Tracks', 'Enter search', 'aBort')
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

def manual_search(singleton):
    """Input either an artist and album (for full albums) or artist and
    track name (for singletons) for manual search.
    """
    artist = raw_input('Artist: ').decode(sys.stdin.encoding)
    name = raw_input('Track: ' if singleton else 'Album: ') \
           .decode(sys.stdin.encoding)
    return artist.strip(), name.strip()

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
        else:
            # We have a candidate! Finish tagging. Here, choice is
            # an (info, items) pair as desired.
            assert not isinstance(choice, importer.action)
            return choice

def choose_item(task, config):
    """Ask the user for a choice about tagging a single item. Returns
    either an action constant or a track info dictionary.
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
            search_artist, search_title = manual_search(False)
            candidates, rec = autotag.tag_item(task.item, config.timid,
                                               search_artist, search_title)
        else:
            # Chose a candidate.
            assert not isinstance(choice, importer.action)
            return choice

# The import command.

def import_files(lib, paths, copy, write, autot, logpath, art, threaded,
                 color, delete, quiet, resume, quiet_fallback, singletons,
                 timid):
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
    import_files(lib, args, copy, write, autot, logpath, art, threaded,
                 color, delete, quiet, resume, quiet_fallback, singletons,
                 timid)
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
    list_items(lib, ui.make_query(args), opts.album, opts.path)
list_cmd.func = list_func
default_commands.append(list_cmd)


# remove: Remove items from library, delete files.

def remove_items(lib, query, album, delete=False):
    """Remove items matching query from lib. If album, then match and
    remove whole albums. If delete, also remove files from disk.
    """
    # Get the matching items.
    if album:
        albums = list(lib.albums(query))
        items = []
        for al in albums:
            items += al.items()
    else:
        items = list(lib.items(query))

    if not items:
        print_('No matching items found.')
        return

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
    remove_items(lib, ui.make_query(args), opts.album, opts.delete)
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
    show_stats(lib, ui.make_query(args))
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
