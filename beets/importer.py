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
from collections import defaultdict

from beets import autotag
from beets import library
import beets.autotag.art
from beets import plugins
from beets.util import pipeline
from beets.util import syspath, normpath, plurality, displayable_path
from beets.util.enumeration import enum

action = enum(
    'SKIP', 'ASIS', 'TRACKS', 'MANUAL', 'APPLY', 'MANUAL_ID',
    name='action'
)

QUEUE_SIZE = 128
STATE_FILE = os.path.expanduser('~/.beetsstate')
SINGLE_ARTIST_THRESH = 0.25
VARIOUS_ARTISTS = u'Various Artists'

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

def log_choice(config, task):
    """Logs the task's current choice if it should be logged.
    """
    path = task.path if task.is_album else task.item.path
    if task.choice_flag is action.ASIS:
        tag_log(config.logfile, 'asis', path)
    elif task.choice_flag is action.SKIP:
        tag_log(config.logfile, 'skip', path)

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
            lib.timeout,
            lib.replacements,
        )
    else:
        return lib

def _duplicate_check(lib, task, recent=None):
    """Check whether an album already exists in the library. `recent`
    should be a set of (artist, album) pairs that will be built up
    with every call to this function and checked along with the
    library.
    """
    if task.choice_flag is action.ASIS:
        artist = task.cur_artist
        album = task.cur_album
    elif task.choice_flag is action.APPLY:
        artist = task.info.artist
        album = task.info.album
    else:
        return False

    if artist is None:
        # As-is import with no artist. Skip check.
        return False

    # Try the recent albums.
    if recent is not None:
        if (artist, album) in recent:
            return True
        recent.add((artist, album))

    # Look in the library.
    cur_paths = set(i.path for i in task.items if i)
    for album_cand in lib.albums(artist=artist):
        if album_cand.album == album:
            # Check whether the album is identical in contents, in which
            # case it is not a duplicate (will be replaced).
            other_paths = set(i.path for i in album_cand.items())
            if other_paths == cur_paths:
                continue
            return True

    return False

def _item_duplicate_check(lib, task, recent=None):
    """Check whether an item already exists in the library."""
    if task.choice_flag is action.ASIS:
        artist = task.item.artist
        title = task.item.title
    elif task.choice_flag is action.APPLY:
        artist = task.info.artist
        title = task.info.title
    else:
        return False

    # Try recent items.
    if recent is not None:
        if (artist, title) in recent:
            return True
        recent.add((artist, title))

    # Check the library.
    for other_item in lib.items(artist=artist, title=title):
        # Existing items not considered duplicates.
        if other_item.path == task.item.path:
            continue
        return True
    return False

def _infer_album_fields(task):
    """Given an album and an associated import task, massage the
    album-level metadata. This ensures that the album artist is set
    and that the "compilation" flag is set automatically.
    """
    assert task.is_album
    assert task.items

    changes = {}

    if task.choice_flag == action.ASIS:
        # Taking metadata "as-is". Guess whether this album is VA.
        plur_artist, freq = plurality([i.artist for i in task.items])
        if freq == len(task.items) or (freq > 1 and
                float(freq) / len(task.items) >= SINGLE_ARTIST_THRESH):
            # Single-artist album.
            changes['albumartist'] = plur_artist
            changes['comp'] = False
        else:
            # VA.
            changes['albumartist'] = VARIOUS_ARTISTS
            changes['comp'] = True

    elif task.choice_flag == action.APPLY:
        # Applying autotagged metadata. Just get AA from the first
        # item.
        for item in task.items:
            if item is not None:
                first_item = item
                break
        else:
            assert False, "all items are None"
        if not first_item.albumartist:
            changes['albumartist'] = first_item.artist
        if not first_item.mb_albumartistid:
            changes['mb_albumartistid'] = first_item.mb_artistid

    else:
        assert False

    # Apply new metadata.
    for item in task.items:
        if item is not None:
            for k, v in changes.iteritems():
                setattr(item, k, v)

def _open_state():
    """Reads the state file, returning a dictionary."""
    try:
        with open(STATE_FILE) as f:
            return pickle.load(f)
    except (IOError, EOFError):
        return {}
def _save_state(state):
    """Writes the state dictionary out to disk."""
    try:
        with open(STATE_FILE, 'w') as f:
            pickle.dump(state, f)
    except IOError, exc:
        log.error(u'state file could not be written: %s' % unicode(exc))


# Utilities for reading and writing the beets progress file, which
# allows long tagging tasks to be resumed when they pause (or crash).
PROGRESS_KEY = 'tagprogress'
def progress_set(toppath, path):
    """Record that tagging for the given `toppath` was successful up to
    `path`. If path is None, then clear the progress value (indicating
    that the tagging completed).
    """
    state = _open_state()
    if PROGRESS_KEY not in state:
        state[PROGRESS_KEY] = {}

    if path is None:
        # Remove progress from file.
        if toppath in state[PROGRESS_KEY]:
            del state[PROGRESS_KEY][toppath]
    else:
        state[PROGRESS_KEY][toppath] = path

    _save_state(state)
def progress_get(toppath):
    """Get the last successfully tagged subpath of toppath. If toppath
    has no progress information, returns None.
    """
    state = _open_state()
    if PROGRESS_KEY not in state:
        return None
    return state[PROGRESS_KEY].get(toppath)


# Similarly, utilities for manipulating the "incremental" import log.
# This keeps track of all directories that were ever imported, which
# allows the importer to only import new stuff.
HISTORY_KEY = 'taghistory'
def history_add(path):
    """Indicate that the import of `path` is completed and should not
    be repeated in incremental imports.
    """
    state = _open_state()
    if HISTORY_KEY not in state:
        state[HISTORY_KEY] = set()

    state[HISTORY_KEY].add(path)

    _save_state(state)
def history_get():
    """Get the set of completed paths in incremental imports.
    """
    state = _open_state()
    if HISTORY_KEY not in state:
        return set()
    return state[HISTORY_KEY]


# The configuration structure.

class ImportConfig(object):
    """Contains all the settings used during an import session. Should
    be used in a "write-once" way -- everything is set up initially and
    then never touched again.
    """
    _fields = ['lib', 'paths', 'resume', 'logfile', 'color', 'quiet',
               'quiet_fallback', 'copy', 'write', 'art', 'delete',
               'choose_match_func', 'should_resume_func', 'threaded',
               'autot', 'singletons', 'timid', 'choose_item_func',
               'query', 'incremental', 'ignore']
    def __init__(self, **kwargs):
        for slot in self._fields:
            setattr(self, slot, kwargs[slot])

        # Normalize the paths.
        if self.paths:
            self.paths = map(normpath, self.paths)

        # Incremental and progress are mutually exclusive.
        if self.incremental:
            self.resume = False

        # When based on a query instead of directories, never
        # save progress or try to resume.
        if self.query is not None:
            self.paths = None
            self.resume = False
            self.incremental = False


# The importer task class.

class ImportTask(object):
    """Represents a single set of items to be imported along with its
    intermediate state. May represent an album or a single item.
    """
    def __init__(self, toppath=None, path=None, items=None):
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

    @classmethod
    def progress_sentinel(cls, toppath, path):
        """Create a task indicating that a single directory in a larger
        import has finished. This is only required for singleton
        imports; progress is implied for album imports.
        """
        obj = cls(toppath, path)
        obj.sentinel = True
        return obj

    @classmethod
    def item_task(cls, item):
        """Creates an ImportTask for a single item."""
        obj = cls()
        obj.item = item
        obj.is_album = False
        return obj

    def set_match(self, cur_artist, cur_album, candidates, rec):
        """Sets the candidates for this album matched by the
        `autotag.tag_album` method.
        """
        assert not self.sentinel
        self.cur_artist = cur_artist
        self.cur_album = cur_album
        self.candidates = candidates
        self.rec = rec
        self.is_album = True

    def set_null_match(self):
        """Set the candidates to indicate no album match was found.
        """
        self.set_match(None, None, None, None)

    def set_item_match(self, candidates, rec):
        """Set the match for a single-item task."""
        assert not self.is_album
        assert self.item is not None
        self.item_match = (candidates, rec)

    def set_null_item_match(self):
        """For single-item tasks, mark the item as having no matches.
        """
        assert not self.is_album
        assert self.item is not None
        self.item_match = None

    def set_choice(self, choice):
        """Given either an (info, items) tuple or an action constant,
        indicates that an action has been selected by the user (or
        automatically).
        """
        assert not self.sentinel
        # Not part of the task structure:
        assert choice not in (action.MANUAL, action.MANUAL_ID)
        assert choice != action.APPLY # Only used internally.
        if choice in (action.SKIP, action.ASIS, action.TRACKS):
            self.choice_flag = choice
            self.info = None
        else:
            assert not isinstance(choice, action)
            if self.is_album:
                info, items = choice
                self.items = items # Reordered items list.
            else:
                info = choice
            self.info = info
            self.choice_flag = action.APPLY # Implicit choice.

    def save_progress(self):
        """Updates the progress state to indicate that this album has
        finished.
        """
        if self.sentinel and self.path is None:
            # "Done" sentinel.
            progress_set(self.toppath, None)
        elif self.sentinel or self.is_album:
            # "Directory progress" sentinel for singletons or a real
            # album task, which implies the same.
            progress_set(self.toppath, self.path)

    def save_history(self):
        """Save the directory in the history for incremental imports.
        """
        if self.sentinel or self.is_album:
            history_add(self.path)

    # Logical decisions.
    def should_write_tags(self):
        """Should new info be written to the files' metadata?"""
        if self.choice_flag == action.APPLY:
            return True
        elif self.choice_flag in (action.ASIS, action.TRACKS, action.SKIP):
            return False
        else:
            assert False
    def should_fetch_art(self):
        """Should album art be downloaded for this album?"""
        return self.should_write_tags() and self.is_album
    def should_skip(self):
        """After a choice has been made, returns True if this is a
        sentinel or it has been marked for skipping.
        """
        return self.sentinel or self.choice_flag == action.SKIP


# Full-album pipeline stages.

def read_tasks(config):
    """A generator yielding all the albums (as ImportTask objects) found
    in the user-specified list of paths. In the case of a singleton
    import, yields single-item tasks instead.
    """
    # Look for saved progress.
    progress = config.resume is not False
    if progress:
        resume_dirs = {}
        for path in config.paths:
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

    # Look for saved incremental directories.
    if config.incremental:
        incremental_skipped = 0
        history_dirs = history_get()
    
    for toppath in config.paths:
        # Check whether the path is to a file.
        if config.singletons and not os.path.isdir(syspath(toppath)):
            item = library.Item.from_path(toppath)
            yield ImportTask.item_task(item)
            continue
        
        # Produce paths under this directory.
        if progress:
            resume_dir = resume_dirs.get(toppath)
        for path, items in autotag.albums_in_dir(toppath, config.ignore):
            # Skip according to progress.
            if progress and resume_dir:
                # We're fast-forwarding to resume a previous tagging.
                if path == resume_dir:
                    # We've hit the last good path! Turn off the
                    # fast-forwarding.
                    resume_dir = None
                continue

            # When incremental, skip paths in the history.
            if config.incremental and path in history_dirs:
                log.debug(u'Skipping previously-imported path: %s' %
                          displayable_path(path))
                incremental_skipped += 1
                continue

            # Yield all the necessary tasks.
            if config.singletons:
                for item in items:
                    yield ImportTask.item_task(item)
                yield ImportTask.progress_sentinel(toppath, path)
            else:
                yield ImportTask(toppath, path, items)

        # Indicate the directory is finished.
        yield ImportTask.done_sentinel(toppath)

    # Show skipped directories.
    if config.incremental and incremental_skipped:
        log.info(u'Incremental import: skipped %i directories.' %
                 incremental_skipped)

def query_tasks(config):
    """A generator that works as a drop-in-replacement for read_tasks.
    Instead of finding files from the filesystem, a query is used to
    match items from the library.
    """
    lib = _reopen_lib(config.lib)

    if config.singletons:
        # Search for items.
        for item in lib.items(config.query):
            yield ImportTask.item_task(item)

    else:
        # Search for albums.
        for album in lib.albums(config.query):
            log.debug('yielding album %i: %s - %s' %
                      (album.id, album.albumartist, album.album))
            items = list(album.items())
            yield ImportTask(None, album.item_dir(), items)

def initial_lookup(config):
    """A coroutine for performing the initial MusicBrainz lookup for an
    album. It accepts lists of Items and yields
    (items, cur_artist, cur_album, candidates, rec) tuples. If no match
    is found, all of the yielded parameters (except items) are None.
    """
    task = None
    while True:
        task = yield task
        if task.sentinel:
            continue

        log.debug('Looking up: %s' % task.path)
        try:
            task.set_match(*autotag.tag_album(task.items, config.timid))
        except autotag.AutotagError:
            task.set_null_match()

def user_query(config):
    """A coroutine for interfacing with the user about the tagging
    process. lib is the Library to import into and logfile may be
    a file-like object for logging the import process. The coroutine
    accepts and yields ImportTask objects.
    """
    lib = _reopen_lib(config.lib)
    recent = set()
    task = None
    while True:
        task = yield task
        if task.sentinel:
            continue
        
        # Ask the user for a choice.
        choice = config.choose_match_func(task, config)
        task.set_choice(choice)
        log_choice(config, task)

        # As-tracks: transition to singleton workflow.
        if choice is action.TRACKS:
            # Set up a little pipeline for dealing with the singletons.
            item_tasks = []
            def emitter():
                for item in task.items:
                    yield ImportTask.item_task(item)
                yield ImportTask.progress_sentinel(task.toppath, task.path)
            def collector():
                while True:
                    item_task = yield
                    item_tasks.append(item_task)
            ipl = pipeline.Pipeline((emitter(), item_lookup(config), 
                                     item_query(config), collector()))
            ipl.run_sequential()
            task = pipeline.multiple(item_tasks)
            continue

        # Check for duplicates if we have a match (or ASIS).
        if _duplicate_check(lib, task, recent):
            tag_log(config.logfile, 'duplicate', task.path)
            log.warn("This album is already in the library!")
            task.set_choice(action.SKIP)

def show_progress(config):
    """This stage replaces the initial_lookup and user_query stages
    when the importer is run without autotagging. It displays the album
    name and artist as the files are added.
    """
    task = None
    while True:
        task = yield task
        if task.sentinel:
            continue

        log.info(task.path)

        # Behave as if ASIS were selected.
        task.set_null_match()
        task.set_choice(action.ASIS)
        
def apply_choices(config):
    """A coroutine for applying changes to albums during the autotag
    process.
    """
    lib = _reopen_lib(config.lib)
    task = None
    while True:    
        task = yield task
        if task.should_skip():
            continue

        items = [i for i in task.items if i] if task.is_album else [task.item]
        # Clear IDs in case the items are being re-tagged.
        for item in items:
            item.id = None
            item.album_id = None

        # Change metadata.
        if task.should_write_tags():
            if task.is_album:
                autotag.apply_metadata(task.items, task.info)
            else:
                autotag.apply_item_metadata(task.item, task.info)

        # Infer album-level fields.
        if task.is_album:
            _infer_album_fields(task)

        # Find existing item entries that these are replacing. Old
        # album structures are automatically cleaned up when the
        # last item is removed.
        replaced_items = defaultdict(list)
        for item in items:
            dup_items = lib.items(library.MatchQuery('path', item.path))
            for dup_item in dup_items:
                replaced_items[item].append(dup_item)
                log.debug('replacing item %i: %s' %
                          (dup_item.id, displayable_path(item.path)))
        log.debug('%i of %i items replaced' % (len(replaced_items),
                                               len(items)))

        # Move/copy files.
        task.old_paths = [item.path for item in items]
        for item in items:
            if config.copy:
                # If we're replacing an item, then move rather than
                # copying.
                old_path = item.path
                do_copy = not bool(replaced_items[item])
                lib.move(item, do_copy, task.is_album)
                if not do_copy:
                    # If we moved the item, remove the now-nonexistent
                    # file from old_paths.
                    task.old_paths.remove(old_path)
            if config.write and task.should_write_tags():
                item.write()

        # Add items to library. We consolidate this at the end to avoid
        # locking while we do the copying and tag updates.
        try:
            # Remove old items.
            for replaced in replaced_items.itervalues():
                for item in replaced:
                    lib.remove(item)

            # Add new ones.
            if task.is_album:
                # Add an album.
                album = lib.add_album(items)
                task.album_id = album.id
            else:
                # Add tracks.
                for item in items:
                    lib.add(item)
        finally:
            lib.save()

def fetch_art(config):
    """A coroutine that fetches and applies album art for albums where
    appropriate.
    """
    lib = _reopen_lib(config.lib)
    task = None
    while True:
        task = yield task
        if task.should_skip():
            continue

        if task.should_fetch_art():
            artpath = beets.autotag.art.art_for_album(task.info, task.path)

            # Save the art if any was found.
            if artpath:
                try:
                    album = lib.get_album(task.album_id)
                    album.set_art(artpath)
                finally:
                    lib.save(False)

def finalize(config):
    """A coroutine that finishes up importer tasks. In particular, the
    coroutine sends plugin events, deletes old files, and saves
    progress. This is a "terminal" coroutine (it yields None).
    """
    lib = _reopen_lib(config.lib)
    while True:
        task = yield
        if task.should_skip():
            if config.resume is not False:
                task.save_progress()
            if config.incremental:
                task.save_history()
            continue

        items = [i for i in task.items if i] if task.is_album else [task.item]

        # Announce that we've added an album.
        if task.is_album:
            album = lib.get_album(task.album_id)
            plugins.send('album_imported', lib=lib, album=album, config=config)
        else:
            for item in items:
                plugins.send('item_imported', lib=lib, item=item, config=config)

        # Finally, delete old files.
        if config.copy and config.delete:
            new_paths = [os.path.realpath(item.path) for item in items]
            for old_path in task.old_paths:
                # Only delete files that were actually copied.
                if old_path not in new_paths:
                    os.remove(syspath(old_path))

        # Update progress.
        if config.resume is not False:
            task.save_progress()
        if config.incremental:
            task.save_history()


# Singleton pipeline stages.

def item_lookup(config):
    """A coroutine used to perform the initial MusicBrainz lookup for
    an item task.
    """
    task = None
    while True:
        task = yield task
        if task.sentinel:
            continue

        task.set_item_match(*autotag.tag_item(task.item, config.timid))

def item_query(config):
    """A coroutine that queries the user for input on single-item
    lookups.
    """
    lib = _reopen_lib(config.lib)
    task = None
    recent = set()
    while True:
        task = yield task
        if task.sentinel:
            continue

        choice = config.choose_item_func(task, config)
        task.set_choice(choice)
        log_choice(config, task)

        # Duplicate check.
        if _item_duplicate_check(lib, task, recent):
            tag_log(config.logfile, 'duplicate', task.item.path)
            log.warn("This item is already in the library!")
            task.set_choice(action.SKIP)

def item_progress(config):
    """Skips the lookup and query stages in a non-autotagged singleton
    import. Just shows progress.
    """
    task = None
    log.info('Importing items:')
    while True:
        task = yield task
        if task.sentinel:
            continue

        log.info(displayable_path(task.item.path))
        task.set_null_item_match()
        task.set_choice(action.ASIS)


# Main driver.

def run_import(**kwargs):
    """Run an import. The keyword arguments are the same as those to
    ImportConfig.
    """
    config = ImportConfig(**kwargs)
    
    # Set up the pipeline.
    if config.query is None:
        stages = [read_tasks(config)]
    else:
        stages = [query_tasks(config)]
    if config.singletons:
        # Singleton importer.
        if config.autot:
            stages += [item_lookup(config), item_query(config)]
        else:
            stages += [item_progress(config)]
    else:
        # Whole-album importer.
        if config.autot:
            # Only look up and query the user when autotagging.
            stages += [initial_lookup(config), user_query(config)]
        else:
            # When not autotagging, just display progress.
            stages += [show_progress(config)]
    stages += [apply_choices(config)]
    if config.art:
        stages += [fetch_art(config)]
    stages += [finalize(config)]
    pl = pipeline.Pipeline(stages)

    # Run the pipeline.
    try:
        if config.threaded:
            pl.run_parallel(QUEUE_SIZE)
        else:
            pl.run_sequential()
    except ImportAbort:
        # User aborted operation. Silently stop.
        pass
