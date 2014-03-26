# This file is part of beets.
# Copyright 2013, Adrian Sampson.
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
from __future__ import print_function

import os
import logging
import pickle
import itertools
from collections import defaultdict

from beets import autotag
from beets import library
from beets import dbcore
from beets import plugins
from beets import util
from beets import config
from beets.util import pipeline
from beets.util import syspath, normpath, displayable_path
from beets.util.enumeration import enum
from beets import mediafile

action = enum(
    'SKIP', 'ASIS', 'TRACKS', 'MANUAL', 'APPLY', 'MANUAL_ID',
    'ALBUMS', name='action'
)

QUEUE_SIZE = 128
SINGLE_ARTIST_THRESH = 0.25
VARIOUS_ARTISTS = u'Various Artists'

# Global logger.
log = logging.getLogger('beets')

class ImportAbort(Exception):
    """Raised when the user aborts the tagging operation.
    """
    pass


# Utilities.

def _duplicate_check(lib, task):
    """Check whether an album already exists in the library. Returns a
    list of Album objects (empty if no duplicates are found).
    """
    assert task.choice_flag in (action.ASIS, action.APPLY)
    artist, album = task.chosen_ident()

    if artist is None:
        # As-is import with no artist. Skip check.
        return []

    found_albums = []
    cur_paths = set(i.path for i in task.items if i)
    for album_cand in lib.albums(dbcore.MatchQuery('albumartist', artist)):
        if album_cand.album == album:
            # Check whether the album is identical in contents, in which
            # case it is not a duplicate (will be replaced).
            other_paths = set(i.path for i in album_cand.items())
            if other_paths == cur_paths:
                continue
            found_albums.append(album_cand)
    return found_albums

def _item_duplicate_check(lib, task):
    """Check whether an item already exists in the library. Returns a
    list of Item objects.
    """
    assert task.choice_flag in (action.ASIS, action.APPLY)
    artist, title = task.chosen_ident()

    found_items = []
    query = dbcore.AndQuery((
        dbcore.MatchQuery('artist', artist),
        dbcore.MatchQuery('title', title),
    ))
    for other_item in lib.items(query):
        # Existing items not considered duplicates.
        if other_item.path == task.item.path:
            continue
        found_items.append(other_item)
    return found_items

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
        plur_albumartist, freq = util.plurality(
                [i.albumartist or i.artist for i in task.items])
        if freq == len(task.items) or (freq > 1 and
                float(freq) / len(task.items) >= SINGLE_ARTIST_THRESH):
            # Single-artist album.
            changes['albumartist'] = plur_albumartist
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

def _resume():
    """Check whether an import should resume and return a boolean or the
    string 'ask' indicating that the user should be queried.
    """
    return config['import']['resume'].as_choice([True, False, 'ask'])

def _open_state():
    """Reads the state file, returning a dictionary."""
    try:
        with open(config['statefile'].as_filename()) as f:
            return pickle.load(f)
    except (IOError, EOFError):
        return {}
def _save_state(state):
    """Writes the state dictionary out to disk."""
    try:
        with open(config['statefile'].as_filename(), 'w') as f:
            pickle.dump(state, f)
    except IOError as exc:
        log.error(u'state file could not be written: %s' % unicode(exc))


# Utilities for reading and writing the beets progress file, which
# allows long tagging tasks to be resumed when they pause (or crash).
PROGRESS_KEY = 'tagprogress'
def progress_set(toppath, paths):
    """Record that tagging for the given `toppath` was successful up to
    `paths`. If paths is None, then clear the progress value (indicating
    that the tagging completed).
    """
    state = _open_state()
    if PROGRESS_KEY not in state:
        state[PROGRESS_KEY] = {}

    if paths is None:
        # Remove progress from file.
        if toppath in state[PROGRESS_KEY]:
            del state[PROGRESS_KEY][toppath]
    else:
        state[PROGRESS_KEY][toppath] = paths

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
def history_add(paths):
    """Indicate that the import of the album in `paths` is completed and
    should not be repeated in incremental imports.
    """
    state = _open_state()
    if HISTORY_KEY not in state:
        state[HISTORY_KEY] = set()

    state[HISTORY_KEY].add(tuple(paths))

    _save_state(state)
def history_get():
    """Get the set of completed path tuples in incremental imports.
    """
    state = _open_state()
    if HISTORY_KEY not in state:
        return set()
    return state[HISTORY_KEY]


# Abstract session class.

class ImportSession(object):
    """Controls an import action. Subclasses should implement methods to
    communicate with the user or otherwise make decisions.
    """
    def __init__(self, lib, logfile, paths, query):
        """Create a session. `lib` is a Library object. `logfile` is a
        file-like object open for writing or None if no logging is to be
        performed. Either `paths` or `query` is non-null and indicates
        the source of files to be imported.
        """
        self.lib = lib
        self.logfile = logfile
        self.paths = paths
        self.query = query

        # Normalize the paths.
        if self.paths:
            self.paths = map(normpath, self.paths)

    def _amend_config(self):
        """Make implied changes the importer configuration.
        """
        # FIXME: Maybe this function should not exist and should instead
        # provide "decision wrappers" like "should_resume()", etc.
        iconfig = config['import']

        # Incremental and progress are mutually exclusive.
        if iconfig['incremental']:
            iconfig['resume'] = False

        # When based on a query instead of directories, never
        # save progress or try to resume.
        if self.query is not None:
            iconfig['resume'] = False
            iconfig['incremental'] = False

        # Copy and move are mutually exclusive.
        if iconfig['move']:
            iconfig['copy'] = False

        # Only delete when copying.
        if not iconfig['copy']:
            iconfig['delete'] = False

    def tag_log(self, status, paths):
        """Log a message about a given album to logfile. The status should
        reflect the reason the album couldn't be tagged.
        """
        if self.logfile:
            print(u'{0} {1}'.format(status, displayable_path(paths)),
                  file=self.logfile)
            self.logfile.flush()

    def log_choice(self, task, duplicate=False):
        """Logs the task's current choice if it should be logged. If
        ``duplicate``, then this is a secondary choice after a duplicate was
        detected and a decision was made.
        """
        paths = task.paths if task.is_album else [task.item.path]
        if duplicate:
            # Duplicate: log all three choices (skip, keep both, and trump).
            if task.remove_duplicates:
                self.tag_log('duplicate-replace', paths)
            elif task.choice_flag in (action.ASIS, action.APPLY):
                self.tag_log('duplicate-keep', paths)
            elif task.choice_flag is (action.SKIP):
                self.tag_log('duplicate-skip', paths)
        else:
            # Non-duplicate: log "skip" and "asis" choices.
            if task.choice_flag is action.ASIS:
                self.tag_log('asis', paths)
            elif task.choice_flag is action.SKIP:
                self.tag_log('skip', paths)

    def should_resume(self, path):
        raise NotImplementedError

    def choose_match(self, task):
        raise NotImplementedError

    def resolve_duplicate(self, task):
        raise NotImplementedError

    def choose_item(self, task):
        raise NotImplementedError

    def run(self):
        """Run the import task.
        """
        self._amend_config()

        # Set up the pipeline.
        if self.query is None:
            stages = [read_tasks(self)]
        else:
            stages = [query_tasks(self)]
        if config['import']['singletons']:
            # Singleton importer.
            if config['import']['autotag']:
                stages += [item_lookup(self), item_query(self)]
            else:
                stages += [item_progress(self)]
        else:
            # Whole-album importer.
            if config['import']['group_albums']:
                # Split directory tasks into one task for each album
                stages += [group_albums(self)]
            if config['import']['autotag']:
                # Only look up and query the user when autotagging.
                stages += [initial_lookup(self), user_query(self)]
            else:
                # When not autotagging, just display progress.
                stages += [show_progress(self)]
        stages += [apply_choices(self)]
        for stage_func in plugins.import_stages():
            stages.append(plugin_stage(self, stage_func))
        stages += [manipulate_files(self)]
        stages += [finalize(self)]
        pl = pipeline.Pipeline(stages)

        # Run the pipeline.
        try:
            if config['threaded']:
                pl.run_parallel(QUEUE_SIZE)
            else:
                pl.run_sequential()
        except ImportAbort:
            # User aborted operation. Silently stop.
            pass


# The importer task class.

class ImportTask(object):
    """Represents a single set of items to be imported along with its
    intermediate state. May represent an album or a single item.
    """
    def __init__(self, toppath=None, paths=None, items=None):
        self.toppath = toppath
        self.paths = paths
        self.items = items
        self.sentinel = False
        self.remove_duplicates = False
        self.is_album = True
        self.choice_flag = None

    @classmethod
    def done_sentinel(cls, toppath):
        """Create an ImportTask that indicates the end of a top-level
        directory import.
        """
        obj = cls(toppath)
        obj.sentinel = True
        return obj

    @classmethod
    def progress_sentinel(cls, toppath, paths):
        """Create a task indicating that a single directory in a larger
        import has finished. This is only required for singleton
        imports; progress is implied for album imports.
        """
        obj = cls(toppath, paths)
        obj.sentinel = True
        return obj

    @classmethod
    def item_task(cls, item):
        """Creates an ImportTask for a single item."""
        obj = cls()
        obj.item = item
        obj.is_album = False
        return obj

    def set_candidates(self, cur_artist, cur_album, candidates, rec):
        """Sets the candidates for this album matched by the
        `autotag.tag_album` method.
        """
        assert self.is_album
        assert not self.sentinel
        self.cur_artist = cur_artist
        self.cur_album = cur_album
        self.candidates = candidates
        self.rec = rec

    def set_null_candidates(self):
        """Set the candidates to indicate no album match was found.
        """
        self.cur_artist = None
        self.cur_album = None
        self.candidates = None
        self.rec = None

    def set_item_candidates(self, candidates, rec):
        """Set the match for a single-item task."""
        assert not self.is_album
        assert self.item is not None
        self.candidates = candidates
        self.rec = rec

    def set_choice(self, choice):
        """Given an AlbumMatch or TrackMatch object or an action constant,
        indicates that an action has been selected for this task.
        """
        assert not self.sentinel
        # Not part of the task structure:
        assert choice not in (action.MANUAL, action.MANUAL_ID)
        assert choice != action.APPLY  # Only used internally.
        if choice in (action.SKIP, action.ASIS, action.TRACKS, action.ALBUMS):
            self.choice_flag = choice
            self.match = None
        else:
            if self.is_album:
                assert isinstance(choice, autotag.AlbumMatch)
            else:
                assert isinstance(choice, autotag.TrackMatch)
            self.choice_flag = action.APPLY  # Implicit choice.
            self.match = choice

    def save_progress(self):
        """Updates the progress state to indicate that this album has
        finished.
        """
        if self.sentinel and self.paths is None:
            # "Done" sentinel.
            progress_set(self.toppath, None)
        elif self.sentinel or self.is_album:
            # "Directory progress" sentinel for singletons or a real
            # album task, which implies the same.
            progress_set(self.toppath, self.paths)

    def save_history(self):
        """Save the directory in the history for incremental imports.
        """
        if self.is_album and self.paths and not self.sentinel:
            history_add(self.paths)


    # Logical decisions.

    def should_write_tags(self):
        """Should new info be written to the files' metadata?"""
        if self.choice_flag == action.APPLY:
            return True
        elif self.choice_flag in (action.ASIS, action.TRACKS, action.SKIP):
            return False
        else:
            assert False

    def should_skip(self):
        """After a choice has been made, returns True if this is a
        sentinel or it has been marked for skipping.
        """
        return self.sentinel or self.choice_flag == action.SKIP


    # Convenient data.

    def chosen_ident(self):
        """Returns identifying metadata about the current choice. For
        albums, this is an (artist, album) pair. For items, this is
        (artist, title). May only be called when the choice flag is ASIS
        (in which case the data comes from the files' current metadata)
        or APPLY (data comes from the choice).
        """
        assert self.choice_flag in (action.ASIS, action.APPLY)
        if self.is_album:
            if self.choice_flag is action.ASIS:
                return (self.cur_artist, self.cur_album)
            elif self.choice_flag is action.APPLY:
                return (self.match.info.artist, self.match.info.album)
        else:
            if self.choice_flag is action.ASIS:
                return (self.item.artist, self.item.title)
            elif self.choice_flag is action.APPLY:
                return (self.match.info.artist, self.match.info.title)

    def imported_items(self):
        """Return a list of Items that should be added to the library.
        If this is an album task, return the list of items in the
        selected match or everything if the choice is ASIS. If this is a
        singleton task, return a list containing the item.
        """
        if self.is_album:
            if self.choice_flag == action.ASIS:
                return list(self.items)
            elif self.choice_flag == action.APPLY:
                return self.match.mapping.keys()
            else:
                assert False
        else:
            return [self.item]


    # Utilities.

    def prune(self, filename):
        """Prune any empty directories above the given file. If this
        task has no `toppath` or the file path provided is not within
        the `toppath`, then this function has no effect. Similarly, if
        the file still exists, no pruning is performed, so it's safe to
        call when the file in question may not have been removed.
        """
        if self.toppath and not os.path.exists(filename):
            util.prune_dirs(os.path.dirname(filename),
                            self.toppath,
                            clutter=config['clutter'].as_str_seq())


# Full-album pipeline stages.

def read_tasks(session):
    """A generator yielding all the albums (as ImportTask objects) found
    in the user-specified list of paths. In the case of a singleton
    import, yields single-item tasks instead.
    """
    # Look for saved progress.
    if _resume():
        resume_dirs = {}
        for path in session.paths:
            resume_dir = progress_get(path)
            if resume_dir:

                # Either accept immediately or prompt for input to decide.
                if _resume() is True:
                    do_resume = True
                    log.warn('Resuming interrupted import of %s' % path)
                else:
                    do_resume = session.should_resume(path)

                if do_resume:
                    resume_dirs[path] = resume_dir
                else:
                    # Clear progress; we're starting from the top.
                    progress_set(path, None)

    # Look for saved incremental directories.
    if config['import']['incremental']:
        incremental_skipped = 0
        history_dirs = history_get()

    for toppath in session.paths:
        # Check whether the path is to a file.
        if config['import']['singletons'] and \
                not os.path.isdir(syspath(toppath)):
            try:
                item = library.Item.from_path(toppath)
            except mediafile.UnreadableFileError:
                log.warn(u'unreadable file: {0}'.format(
                    util.displayable_path(toppath)
                ))
                continue
            yield ImportTask.item_task(item)
            continue

        # A flat album import merges all items into one album.
        if config['import']['flat'] and not config['import']['singletons']:
            all_items = []
            for _, items in autotag.albums_in_dir(toppath):
                all_items += items
            yield ImportTask(toppath, toppath, all_items)
            yield ImportTask.done_sentinel(toppath)
            continue

        # Produce paths under this directory.
        if _resume():
            resume_dir = resume_dirs.get(toppath)
        for path, items in autotag.albums_in_dir(toppath):
            # Skip according to progress.
            if _resume() and resume_dir:
                # We're fast-forwarding to resume a previous tagging.
                if path == resume_dir:
                    # We've hit the last good path! Turn off the
                    # fast-forwarding.
                    resume_dir = None
                continue

            # When incremental, skip paths in the history.
            if config['import']['incremental'] and tuple(path) in history_dirs:
                log.debug(u'Skipping previously-imported path: %s' %
                          displayable_path(path))
                incremental_skipped += 1
                continue

            # Yield all the necessary tasks.
            if config['import']['singletons']:
                for item in items:
                    yield ImportTask.item_task(item)
                yield ImportTask.progress_sentinel(toppath, path)
            else:
                yield ImportTask(toppath, path, items)

        # Indicate the directory is finished.
        yield ImportTask.done_sentinel(toppath)

    # Show skipped directories.
    if config['import']['incremental'] and incremental_skipped:
        log.info(u'Incremental import: skipped %i directories.' %
                 incremental_skipped)

def query_tasks(session):
    """A generator that works as a drop-in-replacement for read_tasks.
    Instead of finding files from the filesystem, a query is used to
    match items from the library.
    """
    if config['import']['singletons']:
        # Search for items.
        for item in session.lib.items(session.query):
            yield ImportTask.item_task(item)

    else:
        # Search for albums.
        for album in session.lib.albums(session.query):
            log.debug('yielding album %i: %s - %s' %
                      (album.id, album.albumartist, album.album))
            items = list(album.items())
            yield ImportTask(None, [album.item_dir()], items)

def initial_lookup(session):
    """A coroutine for performing the initial MusicBrainz lookup for an
    album. It accepts lists of Items and yields
    (items, cur_artist, cur_album, candidates, rec) tuples. If no match
    is found, all of the yielded parameters (except items) are None.
    """
    task = None
    while True:
        task = yield task
        if task.should_skip():
            continue

        plugins.send('import_task_start', session=session, task=task)

        log.debug('Looking up: %s' % displayable_path(task.paths))
        task.set_candidates(
            *autotag.tag_album(task.items)
        )

def user_query(session):
    """A coroutine for interfacing with the user about the tagging
    process.

    The coroutine accepts an ImportTask objects. It uses the
    session's ``choose_match`` method to determine the ``action`` for
    this task. Depending on the action additional stages are exectuted
    and the processed task is yielded.

    It emits the ``import_task_choice`` event for plugins. Plugins have
    acces to the choice via the ``taks.choice_flag`` property and may
    choose to change it.
    """
    recent = set()
    task = None
    while True:
        task = yield task
        if task.should_skip():
            continue

        # Ask the user for a choice.
        choice = session.choose_match(task)
        task.set_choice(choice)
        session.log_choice(task)
        plugins.send('import_task_choice', session=session, task=task)

        # As-tracks: transition to singleton workflow.
        if task.choice_flag is action.TRACKS:
            # Set up a little pipeline for dealing with the singletons.
            def emitter(task):
                for item in task.items:
                    yield ImportTask.item_task(item)
                yield ImportTask.progress_sentinel(task.toppath, task.paths)

            ipl = pipeline.Pipeline([
                emitter(task),
                item_lookup(session),
                item_query(session),
            ])
            task = pipeline.multiple(ipl.pull())
            continue

        # As albums: group items by albums and create task for each album
        if task.choice_flag is action.ALBUMS:
            def emitter(task):
                yield task

            ipl = pipeline.Pipeline([
                emitter(task),
                group_albums(session),
                initial_lookup(session),
                user_query(session)
            ])
            task = pipeline.multiple(ipl.pull())
            continue

        # Check for duplicates if we have a match (or ASIS).
        if task.choice_flag in (action.ASIS, action.APPLY):
            ident = task.chosen_ident()
            # The "recent" set keeps track of identifiers for recently
            # imported albums -- those that haven't reached the database
            # yet.
            if ident in recent or _duplicate_check(session.lib, task):
                session.resolve_duplicate(task)
                session.log_choice(task, True)
            recent.add(ident)

def show_progress(session):
    """This stage replaces the initial_lookup and user_query stages
    when the importer is run without autotagging. It displays the album
    name and artist as the files are added.
    """
    task = None
    while True:
        task = yield task
        if task.should_skip():
            continue

        log.info(displayable_path(task.paths))

        # Behave as if ASIS were selected.
        task.set_null_candidates()
        task.set_choice(action.ASIS)

def apply_choices(session):
    """A coroutine for applying changes to albums and singletons during
    the autotag process.
    """
    task = None
    while True:
        task = yield task
        if task.should_skip():
            continue

        items = task.imported_items()
        # Clear IDs in case the items are being re-tagged.
        for item in items:
            item.id = None
            item.album_id = None

        # Change metadata.
        if task.should_write_tags():
            if task.is_album:
                autotag.apply_metadata(
                    task.match.info, task.match.mapping
                )
            else:
                autotag.apply_item_metadata(task.item, task.match.info)
            plugins.send('import_task_apply', session=session, task=task)

        # Infer album-level fields.
        if task.is_album:
            _infer_album_fields(task)

        # Find existing item entries that these are replacing (for
        # re-imports). Old album structures are automatically cleaned up
        # when the last item is removed.
        task.replaced_items = defaultdict(list)
        for item in items:
            dup_items = session.lib.items(
                dbcore.query.BytesQuery('path', item.path)
            )
            for dup_item in dup_items:
                task.replaced_items[item].append(dup_item)
                log.debug('replacing item %i: %s' %
                          (dup_item.id, displayable_path(item.path)))
        log.debug('%i of %i items replaced' % (len(task.replaced_items),
                                               len(items)))

        # Find old items that should be replaced as part of a duplicate
        # resolution.
        duplicate_items = []
        if task.remove_duplicates:
            if task.is_album:
                for album in _duplicate_check(session.lib, task):
                    duplicate_items += album.items()
            else:
                duplicate_items = _item_duplicate_check(session.lib, task)
            log.debug('removing %i old duplicated items' %
                      len(duplicate_items))

            # Delete duplicate files that are located inside the library
            # directory.
            task.duplicate_paths = []
            for duplicate_path in [i.path for i in duplicate_items]:
                if session.lib.directory in util.ancestry(duplicate_path):
                    # Mark the path for deletion in the manipulate_files
                    # stage.
                    task.duplicate_paths.append(duplicate_path)

        # Add items -- before path changes -- to the library. We add the
        # items now (rather than at the end) so that album structures
        # are in place before calls to destination().
        with session.lib.transaction():
            # Remove old items.
            for replaced in task.replaced_items.itervalues():
                for item in replaced:
                    item.remove()
            for item in duplicate_items:
                item.remove()

            # Add new ones.
            if task.is_album:
                # Add an album.
                album = session.lib.add_album(items)
                task.album_id = album.id
            else:
                # Add tracks.
                for item in items:
                    session.lib.add(item)

def plugin_stage(session, func):
    """A coroutine (pipeline stage) that calls the given function with
    each non-skipped import task. These stages occur between applying
    metadata changes and moving/copying/writing files.
    """
    task = None
    while True:
        task = yield task
        if task.should_skip():
            continue
        func(session, task)

        # Stage may modify DB, so re-load cached item data.
        for item in task.imported_items():
            item.load()

def manipulate_files(session):
    """A coroutine (pipeline stage) that performs necessary file
    manipulations *after* items have been added to the library.
    """
    task = None
    while True:
        task = yield task
        if task.should_skip():
            continue

        # Remove duplicate files marked for deletion.
        if task.remove_duplicates:
            for duplicate_path in task.duplicate_paths:
                log.debug(u'deleting replaced duplicate %s' %
                          util.displayable_path(duplicate_path))
                util.remove(duplicate_path)
                util.prune_dirs(os.path.dirname(duplicate_path),
                                session.lib.directory)

        # Move/copy/write files.
        items = task.imported_items()
        # Save the original paths of all items for deletion and pruning
        # in the next step (finalization).
        task.old_paths = [item.path for item in items]
        for item in items:
            if config['import']['move']:
                # Just move the file.
                item.move(False)
            elif config['import']['copy']:
                # If it's a reimport, move in-library files and copy
                # out-of-library files. Otherwise, copy and keep track
                # of the old path.
                old_path = item.path
                if task.replaced_items[item]:
                    # This is a reimport. Move in-library files and copy
                    # out-of-library files.
                    if session.lib.directory in util.ancestry(old_path):
                        item.move(False)
                        # We moved the item, so remove the
                        # now-nonexistent file from old_paths.
                        task.old_paths.remove(old_path)
                    else:
                        item.move(True)
                else:
                    # A normal import. Just copy files and keep track of
                    # old paths.
                    item.move(True)

            if config['import']['write'] and task.should_write_tags():
                try:
                    item.write()
                except library.FileOperationError as exc:
                    log.error(exc)

        # Save new paths.
        with session.lib.transaction():
            for item in items:
                item.store()

        # Plugin event.
        plugins.send('import_task_files', session=session, task=task)

def finalize(session):
    """A coroutine that finishes up importer tasks. In particular, the
    coroutine sends plugin events, deletes old files, and saves
    progress. This is a "terminal" coroutine (it yields None).
    """
    while True:
        task = yield
        if task.should_skip():
            if _resume():
                task.save_progress()
            if config['import']['incremental']:
                task.save_history()
            continue

        items = task.imported_items()

        # Announce that we've added an album.
        if task.is_album:
            album = session.lib.get_album(task.album_id)
            plugins.send('album_imported',
                         lib=session.lib, album=album)
        else:
            for item in items:
                plugins.send('item_imported',
                             lib=session.lib, item=item)

        # When copying and deleting originals, delete old files.
        if config['import']['copy'] and config['import']['delete']:
            new_paths = [os.path.realpath(item.path) for item in items]
            for old_path in task.old_paths:
                # Only delete files that were actually copied.
                if old_path not in new_paths:
                    util.remove(syspath(old_path), False)
                    task.prune(old_path)

        # When moving, prune empty directories containing the original
        # files.
        elif config['import']['move']:
            for old_path in task.old_paths:
                task.prune(old_path)

        # Update progress.
        if _resume():
            task.save_progress()
        if config['import']['incremental']:
            task.save_history()


# Singleton pipeline stages.

def item_lookup(session):
    """A coroutine used to perform the initial MusicBrainz lookup for
    an item task.
    """
    task = None
    while True:
        task = yield task
        if task.should_skip():
            continue

        plugins.send('import_task_start', session=session, task=task)

        task.set_item_candidates(*autotag.tag_item(task.item))

def item_query(session):
    """A coroutine that queries the user for input on single-item
    lookups.
    """
    task = None
    recent = set()
    while True:
        task = yield task
        if task.should_skip():
            continue

        choice = session.choose_item(task)
        task.set_choice(choice)
        session.log_choice(task)
        plugins.send('import_task_choice', session=session, task=task)

        # Duplicate check.
        if task.choice_flag in (action.ASIS, action.APPLY):
            ident = task.chosen_ident()
            if ident in recent or _item_duplicate_check(session.lib, task):
                session.resolve_duplicate(task)
                session.log_choice(task, True)
            recent.add(ident)

def item_progress(session):
    """Skips the lookup and query stages in a non-autotagged singleton
    import. Just shows progress.
    """
    task = None
    log.info('Importing items:')
    while True:
        task = yield task
        if task.should_skip():
            continue

        log.info(displayable_path(task.item.path))
        task.set_null_candidates()
        task.set_choice(action.ASIS)


def group_albums(session):
    """Group the items of a task by albumartist and album name and create a new
    task for each album. Yield the tasks as a multi message.
    """
    def group(item):
        return (item.albumartist or item.artist, item.album)

    task = None
    while True:
        task = yield task
        if task.should_skip():
            continue
        tasks = []
        for _, items in itertools.groupby(task.items, group):
            tasks.append(ImportTask(items=list(items)))
        tasks.append(ImportTask.progress_sentinel(task.toppath, task.paths))

        task = pipeline.multiple(tasks)
