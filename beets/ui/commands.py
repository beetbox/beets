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

"""This module provides the default commands for beets' command-line
interface.
"""
from __future__ import with_statement # Python 2.5
import os
import logging
import pickle
import sys

from beets import ui
from beets.ui import print_
from beets import autotag
from beets import library
from beets.mediafile import UnreadableFileError, FileTypeError
import beets.autotag.art
from beets.ui import pipeline
from beets import plugins

# Global logger.
log = logging.getLogger('beets')

# The list of default subcommands. This is populated with Subcommand
# objects that can be fed to a SubcommandsOptionParser.
default_commands = []


# import: Autotagger and importer.

DEFAULT_IMPORT_COPY     = True
DEFAULT_IMPORT_WRITE    = True
DEFAULT_IMPORT_DELETE   = False
DEFAULT_IMPORT_AUTOT    = True
DEFAULT_IMPORT_ART      = True
DEFAULT_IMPORT_QUIET    = False
DEFAULT_IMPORT_PROGRESS = True
DEFAULT_THREADED        = True
DEFAULT_COLOR           = True

class ImportAbort(Exception):
    """Raised when the user aborts the tagging operation.
    """
    pass

# Autotagger utilities and support.

def dist_string(dist, color):
    """Formats a distance (a float) as a string. The string is
    colorized if color is True.
    """
    out = str(dist)
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
    if cur_artist != info['artist'] or cur_album != info['album']:
        artist_l, artist_r = cur_artist or '', info['artist']
        album_l,  album_r  = cur_album  or '', info['album']
        if color:
            artist_l, artist_r = ui.colordiff(artist_l, artist_r)
            album_l, album_r   = ui.colordiff(album_l, album_r)
        print_("Correcting tags from:")
        print_('     %s - %s' % (artist_l, album_l))
        print_("To:")
        print_('     %s - %s' % (artist_r, album_r))
    else:
        print_("Tagging: %s - %s" % (info['artist'], info['album']))
    print_('(Distance: %s)' % dist_string(dist, color))
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

CHOICE_SKIP = 'CHOICE_SKIP'
CHOICE_ASIS = 'CHOICE_ASIS'
CHOICE_MANUAL = 'CHOICE_MANUAL'
def choose_candidate(cur_artist, cur_album, candidates, rec, color=True):
    """Given current metadata and a sorted list of
    (distance, candidate) pairs, ask the user for a selection
    of which candidate to use. Returns a pair (candidate, ordered)
    consisting of the the selected candidate and the associated track
    ordering. If user chooses to skip, use as-is, or search manually,
    returns CHOICE_SKIP, CHOICE_ASIS, or CHOICE_MANUAL instead of a
    tuple.
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
            print_('Finding tags for "%s - %s".' % (cur_artist, cur_album))
            print_('Candidates:')
            for i, (dist, items, info) in enumerate(candidates):
                print_('%i. %s - %s (%s)' % (i+1, info['artist'],
                    info['album'], dist_string(dist, color)))
                                            
            # Ask the user for a choice.
            sel = ui.input_options(
                '# selection (default 1), Skip, Use as-is, '
                'Enter search, or aBort?',
                ('s', 'u', 'e', 'b'), '1',
                'Enter a numerical selection, S, U, E, or B:',
                (1, len(candidates))
            )
            if sel == 's':
                return CHOICE_SKIP
            elif sel == 'u':
                return CHOICE_ASIS
            elif sel == 'e':
                return CHOICE_MANUAL
            elif sel == 'b':
                raise ImportAbort()
            else: # Numerical selection.
                dist, items, info = candidates[sel-1]
        bypass_candidates = False
    
        # Show what we're about to do.
        show_change(cur_artist, cur_album, items, info, dist, color)
    
        # Exact match => tag automatically.
        if rec == autotag.RECOMMEND_STRONG:
            return info, items
        
        # Ask for confirmation.
        sel = ui.input_options(
            '[A]pply, More candidates, Skip, Use as-is, '
            'Enter search, or aBort?',
            ('a', 'm', 's', 'u', 'e', 'b'), 'a',
            'Enter A, M, S, U, E, or B:'
        )
        if sel == 'a':
            return info, items
        elif sel == 'm':
            pass
        elif sel == 's':
            return CHOICE_SKIP
        elif sel == 'u':
            return CHOICE_ASIS
        elif sel == 'e':
            return CHOICE_MANUAL
        elif sel == 'b':
            raise ImportAbort()

def manual_search():
    """Input an artist and album for manual search."""
    artist = raw_input('Artist: ').decode(sys.stdin.encoding)
    album = raw_input('Album: ').decode(sys.stdin.encoding)
    return artist.strip(), album.strip()

def tag_log(logfile, status, path):
    """Log a message about a given album to logfile. The status should
    reflect the reason the album couldn't be tagged.
    """
    if logfile:
        print >>logfile, '%s %s' % (status, path)

def choose_match(path, items, cur_artist, cur_album, candidates,
                 rec, color=True, quiet=False):
    """Given an initial autotagging of items, go through an interactive
    dance with the user to ask for a choice of metadata. Returns an
    (info, items) pair, CHOICE_ASIS, or CHOICE_SKIP.
    """
    if quiet:
        # No input; just make a decision.
        if rec == autotag.RECOMMEND_STRONG:
            dist, items, info = candidates[0]
            show_change(cur_artist, cur_album, items, info, dist, color)
            return info, items
        else:
            print_('Skipping.')
            return CHOICE_SKIP

    # Loop until we have a choice.
    while True:
        # Choose from candidates, if available.
        if candidates:
            choice = choose_candidate(cur_artist, cur_album, candidates, rec,
                                      color)
        else:
            # Fallback: if either an error ocurred or no matches found.
            print_("No match found.")
            sel = ui.input_options(
                "[U]se as-is, Skip, Enter manual search, or aBort?",
                ('u', 's', 'e', 'b'), 'u',
                'Enter U, S, E, or B:'
            )
            if sel == 'u':
                choice = CHOICE_ASIS
            elif sel == 'e':
                choice = CHOICE_MANUAL
            elif sel == 's':
                choice = CHOICE_SKIP
            elif sel == 'b':
                raise ImportAbort()
    
        # Choose which tags to use.
        if choice in (CHOICE_SKIP, CHOICE_ASIS):
            # Pass selection to main control flow.
            return choice
        elif choice is CHOICE_MANUAL:
            # Try again with manual search terms.
            search_artist, search_album = manual_search()
        else:
            # We have a candidate! Finish tagging. Here, choice is
            # an (info, items) pair as desired.
            return choice
        
        # Search for entered terms.
        try:
            _, _, candidates, rec = \
                    autotag.tag_album(items, search_artist, search_album)
        except autotag.AutotagError:
            candidates, rec = None, None

def _reopen_lib(lib):
    """Because of limitations in SQLite, a given Library is bound to
    the thread in which it was created. This function reopens Library
    objects so that they can be used from separate threads.
    """
    if isinstance(lib, library.Library):
        return library.Library(
            lib.path,
            lib.directory,
            lib.path_formats,
            lib.art_filename,
        )
    else:
        return lib

# Utilities for reading and writing the beets progress file, which
# allows long tagging tasks to be resumed when they pause (or crash).
PROGRESS_KEY = 'tagprogress'
def progress_set(toppath, path):
    """Record that tagging for the given `toppath` was successful up to
    `path`. If path is None, then clear the progress value (indicating
    that the tagging completed).
    """
    try:
        with open(ui.STATE_FILE) as f:
            state = pickle.load(f)
    except IOError:
        state = {PROGRESS_KEY: {}}

    if path is None:
        # Remove progress from file.
        if toppath in state[PROGRESS_KEY]:
            del state[PROGRESS_KEY][toppath]
    else:
        state[PROGRESS_KEY][toppath] = path

    with open(ui.STATE_FILE, 'w') as f:
        pickle.dump(state, f)
def progress_get(toppath):
    """Get the last successfully tagged subpath of toppath. If toppath
    has no progress information, returns None.
    """
    try:
        with open(ui.STATE_FILE) as f:
            state = pickle.load(f)
    except IOError:
        return None
    return state[PROGRESS_KEY].get(toppath)

# Core autotagger pipeline stages.

# This sentinel is passed along as the "path" when a directory has finished
# tagging.
DONE_SENTINEL = '__IMPORT_DONE_SENTINEL__'

def read_albums(paths, progress, resume):
    """A generator yielding all the albums (as sets of Items) found in
    the user-specified list of paths. `progress` specifies whether
    the resuming feature should be used. `resume` may be None or a
    boolean. If it is False, then progress is disabled (overriding
    `progress`); if it is True, then progress is enabled and the import
    is resumed if possible; if it is None, then the user is prompted
    (the default behavior).
    """
    # Use absolute paths.
    paths = [library._normpath(path) for path in paths]

    # Check the user-specified directories.
    for path in paths:
        if not os.path.isdir(library._syspath(path)):
            raise ui.UserError('not a directory: ' + path)

    # Look for saved progress.
    if progress or resume is not None:
        resume_dirs = {}
        for path in paths:
            resume_dir = progress_get(path)
            if resume_dir:

                # Either accept immediately or prompt for input to decide.
                if resume is not None:
                    do_resume = resume
                    if do_resume:
                        ui.print_('Resuming interrupted import of %s' % path)
                        ui.print_()
                else:
                    do_resume = ui.input_yn("Import of the directory:\n%s"
                                            "\nwas interrupted. Resume (Y/n)?" %
                                            path)
                    ui.print_()

                if do_resume:
                    resume_dirs[path] = resume_dir
                else:
                    # Clear progress; we're starting from the top.
                    progress_set(path, None)
    
    for toppath in paths:
        # Produce each path.
        if progress:
            resume_dir = resume_dirs.get(toppath)
        for path, items in autotag.albums_in_dir(os.path.expanduser(toppath)):
            if progress and resume_dir:
                # We're fast-forwarding to resume a previous tagging.
                if path == resume_dir:
                    # We've hit the last good path! Turn off the
                    # fast-forwarding.
                    resume_dir = None
                continue

            yield toppath, path, items

        # Indicate the directory is finished.
        yield toppath, DONE_SENTINEL, None

def initial_lookup():
    """A coroutine for performing the initial MusicBrainz lookup for an
    album. It accepts lists of Items and yields
    (items, cur_artist, cur_album, candidates, rec) tuples. If no match
    is found, all of the yielded parameters (except items) are None.
    """
    toppath, path, items = yield
    while True:
        if path is DONE_SENTINEL:
            cur_artist, cur_album, candidates, rec = None, None, None, None
        else:
            try:
                cur_artist, cur_album, candidates, rec = \
                        autotag.tag_album(items)
            except autotag.AutotagError:
                cur_artist, cur_album, candidates, rec = \
                        None, None, None, None
        toppath, path, items = yield toppath, path, items, cur_artist, \
                                     cur_album, candidates, rec

def user_query(lib, logfile=None, color=True, quiet=False):
    """A coroutine for interfacing with the user about the tagging
    process. lib is the Library to import into and logfile may be
    a file-like object for logging the import process. The coroutine
    accepts (items, cur_artist, cur_album, candidates, rec) tuples.
    items is a set of Items in the album to be tagged; the remaining
    parameters are the result of an initial lookup from MusicBrainz.
    The coroutine yields (toppath, path, items, info) pairs where info
    is either a candidate info dict, CHOICE_ASIS, or None (indicating
    that the album should not be tagged) and items are the constituent
    Item objects, ordered in the case of successful tagging.
    """
    lib = _reopen_lib(lib)
    first = True
    out = None
    while True:
        toppath, path, items, cur_artist, cur_album, candidates, rec = yield out

        if path is DONE_SENTINEL:
            out = toppath, path, None, None
            continue
        
        # Empty lines between albums.
        if not first:
            print_()
        first = False
        # Show current album path.
        print_(path)
        
        # Ask the user for a choice.
        choice = choose_match(path, items, cur_artist, cur_album, candidates,
                              rec, color, quiet)

        # The "give-up" options.
        if choice is CHOICE_ASIS:
            tag_log(logfile, 'asis', path)
            info = CHOICE_ASIS
        elif choice is CHOICE_SKIP:
            tag_log(logfile, 'skip', path)
            # Yield None, indicating that the pipeline should not
            # progress.
            out = toppath, path, items, None
            continue
        else:
            # We have a real candidate. Get the info dictionary and
            # replace the items list with an ordered list.
            info, items = choice

        # Ensure that we don't have the album already.
        if choice is not CHOICE_ASIS or cur_artist is not None:
            if choice is CHOICE_ASIS:
                artist = cur_artist
                album = cur_album
            else:
                artist = info['artist']
                album = info['album']
            q = library.AndQuery((library.MatchQuery('artist', artist),
                                  library.MatchQuery('album',  album)))
            count, _ = q.count(lib)
            if count >= 1:
                tag_log(logfile, 'duplicate', path)
                print_("This album (%s - %s) is already in the library!" %
                       (artist, album))
                out = toppath, path, items, None
                continue
        
        # Yield the result and get the next chunk of work.
        out = toppath, path, items, info
        
def apply_choices(lib, copy, write, art, delete, progress):
    """A coroutine for applying changes to albums during the autotag
    process. The parameters to the generator control the behavior of
    the import. The coroutine accepts (items, info) pairs and yields
    nothing. items the set of Items to import; info is either a
    candidate info dictionary or CHOICE_ASIS.
    """
    lib = _reopen_lib(lib)
    while True:    
        # Get next chunk of work.
        toppath, path, items, info = yield

        # Check for "path finished" message.
        if path is DONE_SENTINEL:
            if progress:
                # Mark path as complete.
                progress_set(toppath, None)
            continue
        
        # Only process the items if info is not None (indicating a
        # skip).
        if info is not None:

            # Change metadata, move, and copy.
            if info is not CHOICE_ASIS:
                autotag.apply_metadata(items, info)
            if copy and delete:
                old_paths = [os.path.realpath(item.path) for item in items]
            for item in items:
                if copy:
                    item.move(lib, True)
                if write and info is not CHOICE_ASIS:
                    item.write()

            # Add items to library. We consolidate this at the end to avoid
            # locking while we do the copying and tag updates.
            albuminfo = lib.add_album(items, infer_aa = (info is CHOICE_ASIS))

            # Get album art if requested.
            if art and info is not CHOICE_ASIS:
                artpath = beets.autotag.art.art_for_album(info)
                if artpath:
                    albuminfo.set_art(artpath)
            
            # Write the database after each album.
            lib.save()

            # Finally, delete old files.
            if copy and delete:
                new_paths = [os.path.realpath(item.path) for item in items]
                for old_path in old_paths:
                    # Only delete files that were actually moved.
                    if old_path not in new_paths:
                        os.remove(library._syspath(old_path))
                        os.remove(library._syspath(old_path))

        # Update progress.
        if progress:
            progress_set(toppath, path)

# Non-autotagged import (always sequential).

def simple_import(lib, paths, copy, delete, progress, resume):
    """Add files from the paths to the library without changing any
    tags.
    """
    for toppath, path, items in read_albums(paths, progress, resume):
        if items is None:
            continue

        if copy:
            if delete:
                old_paths = [os.path.realpath(item.path) for item in items]
            for item in items:
                item.move(lib, True)

        album = lib.add_album(items, True)
        lib.save()            
        if progress:
            progress_set(toppath, path)

        if copy and delete:
            new_paths = [os.path.realpath(item.path) for item in items]
            for old_path in old_paths:
                # Only delete files that were actually moved.
                if old_path not in new_paths:
                    os.remove(library._syspath(old_path))

        log.info('added album: %s - %s' % (album.albumartist, album.album))

# The import command.

def import_files(lib, paths, copy, write, autot, logpath, art, threaded,
                 color, delete, quiet, progress, resume):
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
    it is not confident about. If progress, then state is saved in
    case an import is interrupted.
    """
    # Open the log.
    if logpath:
        logfile = open(logpath, 'w')
    else:
        logfile = None
    
    # Perform the import.
    if autot:
        # Autotag. Set up the pipeline.
        pl = pipeline.Pipeline([
            read_albums(paths, progress and not quiet, resume),
            initial_lookup(),
            user_query(lib, logfile, color, quiet),
            apply_choices(lib, copy, write, art, delete, progress),
        ])

        # Run the pipeline.
        try:
            if threaded:
                pl.run_parallel()
            else:
                pl.run_sequential()
        except ImportAbort:
            # User aborted operation. Silently stop.
            pass
    else:
        # Simple import without autotagging. Always sequential.
        simple_import(lib, paths, copy, delete, progress, resume)
    
    # If we were logging, close the file.
    if logfile:
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
    dest='write', help="don't write metadata (opposite of -s)")
import_cmd.parser.add_option('-a', '--autotag', action='store_true',
    dest='autotag', help="infer tags for imported files (default)")
import_cmd.parser.add_option('-A', '--noautotag', action='store_false',
    dest='autotag',
    help="don't infer tags for imported files (opposite of -a)")
import_cmd.parser.add_option('-r', '--art', action='store_true',
    default=None, help="try to download album art")
import_cmd.parser.add_option('-p', '--resume', action='store_true',
    default=None, help="resume importing if interrupted")
import_cmd.parser.add_option('-P', '--noresume', action='store_false',
    dest='resume', help="do not try to resume importing")
import_cmd.parser.add_option('-R', '--noart', action='store_false',
    dest='art', help="don't album art (opposite of -r)")
import_cmd.parser.add_option('-q', '--quiet', action='store_true',
    dest='quiet', help="never prompt for input: skip albums instead")
import_cmd.parser.add_option('-l', '--log', dest='logpath',
    help='file to log untaggable albums for later review')
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
    progress = ui.config_val(config, 'beets', 'import_progress',
            DEFAULT_IMPORT_PROGRESS, bool)
    threaded = ui.config_val(config, 'beets', 'threaded',
            DEFAULT_THREADED, bool)
    color = ui.config_val(config, 'beets', 'color', DEFAULT_COLOR, bool)
    resume = opts.resume # May be None.
    quiet = opts.quiet if opts.quiet is not None else DEFAULT_IMPORT_QUIET
    import_files(lib, args, copy, write, autot, opts.logpath, art, threaded,
                 color, delete, quiet, progress, resume)
import_cmd.func = import_func
default_commands.append(import_cmd)


# list: Query and show library contents.

def list_items(lib, query, album):
    """Print out items in lib matching query. If album, then search for
    albums instead of single items.
    """
    if album:
        for album in lib.albums(query=query):
            print_(album.albumartist + u' - ' + album.album)
    else:
        for item in lib.items(query=query):
            print_(item.artist + u' - ' + item.album + u' - ' + item.title)

list_cmd = ui.Subcommand('list', help='query the library', aliases=('ls',))
list_cmd.parser.add_option('-a', '--album', action='store_true',
    help='show matching albums instead of tracks')
def list_func(lib, config, opts, args):
    list_items(lib, ui.make_query(args), opts.album)
list_cmd.func = list_func
default_commands.append(list_cmd)


# remove: Remove items from library, delete files.

def remove_items(lib, query, album, delete=False):
    """Remove items matching query from lib. If album, then match and
    remove whole albums. If delete, also remove files from disk.
    """
    # Get the matching items.
    if album:
        albums = list(lib.albums(query=query))
        items = []
        for al in albums:
            items += al.items()
    else:
        items = list(lib.items(query=query))

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
version_cmd = ui.Subcommand('version',
    help='output version information')
version_cmd.func = show_version
default_commands.append(version_cmd)
