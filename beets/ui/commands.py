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

import os
import logging
from threading import Thread
from Queue import Queue

from beets import ui
from beets.ui import print_
from beets import autotag
from beets import library
from beets.mediafile import UnreadableFileError, FileTypeError
import beets.autotag.art

# Global logger.
log = logging.getLogger('beets')

# The list of default subcommands. This is populated with Subcommand
# objects that can be fed to a SubcommandsOptionParser.
default_commands = []


# import: Autotagger and importer.

DEFAULT_IMPORT_COPY  = True
DEFAULT_IMPORT_WRITE = True
DEFAULT_IMPORT_AUTOT = True
DEFAULT_IMPORT_ART   = True
DEFAULT_THREADED     = True

# Autotagger utilities and support.

def show_change(cur_artist, cur_album, items, info, dist):
    """Print out a representation of the changes that will be made if
    tags are changed from (cur_artist, cur_album, items) to info with
    distance dist.
    """
    if cur_artist != info['artist'] or cur_album != info['album']:
        print_("Correcting tags from:")
        print_('     %s - %s' % (cur_artist or '', cur_album or ''))
        print_("To:")
        print_('     %s - %s' % (info['artist'], info['album']))
    else:
        print_("Tagging: %s - %s" % (info['artist'], info['album']))
    print_('(Distance: %f)' % dist)
    for i, (item, track_data) in enumerate(zip(items, info['tracks'])):
        cur_track = item.track
        new_track = i+1
        if item.title != track_data['title'] and cur_track != new_track:
            print_(" * %s (%i) -> %s (%i)" % (
                item.title, cur_track, track_data['title'], new_track
            ))
        elif item.title != track_data['title']:
            print_(" * %s -> %s" % (item.title, track_data['title']))
        elif cur_track != new_track:
            print_(" * %s (%i -> %i)" % (item.title, cur_track, new_track))

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
            print_('Finding tags for "%s - %s".' % (cur_artist, cur_album))
            print_('Candidates:')
            for i, (dist, items, info) in enumerate(candidates):
                print_('%i. %s - %s (%f)' % (i+1, info['artist'],
                                             info['album'], dist))
                                            
            # Ask the user for a choice.
            sel = ui.input_options(
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
        sel = ui.input_options(
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
    if logfile:
        path = os.path.commonprefix([item.path for item in items])
        print >>logfile, status, os.path.dirname(path)

def choose_match(items, cur_artist, cur_album, candidates, rec):
    """Given an initial autotagging of items, go through an interactive
    dance with the user to ask for a choice of metadata. Returns an
    info dictionary, CHOICE_ASIS, or CHOICE_SKIP.
    """
    # Loop until we have a choice.
    while True:
        # Choose from candidates, if available.
        if candidates:
            info = choose_candidate(cur_artist, cur_album, candidates, rec)
        else:
            # Fallback: if either an error ocurred or no matches found.
            print_("No match found for:", os.path.dirname(items[0].path))
            sel = ui.input_options(
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
            return info
        elif info is CHOICE_MANUAL:
            # Try again with manual search terms.
            search_artist, search_album = manual_search()
        else:
            # Either ASIS or we have a candidate. Finish tagging.
            return info
        
        # Search for entered terms.
        try:
            _, _, candidates, rec = \
                    autotag.tag_album(items, search_artist, search_album)
        except autotag.AutotagError:
            candidates, rec = None, None

# Core autotagger generators and coroutines.

def read_albums(paths):
    """A generator yielding all the albums (as sets of Items) found in
    the user-specified list of paths.
    """
    # Make sure we have only directories.
    for path in paths:
        if not os.path.isdir(path):
            raise ui.UserError('not a directory: ' + path)
    
    for path in paths:
        for items in autotag.albums_in_dir(os.path.expanduser(path)):
            yield items

def initial_lookup():
    """A coroutine for performing the initial MusicBrainz lookup for an
    album. It accepts lists of Items and yields
    (cur_artist, cur_album, candidates, rec) tuples. If no match is found,
    all of the yielded parameters are None.
    """
    items = yield
    while True:
        try:
            cur_artist, cur_album, candidates, rec = autotag.tag_album(items)
        except autotag.AutotagError:
            cur_artist, cur_album, candidates, rec = None, None, None, None
        items = yield(cur_artist, cur_album, candidates, rec)

def user_query(lib, logfile=None):
    """A coroutine for interfacing with the user about the tagging
    process. lib is the Library to import into and logfile may be
    a file-like object for logging the import process. The coroutine
    accepts (items, cur_artist, cur_album, candidates, rec) tuples.
    items is a set of Items in the album to be tagged; the remaining
    parameters are the result of an initial lookup from MusicBrainz.
    The coroutine yields either a candidate info dict, CHOICE_ASIS, or
    None (indicating that the items should not be imported).
    """
    items, cur_artist, cur_album, candidates, rec = yield
    first = True
    while True:
        # Empty lines between albums.
        if not first:
            print_()
        first = False
        
        # Ask the user for a choice.
        info = choose_match(items, cur_artist, cur_album, candidates, rec)

        # The "give-up" options.
        if info is CHOICE_ASIS:
            tag_log(logfile, 'asis', items)
        elif info is CHOICE_SKIP:
            tag_log(logfile, 'skip', items)
            # Yield None, indicating that the pipeline should not
            # progress.
            items, cur_artist, cur_album, candidates, rec = yield None
            continue

        # Ensure that we don't have the album already.
        if info is not CHOICE_ASIS or cur_artist is not None:
            if info is CHOICE_ASIS:
                artist = cur_artist
                album = cur_album
            else:
                artist = info['artist']
                album = info['album']
            q = library.AndQuery((library.MatchQuery('artist', artist),
                                  library.MatchQuery('album',  album)))
            count, _ = q.count(lib)
            if count >= 1:
                print_("This album (%s - %s) is already in the library!" %
                       (artist, album))
                items, cur_artist, cur_album, candidates, rec = yield None
                continue
        
        # Yield the result and get the next chunk of work.
        items, cur_artist, cur_album, candidates, rec = yield info
        
def apply_choices(lib, copy, write, art):
    """A coroutine for applying changes to albums during the autotag
    process. The parameters to the generator control the behavior of
    the import. The coroutine accepts (items, info) pairs and yields
    nothing. items the set of Items to import; info is either a
    candidate info dictionary or CHOICE_ASIS.
    """
    while True:    
        # Get next chunk of work.
        items, info = yield
        
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
        albuminfo = lib.add_album(items)

        # Get album art if requested.
        if art and info is not CHOICE_ASIS:
            artpath = beets.autotag.art.art_for_album(info)
            if artpath:
                albuminfo.set_art(artpath)

        # Write the database after each album.
        lib.save()

# Importer main functions.

def autotag_sequential(lib, paths, copy, write, logfile, art):
    """Autotags and imports the albums in the directory in a single-
    threaded manner. lib is the Library to import into. If copy, then
    items are copied into the destination directory. If write, then
    new metadata is written back to the files' tags. If logfile is
    provided, then a log message will be added there if the album is
    untaggable. If art, then attempt to download cover art for the
    album.
    """
    # Set up the various coroutines.
    init_lookup_coro = initial_lookup()
    init_lookup_coro.next()
    user_coro = user_query(lib, logfile)
    user_coro.next()
    apply_coro = apply_choices(lib, copy, write, art)
    apply_coro.next()
    
    # Crawl albums and send them through the pipeline one at a time.
    for items in read_albums(paths):
        cur_artist, cur_album, candidates, rec = \
            init_lookup_coro.send(items)
        info = user_coro.send((items, cur_artist, cur_album, candidates, rec))
        if info is None:
            # User-query coroutine yeilds None when the album
            # should be skipped. Bypass the rest of the pipeline.
            continue
        apply_coro.send((items, info))


def _reopen_lib(lib):
    if isinstance(lib, library.Library):
        return library.Library(
            lib.path,
            lib.directory,
            lib.path_format,
            lib.art_filename,
        )
    else:
        return lib

CHANNEL_POISON = 'CHANNEL_POISION'
class ReadAlbumsThread(Thread):
    def __init__(self, paths, out_queue):
        super(ReadAlbumsThread, self).__init__()
        self.gen = read_albums(paths)
        self.out_queue = out_queue
    def run(self):
        for items in self.gen:
            self.out_queue.put(items)
        self.out_queue.put(CHANNEL_POISON)
class InitialLookupThread(Thread):
    def __init__(self, in_queue, out_queue):
        super(InitialLookupThread, self).__init__()
        self.coro = initial_lookup()
        self.coro.next()
        self.in_queue, self.out_queue = in_queue, out_queue
    def run(self):
        while True:
            items = self.in_queue.get()
            if items is CHANNEL_POISON:
                break
            cur_artist, cur_album, candidates, rec = self.coro.send(items)
            self.out_queue.put((items, cur_artist, cur_album,
                                candidates, rec))
        self.out_queue.put(CHANNEL_POISON)
class UIThread(Thread):
    def __init__(self, lib, logfile, in_queue, out_queue):
        super(UIThread, self).__init__()
        self.lib, self.logfile = lib, logfile
        self.in_queue, self.out_queue = in_queue, out_queue
    def run(self):
        self.coro = user_query(_reopen_lib(self.lib), self.logfile)
        self.coro.next()
        while True:
            msg = self.in_queue.get()
            if msg is CHANNEL_POISON:
                break
            items = msg[0]
            info = self.coro.send(msg)
            if info is None:
                # Skip this album.
                continue
            self.out_queue.put((items, info))
        self.out_queue.put(CHANNEL_POISON)
class ApplyThread(Thread):
    def __init__(self, lib, copy, write, art, in_queue):
        super(ApplyThread, self).__init__()
        self.lib, self.copy, self.write, self.art = lib, copy, write, art
        self.in_queue = in_queue
    def run(self):    
        self.coro = apply_choices(_reopen_lib(self.lib), self.copy,
                                  self.write, self.art)
        self.coro.next()
        while True:
            msg = self.in_queue.get()
            if msg is CHANNEL_POISON:
                break
            self.coro.send(msg)
CHANNEL_SIZE = 10
def autotag_threaded(lib, paths, copy, write, logfile, art):
    """Autotags and imports albums using multiple threads. A drop-in
    replacement for autotag_sequential.
    """
    q_read_to_lookup = Queue(CHANNEL_SIZE)
    q_lookup_to_user = Queue(CHANNEL_SIZE)
    q_user_to_apply = Queue(CHANNEL_SIZE)
    
    reader_thread = ReadAlbumsThread(paths, q_read_to_lookup)
    lookup_thread = InitialLookupThread(q_read_to_lookup, q_lookup_to_user)
    ui_thread = UIThread(lib, logfile, q_lookup_to_user, q_user_to_apply)
    apply_thread = ApplyThread(lib, copy, write, art, q_user_to_apply)
    
    reader_thread.start()
    lookup_thread.start()
    ui_thread.start()
    apply_thread.start()
    
    reader_thread.join()
    lookup_thread.join()
    ui_thread.join()
    apply_thread.join()

def simple_import(lib, paths, copy):
    """Imports all the albums found in the paths without attempting to
    autotag them. The behavior is similar to an import in which the
    user always chooses the "as-is" option.
    """
    for items in read_albums(paths):
        if copy:
            for item in items:
                item.move(lib, True)
        lib.add_album(items)
        lib.save()

# The import command.

def import_files(lib, paths, copy, write, autot, logpath, art, threaded):
    """Import the files in the given list of paths, tagging each leaf
    directory as an album. If copy, then the files are copied into
    the library folder. If write, then new metadata is written to the
    files themselves. If not autot, then just import the files
    without attempting to tag. If logpath is provided, then untaggable
    albums will be logged there. If art, then attempt to download
    cover art for each album.
    """
    # Open the log.
    if logpath:
        logfile = open(logpath, 'w')
    else:
        logfile = None
    
    # Perform the import.
    if autot:
        if threaded:
            autotag_threaded(lib, paths, copy, write, logfile, art)
        else:
            autotag_sequential(lib, paths, copy, write, logfile, art)
    else:
        just_import(lib, paths, copy)
    
    # If we were logging, close the file.
    if logfile:
        logfile.close()

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
import_cmd.parser.add_option('-R', '--noart', action='store_false',
    dest='art', help="don't album art (opposite of -r)")
import_cmd.parser.add_option('-l', '--log', dest='logpath',
    help='file to log untaggable albums for later review')
def import_func(lib, config, opts, args):
    copy  = opts.copy  if opts.copy  is not None else \
        ui.config_val(config, 'beets', 'import_copy',
            DEFAULT_IMPORT_COPY, bool)
    write = opts.write if opts.write is not None else \
        ui.config_val(config, 'beets', 'import_write',
            DEFAULT_IMPORT_WRITE, bool)
    autot = opts.autotag if opts.autotag is not None else DEFAULT_IMPORT_AUTOT
    art = opts.art if opts.art is not None else \
        ui.config_val(config, 'beets', 'import_art',
            DEFAULT_IMPORT_ART, bool)
    threaded = ui.config_val(config, 'beets', 'threaded',
            DEFAULT_THREADED, bool)
    import_files(lib, args, copy, write, autot, opts.logpath, art, threaded)
import_cmd.func = import_func
default_commands.append(import_cmd)


# list: Query and show library contents.

def list_items(lib, query, album):
    """Print out items in lib matching query. If album, then search for
    albums instead of single items.
    """
    if album:
        for album in lib.albums(query=query):
            print_(album.artist + ' - ' + album.album)
    else:
        for item in lib.items(query=query):
            print_(item.artist + ' - ' + item.album + ' - ' + item.title)

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
