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
from tempfile import mkdtemp
import shutil

from beets import autotag
from beets import library
from beets import dbcore
from beets import plugins
from beets import util
from beets import config
from beets.util import pipeline
from beets.util import syspath, normpath, displayable_path
from enum import Enum
from beets import mediafile

action = Enum('action',
              ['SKIP', 'ASIS', 'TRACKS', 'MANUAL', 'APPLY', 'MANUAL_ID',
               'ALBUMS'])

QUEUE_SIZE = 128
SINGLE_ARTIST_THRESH = 0.25
VARIOUS_ARTISTS = u'Various Artists'
PROGRESS_KEY = 'tagprogress'
HISTORY_KEY = 'taghistory'

# Global logger.
log = logging.getLogger('beets')


class ImportAbort(Exception):
    """Raised when the user aborts the tagging operation.
    """
    pass


# Utilities.

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

        self.want_resume = iconfig['resume'].as_choice([True, False, 'ask'])

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
        paths = task.paths
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
                stages += [lookup_candidates(self), item_query(self),
                           resolve_duplicates(self)]
            else:
                stages += [item_progress(self)]
        else:
            # Whole-album importer.
            if config['import']['group_albums']:
                # Split directory tasks into one task for each album
                stages += [group_albums(self)]
            if config['import']['autotag']:
                # Only look up and query the user when autotagging.
                stages += [lookup_candidates(self), user_query(self),
                           resolve_duplicates(self)]
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
        self.choice_flag = None
        # TODO remove this eventually
        self.remove_duplicates = False
        self.is_album = True

    def set_candidates(self, cur_artist, cur_album, candidates, rec):
        """Sets the candidates for this album matched by the
        `autotag.tag_album` method.
        """
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
        raise NotImplementedError

    def set_choice(self, choice):
        """Given an AlbumMatch or TrackMatch object or an action constant,
        indicates that an action has been selected for this task.
        """
        # Not part of the task structure:
        assert choice not in (action.MANUAL, action.MANUAL_ID)
        assert choice != action.APPLY  # Only used internally.
        if choice in (action.SKIP, action.ASIS, action.TRACKS, action.ALBUMS):
            self.choice_flag = choice
            self.match = None
        else:
            self.choice_flag = action.APPLY  # Implicit choice.
            self.match = choice

    def save_progress(self):
        """Updates the progress state to indicate that this album has
        finished.
        """
        progress_set(self.toppath, self.paths)

    def save_history(self):
        """Save the directory in the history for incremental imports.
        """
        if self.paths:
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
        return self.choice_flag == action.SKIP

    # Convenient data.

    def chosen_ident(self):
        """Returns identifying metadata about the current choice. For
        albums, this is an (artist, album) pair. For items, this is
        (artist, title). May only be called when the choice flag is ASIS
        (in which case the data comes from the files' current metadata)
        or APPLY (data comes from the choice).
        """
        if self.choice_flag is action.ASIS:
            return (self.cur_artist, self.cur_album)
        elif self.choice_flag is action.APPLY:
            return (self.match.info.artist, self.match.info.album)

    def imported_items(self):
        """Return a list of Items that should be added to the library.
        If this is an album task, return the list of items in the
        selected match or everything if the choice is ASIS. If this is a
        singleton task, return a list containing the item.
        """
        if self.choice_flag == action.ASIS:
            return list(self.items)
        elif self.choice_flag == action.APPLY:
            return self.match.mapping.keys()
        else:
            assert False

    def apply_metadata(self):
        """Copy metadata from match info to the items.
        """
        autotag.apply_metadata(self.match.info, self.match.mapping)

    def finalize(self, session):
        """Move files, save progress and emit plugin event.
        """
        # FIXME the session argument is unfortunate. It should be
        # present as an attribute of the task.

        # Update progress.
        if session.want_resume:
            self.save_progress()
        if config['import']['incremental']:
            self.save_history()
        self.cleanup()
        self._emit_imported(session)

    def cleanup(self):
        """Remove and prune imported paths.
        """
        # FIXME This shouldn't be here. Skipped tasks should be removed from
        # the pipeline.
        if self.should_skip():
            return
        items = self.imported_items()

        # When copying and deleting originals, delete old files.
        if config['import']['copy'] and config['import']['delete']:
            new_paths = [os.path.realpath(item.path) for item in items]
            for old_path in self.old_paths:
                # Only delete files that were actually copied.
                if old_path not in new_paths:
                    util.remove(syspath(old_path), False)
                    self.prune(old_path)

        # When moving, prune empty directories containing the original files.
        elif config['import']['move']:
            for old_path in self.old_paths:
                self.prune(old_path)

    def _emit_imported(self, session):
        # FIXME This shouldn't be here. Skipped tasks should be removed from
        # the pipeline.
        if self.should_skip():
            return
        album = session.lib.get_album(self.album_id)
        plugins.send('album_imported', lib=session.lib, album=album)

    def lookup_candidates(self):
        """Retrieve and store candidates for this album.
        """
        self.set_candidates(*autotag.tag_album(self.items))

    def find_duplicates(self, lib):
        """Return a list of albums from `lib` with the same artist and
        album name as the task.
        """
        artist, album = self.chosen_ident()

        if artist is None:
            # As-is import with no artist. Skip check.
            return []

        duplicates = []
        task_paths = set(i.path for i in self.items if i)
        duplicate_query = dbcore.AndQuery((
            dbcore.MatchQuery('albumartist', artist),
            dbcore.MatchQuery('album', album),
        ))

        for album in lib.albums(duplicate_query):
            # Check whether the album is identical in contents, in which
            # case it is not a duplicate (will be replaced).
            album_paths = set(i.path for i in album.items())
            if album_paths != task_paths:
                duplicates.append(album)
        return duplicates

    def infer_album_fields(self):
        """Make the some album fields equal across `self.items`
        """
        changes = {}

        if self.choice_flag == action.ASIS:
            # Taking metadata "as-is". Guess whether this album is VA.
            plur_albumartist, freq = util.plurality(
                [i.albumartist or i.artist for i in self.items]
            )
            if freq == len(self.items) or \
                (freq > 1 and
                    float(freq) / len(self.items) >= SINGLE_ARTIST_THRESH):
                # Single-artist album.
                changes['albumartist'] = plur_albumartist
                changes['comp'] = False
            else:
                # VA.
                changes['albumartist'] = VARIOUS_ARTISTS
                changes['comp'] = True

        elif self.choice_flag == action.APPLY:
            # Applying autotagged metadata. Just get AA from the first
            # item.
            # FIXME this is overly complicated. Can we assume that
            # `self.items` contains only elements that are not none and
            # at least one of them?
            for item in self.items:
                if item is not None:
                    first_item = item
                    break
            else:
                assert False, "all items are None"
            if not first_item.albumartist:
                changes['albumartist'] = first_item.artist
            if not first_item.mb_albumartistid:
                changes['mb_albumartistid'] = first_item.mb_artistid

        # Apply new metadata.
        for item in self.items:
            if item is not None:
                item.update(changes)

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


class SingletonImportTask(ImportTask):
    """ImportTask for a single track that is not associated to an album.
    """

    def __init__(self, item):
        super(SingletonImportTask, self).__init__(paths=[item.path])
        self.item = item
        self.is_album = False
        self.paths = [item.path]

    def chosen_ident(self):
        assert self.choice_flag in (action.ASIS, action.APPLY)
        if self.choice_flag is action.ASIS:
            return (self.item.artist, self.item.title)
        elif self.choice_flag is action.APPLY:
            return (self.match.info.artist, self.match.info.title)

    def imported_items(self):
        return [self.item]

    def save_progress(self):
        # TODO we should also save progress for singletons
        pass

    def save_history(self):
        # TODO we should also save history for singletons
        pass

    def set_item_candidates(self, candidates, rec):
        """Set the match for a single-item task."""
        assert self.item is not None
        self.candidates = candidates
        self.rec = rec

    def set_candidates(self, cur_artist, cur_album, candidates, rec):
        raise NotImplementedError

    def apply_metadata(self):
        autotag.apply_item_metadata(self.item, self.match.info)

    def _emit_imported(self, session):
        # FIXME This shouldn't be here. Skipped tasks should be removed from
        # the pipeline.
        if self.should_skip():
            return
        for item in self.imported_items():
            plugins.send('item_imported', lib=session.lib, item=item)

    def lookup_candidates(self):
        self.set_item_candidates(*autotag.tag_item(self.item))

    def find_duplicates(self, lib):
        """Return a list of items from `lib` that have the same artist
        and title as the task.
        """
        artist, title = self.chosen_ident()

        found_items = []
        query = dbcore.AndQuery((
            dbcore.MatchQuery('artist', artist),
            dbcore.MatchQuery('title', title),
        ))
        for other_item in lib.items(query):
            # Existing items not considered duplicates.
            if other_item.path != self.item.path:
                found_items.append(other_item)
        return found_items

    def infer_album_fields(self):
        raise NotImplementedError


# FIXME The inheritance relationships are inverted. This is why there
# are so many methods which pass. We should introduce a new
# BaseImportTask class.
class SentinelImportTask(ImportTask):
    """This class marks the progress of an import and does not import
    any items itself.

    If only `toppath` is set the task indicats the end of a top-level
    directory import. If the `paths` argument is givent, too, the task
    indicates the progress in the `toppath` import.
    """

    def __init__(self, toppath=None, paths=None):
        self.toppath = toppath
        self.paths = paths
        # TODO Remove the remaining attributes eventually
        self.items = None
        self.remove_duplicates = False
        self.is_album = True
        self.choice_flag = None

    def save_history(self):
        pass

    def save_progress(self):
        if self.paths is None:
            # "Done" sentinel.
            progress_set(self.toppath, None)
        else:
            # "Directory progress" sentinel for singletons
            progress_set(self.toppath, self.paths)

    def should_skip(self):
        return True

    def set_choice(self, choice):
        raise NotImplementedError

    def set_candidates(self, cur_artist, cur_album, candidates, rec):
        raise NotImplementedError

    def cleanup(self):
        pass

    def _emit_imported(self, session):
        pass


class ArchiveImportTask(SentinelImportTask):
    """Additional methods for handling archives.

    Use when `toppath` points to a `zip`, `tar`, or `rar` archive.
    """

    def __init__(self, toppath):
        super(ArchiveImportTask, self).__init__(toppath)
        self.extracted = False

    @classmethod
    def is_archive(cls, path):
        """Returns true if the given path points to an archive that can
        be handled.
        """
        if not os.path.isfile(path):
            return False

        for path_test, _ in cls.handlers():
            if path_test(path):
                return True
        return False

    @classmethod
    def handlers(cls):
        """Returns a list of archive handlers.

        Each handler is a `(path_test, ArchiveClass)` tuple. `path_test`
        is a function that returns `True` if the given path can be
        handled by `ArchiveClass`. `ArchiveClass` is a class that
        implements the same interface as `tarfile.TarFile`.
        """
        if not hasattr(cls, '_handlers'):
            cls._handlers = []
            from zipfile import is_zipfile, ZipFile
            cls._handlers.append((is_zipfile, ZipFile))
            from tarfile import is_tarfile, TarFile
            cls._handlers.append((is_tarfile, TarFile))
            try:
                from rarfile import is_rarfile, RarFile
            except ImportError:
                pass
            else:
                cls._handlers.append((is_rarfile, RarFile))

        return cls._handlers

    def cleanup(self):
        """Removes the temporary directory the archive was extracted to.
        """
        if self.extracted:
            shutil.rmtree(self.toppath)

    def extract(self):
        """Extracts the archive to a temporary directory and sets
        `toppath` to that directory.
        """
        for path_test, handler_class in self.handlers():
            if path_test(self.toppath):
                break

        try:
            extract_to = mkdtemp()
            archive = handler_class(self.toppath, mode='r')
            archive.extractall(extract_to)
        finally:
            archive.close()
        self.extracted = True
        self.toppath = extract_to


# Full-album pipeline stages.

def read_tasks(session):
    """A generator yielding all the albums (as ImportTask objects) found
    in the user-specified list of paths. In the case of a singleton
    import, yields single-item tasks instead.
    """
    # Look for saved incremental directories.
    if config['import']['incremental']:
        incremental_skipped = 0
        history_dirs = history_get()

    for toppath in session.paths:
        # Extract archives.
        archive_task = None
        if ArchiveImportTask.is_archive(syspath(toppath)):
            if not (config['import']['move'] or config['import']['copy']):
                log.warn("Archive importing requires either "
                         "'copy' or 'move' to be enabled.")
                continue

            log.debug('extracting archive {0}'
                      .format(displayable_path(toppath)))
            archive_task = ArchiveImportTask(toppath)
            try:
                archive_task.extract()
            except Exception as exc:
                log.error('extraction failed: {0}'.format(exc))
                continue

            # Continue reading albums from the extracted directory.
            toppath = archive_task.toppath

        # Check whether the path is to a file.
        if not os.path.isdir(syspath(toppath)):
            try:
                item = library.Item.from_path(toppath)
            except mediafile.UnreadableFileError:
                log.warn(u'unreadable file: {0}'.format(
                    util.displayable_path(toppath)
                ))
                continue
            if config['import']['singletons']:
                yield SingletonImportTask(item)
            else:
                yield ImportTask(toppath, [toppath], [item])
            continue

        # A flat album import merges all items into one album.
        if config['import']['flat'] and not config['import']['singletons']:
            all_items = []
            for _, items in autotag.albums_in_dir(toppath):
                all_items += items
            yield ImportTask(toppath, [toppath], all_items)
            yield SentinelImportTask(toppath)
            continue

        resume_dir = None
        if session.want_resume:
            resume_dir = progress_get(toppath)
            if resume_dir:
                # Either accept immediately or prompt for input to decide.
                if session.want_resume is True or \
                   session.should_resume(toppath):
                    log.warn('Resuming interrupted import of %s' % toppath)
                else:
                    # Clear progress; we're starting from the top.
                    resume_dir = None
                    progress_set(toppath, None)

        # Produce paths under this directory.
        for paths, items in autotag.albums_in_dir(toppath):
            # Skip according to progress.
            if session.want_resume and resume_dir:
                # We're fast-forwarding to resume a previous tagging.
                if paths == resume_dir:
                    # We've hit the last good path! Turn off the
                    # fast-forwarding.
                    resume_dir = None
                continue

            # When incremental, skip paths in the history.
            if config['import']['incremental'] \
               and tuple(paths) in history_dirs:
                log.debug(u'Skipping previously-imported path: %s' %
                          displayable_path(paths))
                incremental_skipped += 1
                continue

            # Yield all the necessary tasks.
            if config['import']['singletons']:
                for item in items:
                    yield SingletonImportTask(item)
                yield SentinelImportTask(toppath, paths)
            else:
                yield ImportTask(toppath, paths, items)

        # Indicate the directory is finished.
        # FIXME hack to delete extracted archives
        if archive_task is None:
            yield SentinelImportTask(toppath)
        else:
            yield archive_task

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
            yield SingletonImportTask(item)

    else:
        # Search for albums.
        for album in session.lib.albums(session.query):
            log.debug('yielding album %i: %s - %s' %
                      (album.id, album.albumartist, album.album))
            items = list(album.items())
            yield ImportTask(None, [album.item_dir()], items)


def lookup_candidates(session):
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
        task.lookup_candidates()


def user_query(session):
    """A coroutine for interfacing with the user about the tagging
    process.

    The coroutine accepts an ImportTask objects. It uses the
    session's `choose_match` method to determine the `action` for
    this task. Depending on the action additional stages are exectuted
    and the processed task is yielded.

    It emits the ``import_task_choice`` event for plugins. Plugins have
    acces to the choice via the ``taks.choice_flag`` property and may
    choose to change it.
    """
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
                    yield SingletonImportTask(item)
                yield SentinelImportTask(task.toppath, task.paths)

            ipl = pipeline.Pipeline([
                emitter(task),
                lookup_candidates(session),
                item_query(session),
            ])
            task = pipeline.multiple(ipl.pull())

        # As albums: group items by albums and create task for each album
        elif task.choice_flag is action.ALBUMS:
            def emitter(task):
                yield task

            ipl = pipeline.Pipeline([
                emitter(task),
                group_albums(session),
                lookup_candidates(session),
                user_query(session)
            ])
            task = pipeline.multiple(ipl.pull())


def resolve_duplicates(session):
    """Check if a task conflicts with items or albums already imported
    and ask the session to resolve this.

    Two separate stages have to be created for albums and singletons
    since `chosen_ident()` returns different types of data.
    """
    task = None
    recent = set()
    while True:
        task = yield task

        if task.choice_flag in (action.ASIS, action.APPLY):
            ident = task.chosen_ident()
            if ident in recent or task.find_duplicates(session.lib):
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
            task.apply_metadata()
            plugins.send('import_task_apply', session=session, task=task)

        # Infer album-level fields.
        if task.is_album:
            task.infer_album_fields()

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
                for album in task.find_duplicates(session.lib):
                    duplicate_items += album.items()
            else:
                duplicate_items = task.find_duplicates(session.lib)
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
                item.try_write()

        # Save new paths.
        with session.lib.transaction():
            for item in items:
                item.store()

        # Plugin event.
        plugins.send('import_task_files', session=session, task=task)


# TODO Get rid of this.
def finalize(session):
    while True:
        task = yield
        task.finalize(session)


# Singleton pipeline stages.

def item_query(session):
    """A coroutine that queries the user for input on single-item
    lookups.
    """
    task = None
    while True:
        task = yield task
        if task.should_skip():
            continue

        choice = session.choose_item(task)
        task.set_choice(choice)
        session.log_choice(task)
        plugins.send('import_task_choice', session=session, task=task)


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
        tasks.append(SentinelImportTask(task.toppath, task.paths))

        task = pipeline.multiple(tasks)
