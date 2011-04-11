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

"""Provides the basic, interface-agnostic workflow for importing and
autotagging music files.
"""
from __future__ import with_statement # Python 2.5
import os
import logging
import pickle

from beets import autotag
from beets import library
import beets.autotag.art
from beets import plugins
from beets.util import pipeline
from beets.util import syspath, normpath

CHOICE_SKIP = 'CHOICE_SKIP'
CHOICE_ASIS = 'CHOICE_ASIS'
CHOICE_TRACKS = 'CHOICE_TRACKS'
CHOICE_MANUAL = 'CHOICE_MANUAL'
CHOICE_ALBUM = 'CHOICE_ALBUM'

QUEUE_SIZE = 128
STATE_FILE = os.path.expanduser('~/.beetsstate')

# Global logger.
log = logging.getLogger('beets')

class ImportAbort(Exception):
    """Raised when the user aborts the tagging operation.
    """
    pass


# Utilities.

def tag_log(logfile, status, path):
    """Log a message about a given album to logfile. The status should
    reflect the reason the album couldn't be tagged.
    """
    if logfile:
        print >>logfile, '%s %s' % (status, path)

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

def _duplicate_check(lib, artist, album):
    """Check whether the match already exists in the library."""
    if artist is None:
        # As-is import with no artist. Skip check.
        return False

    for album_cand in lib.albums(artist):
        if album_cand.album == album:
            return True
    return False

# Utilities for reading and writing the beets progress file, which
# allows long tagging tasks to be resumed when they pause (or crash).
PROGRESS_KEY = 'tagprogress'
def progress_set(toppath, path):
    """Record that tagging for the given `toppath` was successful up to
    `path`. If path is None, then clear the progress value (indicating
    that the tagging completed).
    """
    try:
        with open(STATE_FILE) as f:
            state = pickle.load(f)
    except IOError:
        state = {PROGRESS_KEY: {}}

    if path is None:
        # Remove progress from file.
        if toppath in state[PROGRESS_KEY]:
            del state[PROGRESS_KEY][toppath]
    else:
        state[PROGRESS_KEY][toppath] = path

    with open(STATE_FILE, 'w') as f:
        pickle.dump(state, f)
def progress_get(toppath):
    """Get the last successfully tagged subpath of toppath. If toppath
    has no progress information, returns None.
    """
    try:
        with open(STATE_FILE) as f:
            state = pickle.load(f)
    except IOError:
        return None
    return state[PROGRESS_KEY].get(toppath)


# The configuration structure.

class ImportConfig(object):
    """Contains all the settings used during an import session. Should
    be used in a "write-once" way -- everything is set up initially and
    then never touched again.
    """
    _fields = ['lib', 'paths', 'resume', 'logfile', 'color', 'quiet',
               'quiet_fallback', 'copy', 'write', 'art', 'delete',
               'choose_match_func', 'should_resume_func', 'threaded', 'autot']
    def __init__(self, **kwargs):
        for slot in self._fields:
            setattr(self, slot, kwargs[slot])


# The importer task class.

class ImportTask(object):
    """Represents a single directory to be imported along with its
    intermediate state.
    """
    def __init__(self, toppath, path=None, items=None):
        self.toppath = toppath
        self.path = path
        self.items = items
        self.sentinel = False

    @classmethod
    def done_sentinel(cls, toppath):
        """Create an ImportTask that indicates the end of a top-level
        directory import.
        """
        obj = cls(toppath)
        obj.sentinel = True
        return obj

    def set_match(self, cur_artist, cur_album, candidates, rec):
        """Sets the candidates matched by the autotag.tag_album method.
        """
        assert not self.sentinel
        self.cur_artist = cur_artist
        self.cur_album = cur_album
        self.candidates = candidates
        self.rec = rec

    def set_null_match(self):
        """Set the candidate to indicate no match was found."""
        self.set_match(None, None, None, None)

    def set_choice(self, choice):
        """Given either an (info, items) tuple or a CHOICE_ constant,
        indicates that an action has been selected by the user (or
        automatically).
        """
        assert not self.sentinel
        assert choice != CHOICE_MANUAL # Not part of the task structure.
        assert choice != CHOICE_ALBUM # Only used internally.
        if choice in (CHOICE_SKIP, CHOICE_ASIS, CHOICE_TRACKS):
            self.choice_flag = choice
            self.info = None
            if choice == CHOICE_SKIP:
                self.items = None # Items no longer needed.
        else:
            info, items = choice
            self.items = items # Reordered items list.
            self.info = info
            self.choice_flag = CHOICE_ALBUM # Implicit choice.

    def save_progress(self):
        """Updates the progress state to indicate that this album has
        finished.
        """
        if self.sentinel:
            progress_set(self.toppath, None)
        else:
            progress_set(self.toppath, self.path)

    def should_create_album(self):
        """Should an album structure be created for these items?"""
        if self.choice_flag in (CHOICE_ALBUM, CHOICE_ASIS):
            return True
        elif self.choice_flag in (CHOICE_TRACKS, CHOICE_SKIP):
            return False
        else:
            assert False
    def should_write_tags(self):
        """Should new info be written to the files' metadata?"""
        if self.choice_flag == CHOICE_ALBUM:
            return True
        elif self.choice_flag in (CHOICE_ASIS, CHOICE_TRACKS, CHOICE_SKIP):
            return False
        else:
            assert False
    def should_fetch_art(self):
        """Should album art be downloaded for this album?"""
        return self.should_write_tags()
    def should_infer_aa(self):
        """When creating an album structure, should the album artist
        field be inferred from the plurality of track artists?
        """
        assert self.should_create_album()
        if self.choice_flag == CHOICE_ALBUM:
            # Album artist comes from the info dictionary.
            return False
        elif self.choice_flag == CHOICE_ASIS:
            # As-is imports likely don't have an album artist.
            return True
        else:
            assert False


# Core autotagger pipeline stages.

def read_albums(config):
    """A generator yielding all the albums (as ImportTask objects) found
    in the user-specified list of paths. `progress` specifies whether
    the resuming feature should be used. It may be True (resume if
    possible), False (never resume), or None (ask).
    """
    # Use absolute paths.
    paths = [normpath(path) for path in config.paths]

    # Look for saved progress.
    progress = config.resume is not False
    if progress:
        resume_dirs = {}
        for path in paths:
            resume_dir = progress_get(path)
            if resume_dir:

                # Either accept immediately or prompt for input to decide.
                if config.resume:
                    do_resume = True
                    log.warn('Resuming interrupted import of %s' % path)
                else:
                    do_resume = config.should_resume_func(config, path)

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

            yield ImportTask(toppath, path, items)

        # Indicate the directory is finished.
        yield ImportTask.done_sentinel(toppath)

def initial_lookup(config):
    """A coroutine for performing the initial MusicBrainz lookup for an
    album. It accepts lists of Items and yields
    (items, cur_artist, cur_album, candidates, rec) tuples. If no match
    is found, all of the yielded parameters (except items) are None.
    """
    task = yield
    log.debug('Looking up: %s' % task.path)
    while True:
        if task.sentinel:
            task = yield task
            continue

        try:
            task.set_match(*autotag.tag_album(task.items))
        except autotag.AutotagError:
            task.set_null_match()
        task = yield task

def user_query(config):
    """A coroutine for interfacing with the user about the tagging
    process. lib is the Library to import into and logfile may be
    a file-like object for logging the import process. The coroutine
    accepts and yields ImportTask objects.
    """
    lib = _reopen_lib(config.lib)
    task = None
    while True:
        task = yield task
        if task.sentinel:
            continue
        
        # Ask the user for a choice.
        choice = config.choose_match_func(task, config)
        task.set_choice(choice)

        # Log certain choices.
        if choice is CHOICE_ASIS:
            tag_log(config.logfile, 'asis', task.path)
        elif choice is CHOICE_SKIP:
            tag_log(config.logfile, 'skip', task.path)

        # Check for duplicates if we have a match.
        if choice == CHOICE_ASIS or isinstance(choice, tuple):
            if choice == CHOICE_ASIS:
                artist = task.cur_artist
                album = task.cur_album
            else:
                artist = task.info['artist']
                album = task.info['album']
            if _duplicate_check(lib, artist, album):
                tag_log(config.logfile, 'duplicate', task.path)
                log.warn("This album is already in the library!")
                task.set_choice(CHOICE_SKIP)
        
def apply_choices(config):
    """A coroutine for applying changes to albums during the autotag
    process. The parameters to the generator control the behavior of
    the import. The coroutine accepts ImportTask objects and yields
    nothing.
    """
    lib = _reopen_lib(config.lib)
    while True:    
        task = yield
        # Don't do anything if we're skipping the album or we're done.
        if task.choice_flag == CHOICE_SKIP or task.sentinel:
            if config.resume is not False:
                task.save_progress()
            continue

        # Change metadata, move, and copy.
        if task.should_write_tags():
            autotag.apply_metadata(task.items, task.info)
        if config.copy and config.delete:
            old_paths = [os.path.realpath(item.path)
                         for item in task.items]
        for item in task.items:
            if config.copy:
                item.move(lib, True, task.should_create_album())
            if config.write and task.should_write_tags():
                item.write()

        # Add items to library. We consolidate this at the end to avoid
        # locking while we do the copying and tag updates.
        if task.should_create_album():
            # Add an album.
            albuminfo = lib.add_album(task.items,
                                      infer_aa = task.should_infer_aa())
        else:
            # Add tracks.
            for item in task.items:
                lib.add(item)

        # Get album art if requested.
        if config.art and task.should_fetch_art():
            artpath = beets.autotag.art.art_for_album(task.info)
            if artpath:
                albuminfo.set_art(artpath)
        
        # Write the database after each album.
        lib.save()

        # Announce that we've added an album.
        if task.should_create_album():
            plugins.send('album_imported', album=albuminfo)
        else:
            for item in task.items:
                plugins.send('item_imported', lib=lib, item=item)

        # Finally, delete old files.
        if config.copy and config.delete:
            new_paths = [os.path.realpath(item.path) for item in task.items]
            for old_path in old_paths:
                # Only delete files that were actually moved.
                if old_path not in new_paths:
                    os.remove(syspath(old_path))

        # Update progress.
        if config.resume is not False:
            task.save_progress()


# Non-autotagged import (always sequential).
#TODO probably no longer necessary; use the same machinery?

def simple_import(config):
    """Add albums from the paths to the library without changing any
    tags.
    """
    for task in read_albums(config):
        if task.sentinel:
            task.save_progress()
            continue

        if config.copy:
            if config.delete:
                old_paths = [os.path.realpath(item.path) for item in task.items]
            for item in task.items:
                item.move(config.lib, True, True)

        album = config.lib.add_album(task.items, True)
        config.lib.save()            

        # Announce that we added an album.
        plugins.send('album_imported', album=album)

        if config.resume is not False:
            task.save_progress()

        if config.copy and config.delete:
            new_paths = [os.path.realpath(item.path) for item in task.items]
            for old_path in old_paths:
                # Only delete files that were actually moved.
                if old_path not in new_paths:
                    os.remove(syspath(old_path))

        log.info('added album: %s - %s' % (album.albumartist, album.album))


# Main driver.

def run_import(**kwargs):
    config = ImportConfig(**kwargs)
    
    if config.autot:
        # Autotag. Set up the pipeline.
        pl = pipeline.Pipeline([
            read_albums(config),
            initial_lookup(config),
            user_query(config),
            apply_choices(config),
        ])

        # Run the pipeline.
        try:
            if config.threaded:
                pl.run_parallel(QUEUE_SIZE)
            else:
                pl.run_sequential()
        except ImportAbort:
            # User aborted operation. Silently stop.
            pass
    else:
        # Simple import without autotagging. Always sequential.
        simple_import(config)
