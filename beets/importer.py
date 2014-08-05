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
from bisect import insort, bisect_left
from contextlib import contextmanager
import shutil

from beets import autotag
from beets import library
from beets import dbcore
from beets import plugins
from beets import util
from beets import config
from beets.util import pipeline
from beets.util import syspath, normpath, displayable_path
from beets.attachments import AttachmentFactory
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

def progress_read():
    state = _open_state()
    return state.setdefault(PROGRESS_KEY, {})


@contextmanager
def progress_write():
    state = _open_state()
    progress = state.setdefault(PROGRESS_KEY, {})
    yield progress
    _save_state(state)


def progress_add(toppath, *paths):
    """Record that the files under all of the `paths` have been imported
    under `toppath`.
    """
    with progress_write() as state:
        imported = state.setdefault(toppath, [])
        for path in paths:
            # Normally `progress_add` will be called with the path
            # argument increasing. This is because of the ordering in
            # `autotag.albums_in_dir`. We take advantage of that to make
            # the code faster
            if imported and imported[len(imported) - 1] <= path:
                imported.append(path)
            else:
                insort(imported, path)


def progress_element(toppath, path):
    """Return whether `path` has been imported in `toppath`.
    """
    state = progress_read()
    if toppath not in state:
        return False
    imported = state[toppath]
    i = bisect_left(imported, path)
    return i != len(imported) and imported[i] == path


def has_progress(toppath):
    """Return `True` if there exist paths that have already been
    imported under `toppath`.
    """
    state = progress_read()
    return toppath in state


def progress_reset(toppath):
    with progress_write() as state:
        if toppath in state:
            del state[toppath]


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
        self.seen_idents = set()
        self._is_resuming = dict()
        self.attachment_factory = AttachmentFactory(lib)
        self.attachment_factory.register_plugins(plugins.find_plugins())

        # Normalize the paths.
        if self.paths:
            self.paths = map(normpath, self.paths)

    def set_config(self, config):
        """Set `config` property from global import config and make
        implied changes.
        """
        # FIXME: Maybe this function should not exist and should instead
        # provide "decision wrappers" like "should_resume()", etc.
        iconfig = dict(config)
        self.config = iconfig

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

        self.want_resume = config['resume'].as_choice([True, False, 'ask'])

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
            if task.should_remove_duplicates:
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
        self.set_config(config['import'])

        # Set up the pipeline.
        if self.query is None:
            stages = [read_tasks(self)]
        else:
            stages = [query_tasks(self)]

        if self.config['group_albums'] and \
           not self.config['singletons']:
            # Split directory tasks into one task for each album
            stages += [group_albums(self)]
        if self.config['autotag']:
            # Only look up and query the user when autotagging.

            # FIXME We should also resolve duplicates when not
            # autotagging.
            stages += [lookup_candidates(self), user_query(self)]
        else:
            stages += [import_asis(self)]
        stages += [apply_choices(self)]
        for stage_func in plugins.import_stages():
            stages.append(plugin_stage(self, stage_func))
        stages += [manipulate_files(self)]
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

    # Incremental and resumed imports

    def already_imported(self, toppath, paths):
        """Returns true if the files belonging to this task have already
        been imported in a previous session.
        """
        if self.is_resuming(toppath) \
           and all(map(lambda p: progress_element(toppath, p), paths)):
            return True
        if self.config['incremental'] \
           and tuple(paths) in self.history_dirs:
            return True

        return False

    @property
    def history_dirs(self):
        if not hasattr(self, '_history_dirs'):
            self._history_dirs = history_get()
        return self._history_dirs

    def is_resuming(self, toppath):
        """Return `True` if user wants to resume import of this path.

        You have to call `ask_resume` first to determine the return value.
        """
        return self._is_resuming.get(toppath, False)

    def ask_resume(self, toppath):
        """If import of `toppath` was aborted in an earlier session, ask
        user if she wants to resume the import.

        Determines the return value of `is_resuming(toppath)`.
        """
        if self.want_resume and has_progress(toppath):
            # Either accept immediately or prompt for input to decide.
            if self.want_resume is True or \
               self.should_resume(toppath):
                log.warn('Resuming interrupted import of %s' % toppath)
                self._is_resuming[toppath] = True
            else:
                # Clear progress; we're starting from the top.
                progress_reset(toppath)


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
        self.should_remove_duplicates = False
        self.is_album = True
        self.attachments = []

    def set_null_candidates(self):
        """Set the candidates to indicate no album match was found.
        """
        self.cur_artist = None
        self.cur_album = None
        self.candidates = None
        self.rec = None

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
        if self.toppath:
            progress_add(self.toppath, *self.paths)

    def save_history(self):
        """Save the directory in the history for incremental imports.
        """
        if self.paths:
            history_add(self.paths)

    # Logical decisions.

    @property
    def apply(self):
        return self.choice_flag == action.APPLY

    @property
    def skip(self):
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

    def duplicate_items(self, lib):
        duplicate_items = []
        for album in self.find_duplicates(lib):
            duplicate_items += album.items()
        return duplicate_items

    def remove_duplicates(self, lib):
        duplicate_items = self.duplicate_items(lib)
        log.debug('removing %i old duplicated items' %
                  len(duplicate_items))
        for item in duplicate_items:
            item.remove()
            if lib.directory in util.ancestry(item.path):
                log.debug(u'deleting duplicate %s' %
                          util.displayable_path(item.path))
                util.remove(item.path)
                util.prune_dirs(os.path.dirname(item.path),
                                lib.directory)

    def finalize(self, session):
        """Save progress, clean up files, and emit plugin event.
        """
        # FIXME the session argument is unfortunate. It should be
        # present as an attribute of the task.

        # Update progress.
        if session.want_resume:
            self.save_progress()
        if session.config['incremental']:
            self.save_history()

        if not self.skip:
            self.cleanup(copy=session.config['copy'],
                         delete=session.config['delete'],
                         move=session.config['move'])
            self._emit_imported(session.lib)

    def cleanup(self, copy=False, delete=False, move=False):
        """Remove and prune imported paths.
        """
        # FIXME Maybe the keywords should be task properties.

        # FIXME This shouldn't be here. Skipping should be handled in
        # the stages.
        if self.skip:
            return
        items = self.imported_items()

        # When copying and deleting originals, delete old files.
        if copy and delete:
            new_paths = [os.path.realpath(item.path) for item in items]
            for old_path in self.old_paths:
                # Only delete files that were actually copied.
                if old_path not in new_paths:
                    util.remove(syspath(old_path), False)
                    self.prune(old_path)

        # When moving, prune empty directories containing the original files.
        elif move:
            for old_path in self.old_paths:
                self.prune(old_path)

    def _emit_imported(self, lib):
        # FIXME This shouldn't be here. Skipping should be handled in
        # the stages.
        if self.skip:
            return
        plugins.send('album_imported', lib=lib, album=self.album)

    def lookup_candidates(self):
        """Retrieve and store candidates for this album.
        """
        artist, album, candidates, recommendation = \
            autotag.tag_album(self.items)
        self.cur_artist = artist
        self.cur_album = album
        self.candidates = candidates
        self.rec = recommendation

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
            if not self.items[0].albumartist:
                changes['albumartist'] = self.items[0].artist
            if not self.items[0].mb_albumartistid:
                changes['mb_albumartistid'] = self.items[0].mb_artistid

        # Apply new metadata.
        for item in self.items:
            item.update(changes)

    def manipulate_files(self, move=False, copy=False, write=False,
                         session=None):
        items = self.imported_items()
        # Save the original paths of all items for deletion and pruning
        # in the next step (finalization).
        self.old_paths = [item.path for item in items]
        for item in items:
            if session.config['move']:
                # Just move the file.
                item.move(False)
            elif session.config['copy']:
                # If it's a reimport, move in-library files and copy
                # out-of-library files. Otherwise, copy and keep track
                # of the old path.
                old_path = item.path
                if self.replaced_items[item]:
                    # This is a reimport. Move in-library files and copy
                    # out-of-library files.
                    if session.lib.directory in util.ancestry(old_path):
                        item.move(False)
                        # We moved the item, so remove the
                        # now-nonexistent file from old_paths.
                        self.old_paths.remove(old_path)
                    else:
                        item.move(True)
                else:
                    # A normal import. Just copy files and keep track of
                    # old paths.
                    item.move(True)

            if session.config['write'] and self.apply:
                item.try_write()

        with session.lib.transaction():
            for item in self.imported_items():
                item.store()

        for a in self.attachments:
            if move or copy:
                a.move(copy=copy)

        plugins.send('import_task_files', session=session, task=self)

    def add(self, lib):
        """Add the items as an album to the library and remove replaced items.
        """
        with lib.transaction():
            self.remove_replaced(lib)
            # FIXME set album earlier so we can use it to create
            # attachmenst
            self.album = lib.add_album(self.imported_items())
            for a in self.attachments:
                a.entity = self.album
                a.add(lib)

    def remove_replaced(self, lib):
        """Removes all the items from the library that have the same
        path as an item from this task.

        Records the replaced items in the `replaced_items` dictionary
        """
        self.replaced_items = defaultdict(list)
        for item in self.imported_items():
            dup_items = list(lib.items(
                dbcore.query.BytesQuery('path', item.path)
            ))
            self.replaced_items[item] = dup_items
            for dup_item in dup_items:
                log.debug('replacing item %i: %s' %
                          (dup_item.id, displayable_path(item.path)))
                dup_item.remove()
        log.debug('%i of %i items replaced' % (len(self.replaced_items),
                                               len(self.imported_items())))

    def choose_match(self, session):
        """Ask the session which match should apply and apply it.
        """
        choice = session.choose_match(self)
        self.set_choice(choice)
        session.log_choice(self)

    def reload(self):
        """Reload albums and items from the database.
        """
        for item in self.imported_items():
            item.load()
        self.album.load()

    def discover_attachments(self, factory):
        """Return a list of known attachments for files in the album's directory.

        Saves the list in the `attachments` attribute.
        """
        # FIXME the album model should already be available so we can
        # attach the attachment. This also means attachments must handle
        # unpersisted entities.
        for album_path in self.paths:
            for path in factory.discover(album_path):
                self.attachments.extend(factory.detect(path))
        return self.attachments

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

    def __init__(self, toppath, item):
        super(SingletonImportTask, self).__init__(toppath, [item.path])
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

    def apply_metadata(self):
        autotag.apply_item_metadata(self.item, self.match.info)

    def _emit_imported(self, lib):
        # FIXME This shouldn't be here. Skipped tasks should be removed from
        # the pipeline.
        if self.skip:
            return
        for item in self.imported_items():
            plugins.send('item_imported', lib=lib, item=item)

    def lookup_candidates(self):
        candidates, recommendation = autotag.tag_item(self.item)
        self.candidates = candidates
        self.rec = recommendation

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

    duplicate_items = find_duplicates

    def add(self, lib):
        with lib.transaction():
            self.remove_replaced(lib)
            lib.add(self.item)
            for a in self.attachments:
                a.entity = self.item
                a.add(lib)

    def infer_album_fields(self):
        raise NotImplementedError

    def choose_match(self, session):
        """Ask the session which match should apply and apply it.
        """
        choice = session.choose_item(self)
        self.set_choice(choice)
        session.log_choice(self)

    def reload(self):
        self.item.load()


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
        self.should_remove_duplicates = False
        self.is_album = True
        self.choice_flag = None

    def save_history(self):
        pass

    def save_progress(self):
        if self.paths is None:
            # "Done" sentinel.
            progress_reset(self.toppath)
        else:
            # "Directory progress" sentinel for singletons
            progress_add(self.toppath, *self.paths)

    def skip(self):
        return True

    def set_choice(self, choice):
        raise NotImplementedError

    def cleanup(self, **kwargs):
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

    def cleanup(self, **kwargs):
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
    skipped = 0
    for toppath in session.paths:

        # Determine if we want to resume import of the toppath
        session.ask_resume(toppath)

        # Extract archives.
        archive_task = None
        if ArchiveImportTask.is_archive(syspath(toppath)):
            if not (session.config['move'] or session.config['copy']):
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
            # FIXME remove duplicate code. We could put the debug
            # statement into `session.alread_imported` but I don't feel
            # comfortable triggering an action in a query.
            if session.already_imported(toppath, toppath):
                log.debug(u'Skipping previously-imported path: {0}'
                          .format(displayable_path(toppath)))
                skipped += 1
                continue

            try:
                item = library.Item.from_path(toppath)
            except mediafile.UnreadableFileError:
                log.warn(u'unreadable file: {0}'.format(
                    util.displayable_path(toppath)
                ))
                continue
            if session.config['singletons']:
                yield SingletonImportTask(toppath, item)
            else:
                yield ImportTask(toppath, [toppath], [item])
            continue

        # A flat album import merges all items into one album.
        if session.config['flat'] and not session.config['singletons']:
            all_items = []
            for _, items in autotag.albums_in_dir(toppath):
                all_items += items
            if all_items:
                if session.already_imported(toppath, [toppath]):
                    log.debug(u'Skipping previously-imported path: {0}'
                              .format(displayable_path(toppath)))
                    skipped += 1
                    continue
                yield ImportTask(toppath, [toppath], all_items)
                yield SentinelImportTask(toppath)
            continue

        # Produce paths under this directory.
        for paths, items in autotag.albums_in_dir(toppath):
            if session.config['singletons']:
                for item in items:
                    if session.already_imported(toppath, [item.path]):
                        log.debug(u'Skipping previously-imported path: {0}'
                                  .format(displayable_path(paths)))
                        skipped += 1
                        continue
                    yield SingletonImportTask(toppath, item)
                yield SentinelImportTask(toppath, paths)

            else:
                if session.already_imported(toppath, paths):
                    log.debug(u'Skipping previously-imported path: {0}'
                              .format(displayable_path(paths)))
                    skipped += 1
                    continue
                yield ImportTask(toppath, paths, items)

        # Indicate the directory is finished.
        # FIXME hack to delete extracted archives
        if archive_task is None:
            yield SentinelImportTask(toppath)
        else:
            yield archive_task

    # Show skipped directories.
    if skipped:
        log.info(u'Skipped {0} directories.'.format(skipped))


def query_tasks(session):
    """A generator that works as a drop-in-replacement for read_tasks.
    Instead of finding files from the filesystem, a query is used to
    match items from the library.
    """
    if session.config['singletons']:
        # Search for items.
        for item in session.lib.items(session.query):
            yield SingletonImportTask(None, item)

    else:
        # Search for albums.
        for album in session.lib.albums(session.query):
            log.debug('yielding album %i: %s - %s' %
                      (album.id, album.albumartist, album.album))
            items = list(album.items())

            # Clear IDs from re-tagged items so they appear "fresh" when
            # we add them back to the library.
            for item in items:
                item.id = None
                item.album_id = None

            yield ImportTask(None, [album.item_dir()], items)


@pipeline.mutator_stage
def lookup_candidates(session, task):
    """A coroutine for performing the initial MusicBrainz lookup for an
    album. It accepts lists of Items and yields
    (items, cur_artist, cur_album, candidates, rec) tuples. If no match
    is found, all of the yielded parameters (except items) are None.
    """
    if task.skip:
        # FIXME This gets duplicated a lot. We need a better
        # abstraction.
        return

    plugins.send('import_task_start', session=session, task=task)
    log.debug('Looking up: %s' % displayable_path(task.paths))
    task.lookup_candidates()


@pipeline.stage
def user_query(session, task):
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
    if task.skip:
        return task

    # Ask the user for a choice.
    task.choose_match(session)
    plugins.send('import_task_choice', session=session, task=task)

    # As-tracks: transition to singleton workflow.
    if task.choice_flag is action.TRACKS:
        # Set up a little pipeline for dealing with the singletons.
        def emitter(task):
            for item in task.items:
                yield SingletonImportTask(task.toppath, item)
            yield SentinelImportTask(task.toppath, task.paths)

        ipl = pipeline.Pipeline([
            emitter(task),
            lookup_candidates(session),
            user_query(session),
        ])
        return pipeline.multiple(ipl.pull())

    # As albums: group items by albums and create task for each album
    if task.choice_flag is action.ALBUMS:
        ipl = pipeline.Pipeline([
            iter([task]),
            group_albums(session),
            lookup_candidates(session),
            user_query(session)
        ])
        return pipeline.multiple(ipl.pull())

    resolve_duplicates(session, task)
    return task


def resolve_duplicates(session, task):
    """Check if a task conflicts with items or albums already imported
    and ask the session to resolve this.
    """
    if task.choice_flag in (action.ASIS, action.APPLY):
        ident = task.chosen_ident()
        if ident in session.seen_idents or task.find_duplicates(session.lib):
            session.resolve_duplicate(task)
            session.log_choice(task, True)
        session.seen_idents.add(ident)


@pipeline.mutator_stage
def import_asis(session, task):
    """Select the `action.ASIS` choice for all tasks.

    This stage replaces the initial_lookup and user_query stages
    when the importer is run without autotagging.
    """
    if task.skip:
        return

    log.info(displayable_path(task.paths))

    # Behave as if ASIS were selected.
    task.set_null_candidates()
    task.set_choice(action.ASIS)


@pipeline.mutator_stage
def apply_choices(session, task):
    """A coroutine for applying changes to albums and singletons during
    the autotag process.
    """
    if task.skip:
        return

    # Change metadata.
    if task.apply:
        task.apply_metadata()
        plugins.send('import_task_apply', session=session, task=task)

    # Infer album-level fields.
    if task.is_album:
        task.infer_album_fields()

    task.discover_attachments(session.attachment_factory)
    task.add(session.lib)


@pipeline.mutator_stage
def plugin_stage(session, func, task):
    """A coroutine (pipeline stage) that calls the given function with
    each non-skipped import task. These stages occur between applying
    metadata changes and moving/copying/writing files.
    """
    if task.skip:
        return

    func(session, task)

    # Stage may modify DB, so re-load cached item data.
    # FIXME Importer plugins should not modify the database but instead
    # the albums and items attached to tasks.
    task.reload()


@pipeline.stage
def manipulate_files(session, task):
    """A coroutine (pipeline stage) that performs necessary file
    manipulations *after* items have been added to the library and
    finalizes each task.
    """
    if not task.skip:
        if task.should_remove_duplicates:
            task.remove_duplicates(session.lib)

        task.manipulate_files(
            move=session.config['move'],
            copy=session.config['copy'],
            write=session.config['write'],
            session=session,
        )

    # Progress, cleanup, and event.
    task.finalize(session)


def group_albums(session):
    """Group the items of a task by albumartist and album name and create a new
    task for each album. Yield the tasks as a multi message.
    """
    def group(item):
        return (item.albumartist or item.artist, item.album)

    task = None
    while True:
        task = yield task
        if task.skip:
            continue
        tasks = []
        for _, items in itertools.groupby(task.items, group):
            tasks.append(ImportTask(items=list(items)))
        tasks.append(SentinelImportTask(task.toppath, task.paths))

        task = pipeline.multiple(tasks)
