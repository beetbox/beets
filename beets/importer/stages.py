from __future__ import annotations

import contextvars
import itertools
import logging
from typing import TYPE_CHECKING, TypeAlias

from beets import config, dbcore, plugins
from beets.util import MoveOperation, displayable_path, pipeline
from beets.util.color import colorize

from .actions import Action, DuplicateAction
from .tasks import (
    ImportTask,
    ImportTaskFactory,
    SentinelImportTask,
    SingletonImportTask,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable, Iterator

    from beets import library

    from .session import ImportSession
    from .tasks import BaseImportTask

    StageMessage: TypeAlias = BaseImportTask | pipeline.MultiMessage | None
    StageCoro: TypeAlias = Generator[StageMessage, ImportTask, None]
    StageReturn: TypeAlias = ImportTask | pipeline.MultiMessage | str

# Global logger.
log = logging.getLogger("beets")

# ---------------------------- Producer functions ---------------------------- #
# Functions that are called first i.e. they generate import tasks


def read_tasks(session: ImportSession) -> Iterator[BaseImportTask]:
    """A generator yielding all the albums (as ImportTask objects) found
    in the user-specified list of paths. In the case of a singleton
    import, yields single-item tasks instead.
    """
    skipped = 0

    for toppath in session.paths:
        # Check whether we need to resume the import.
        session.ask_resume(toppath)

        # Generate tasks.
        task_factory = ImportTaskFactory(toppath, session)
        yield from task_factory.tasks()
        skipped += task_factory.skipped

        if not task_factory.imported:
            log.warning("No files imported from {}", displayable_path(toppath))

    # Show skipped directories (due to incremental/resume).
    if skipped:
        log.info("Skipped {} paths.", skipped)


def query_tasks(session: ImportSession) -> Iterator[BaseImportTask]:
    """A generator that works as a drop-in-replacement for read_tasks.
    Instead of finding files from the filesystem, a query is used to
    match items from the library.
    """
    task: BaseImportTask
    if session.config["singletons"]:
        # Search for items.
        for item in session.lib.items(session.query):
            task = SingletonImportTask(None, item)
            for task in task.handle_created(session):
                yield task

    else:
        # Search for albums.
        for album in session.lib.albums(session.query):
            log.debug(
                "yielding album {0.id}: {0.albumartist} - {0.album}", album
            )
            items = list(album.items())
            _freshen_items(items)

            task = ImportTask(None, [album.item_dir()], items)
            for task in task.handle_created(session):
                yield task


# ---------------------------------- Stages ---------------------------------- #
# Functions that process import tasks, may transform or filter them
# They are chained together in the pipeline e.g. stage2(stage1(task)) -> task


def group_albums(session: ImportSession) -> StageCoro:
    """A pipeline stage that groups the items of each task into albums
    using their metadata.

    Groups are identified using their artist and album fields. The
    pipeline stage emits new album tasks for each discovered group.
    """

    def group(item: library.Item) -> tuple[str | None, str | None]:
        return (item.albumartist or item.artist, item.album)

    out: StageMessage = None
    while True:
        task = yield out
        if task.skip:
            out = task
            continue
        tasks = []
        sorted_items: list[library.Item] = sorted(task.items, key=group)
        for _, items in itertools.groupby(sorted_items, group):
            l_items = list(items)
            task = ImportTask(task.toppath, [i.path for i in l_items], l_items)
            tasks += task.handle_created(session)
        tasks.append(SentinelImportTask(task.toppath, task.paths))

        out = pipeline.multiple(tasks)


@pipeline.mutator_stage
    """Resolve tracks of an album that already exist in the library.

    When ``import.duplicate_track_resolution`` is enabled, each item of an
    album import is checked against the library using
    ``import.duplicate_keys.item``. Matched tracks are resolved according to
    ``import.duplicate_track_action`` (which falls back to
    ``import.duplicate_action`` when unset):

    * ``skip`` drops the duplicate tracks and adds the remaining new tracks to
      the existing album they belong to (if every track is a duplicate, the
      whole album is skipped);
    * ``remove`` removes the matching old library items;
    * ``keep`` (and ``merge``) import everything as-is;
    * ``ask`` prompts the session for one of the above.

    This runs before :func:`lookup_candidates` so that dropped tracks are
    excluded from the autotag match. Singleton imports are handled by the
    regular duplicate resolution and are ignored here.
    """
    if (
        task.skip
        or not task.is_album
        or not task.items
        or not config["import"]["duplicate_track_resolution"].get(bool)
    ):
        return

    keys = config["import"]["duplicate_keys"]["item"].as_str_seq()
    if not keys:
        return

    # Map each incoming item to the existing library items it duplicates.
    duplicates: dict[library.Item, list[library.Item]] = {}
    for item in task.items:
        if not any(item.get(k) for k in keys):
            continue
        matches = _find_track_duplicates(session.lib, item, keys)
        if matches:
            duplicates[item] = matches

    if not duplicates:
        return

    action = _track_duplicate_action()
    if action is DuplicateAction.ASK:
        action = session.resolve_track_duplicates(task, duplicates)

    if action is DuplicateAction.SKIP:
        for item in duplicates:
            log.info(
                colorize("text_warning", "Skipping duplicate track: {}"),
                displayable_path(item.path),
            )
            task.items.remove(item)
        if not task.items:
            # Every track was a duplicate: skip the whole album.
            log.info(
                colorize(
                    "text_warning",
                    "Skipping album, all tracks are duplicates: {}",
                ),
                next(iter(duplicates)).album,
            )
            task.set_choice(Action.SKIP)
            return
        # Only some tracks were duplicates; we have already dropped them, so
        # don't let the album-level check skip the rest.
        task.duplicate_tracks_resolved = True
        # Fold the remaining new tracks into the existing album the matched
        # duplicates belong to. Tracks matching a *singleton* are skipped
        # individually but do not affect the fold target (their ``album_id``
        # is ``None``), so a mix of album-member and singleton matches still
        # completes the album. Only when the matched album members span more
        # than one album -- or none of the matches belong to an album at all
        # -- are the new tracks imported as their own album.
        album_ids = {
            match.album_id
            for matches in duplicates.values()
            for match in matches
            if match.album_id is not None
        }
        if len(album_ids) == 1:
            task.fold_into_album_id = album_ids.pop()
        else:
            log.warning(
                "cannot fold tracks into a single existing album; "
                "importing them as a new album"
            )
    elif action is DuplicateAction.REMOVE:
        for matches in duplicates.values():
            task.duplicate_track_items_to_remove.extend(matches)
        task.duplicate_tracks_resolved = True
    # KEEP and MERGE leave the incoming tracks untouched; whole-album
    # duplicates are still handled by the regular resolution stage.


@pipeline.mutator_stage
def lookup_candidates(session: ImportSession, task: ImportTask):
    """A coroutine for performing the initial MusicBrainz lookup for an
    album. It accepts lists of Items and yields
    (items, cur_artist, cur_album, candidates, rec) tuples. If no match
    is found, all of the yielded parameters (except items) are None.
    """
    if task.skip:
        # FIXME This gets duplicated a lot. We need a better
        # abstraction.
        return

    plugins.send("import_task_start", session=session, task=task)
    log.debug("Looking up: {}", displayable_path(task.paths))

    # Restrict the initial lookup to IDs specified by the user via the -m
    # option. Currently all the IDs are passed onto the tasks directly.
    task.lookup_candidates(session.config["search_ids"].as_str_seq())


@pipeline.stage
def user_query(session: ImportSession, task: ImportTask) -> StageReturn:
    """A coroutine for interfacing with the user about the tagging
    process.

    The coroutine accepts an ImportTask objects. It uses the
    session's `choose_match` method to determine the `action` for
    this task. Depending on the action additional stages are executed
    and the processed task is yielded.

    It emits the ``import_task_choice`` event for plugins. Plugins have
    access to the choice via the ``task.choice_flag`` property and may
    choose to change it.
    """
    if task.skip:
        return task

    if session.already_merged(task.paths):
        return pipeline.BUBBLE

    # Ask the user for a choice.
    task.choose_match(session)
    plugins.send("import_task_choice", session=session, task=task)

    # As-tracks: transition to singleton workflow.
    if task.choice_flag is Action.TRACKS:
        # Set up a little pipeline for dealing with the singletons.
        def emitter(task: ImportTask) -> Iterator[BaseImportTask]:
            for item in task.items:
                task = SingletonImportTask(task.toppath, item)
                yield from task.handle_created(session)
            yield SentinelImportTask(task.toppath, task.paths)

        return _extend_pipeline(
            emitter(task), lookup_candidates(session), user_query(session)
        )

    # As albums: group items by albums and create task for each album
    if task.choice_flag is Action.ALBUMS:
        return _extend_pipeline(
            [task],
            group_albums(session),
            lookup_candidates(session),
            user_query(session),
        )

    _resolve_duplicates(session, task)

    if task.duplicate_action is DuplicateAction.MERGE:
        # Create a new task for tagging the current items
        # and duplicates together
        duplicate_items = task.duplicate_items(session.lib)

        # Duplicates would be reimported so make them look "fresh"
        _freshen_items(duplicate_items)
        duplicate_paths = [item.path for item in duplicate_items]

        # Record merged paths in the session so they are not reimported
        session.mark_merged(duplicate_paths)

        merged_task = ImportTask(
            None, task.paths + duplicate_paths, task.items + duplicate_items
        )

        return _extend_pipeline(
            [merged_task], lookup_candidates(session), user_query(session)
        )

    _apply_choice(session, task)
    return task


@pipeline.mutator_stage
def import_asis(session: ImportSession, task: ImportTask) -> None:
    """Select the `action.ASIS` choice for all tasks.

    This stage replaces the initial_lookup and user_query stages
    when the importer is run without autotagging.
    """
    if task.skip:
        return

    log.info("{}", displayable_path(task.paths))
    task.set_choice(Action.ASIS)
    _resolve_duplicates(session, task)
    _apply_choice(session, task)


@pipeline.mutator_stage
def plugin_stage(
    session: ImportSession,
    func: Callable[[ImportSession, ImportTask], None],
    task: ImportTask,
) -> None:
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
def log_files(session: ImportSession, task: ImportTask) -> None:
    """A coroutine (pipeline stage) to log each file to be imported."""
    if isinstance(task, SingletonImportTask):
        log.info("Singleton: {}", displayable_path(task.item["path"]))
    elif task.items:
        log.info("Album: {}", displayable_path(task.paths[0]))
        for item in task.items:
            log.info("  {}", displayable_path(item["path"]))


# --------------------------------- Consumer --------------------------------- #
# Anything that should be placed last in the pipeline
# In theory every stage could be a consumer, but in practice there are some
# functions which are typically placed last in the pipeline


@pipeline.stage
def manipulate_files(session: ImportSession, task: ImportTask) -> None:
    """A coroutine (pipeline stage) that performs necessary file
    manipulations *after* items have been added to the library and
    finalizes each task.
    """
    if not task.skip:
        if task.duplicate_action is DuplicateAction.REMOVE:
            task.remove_duplicates(session.lib)

        if task.duplicate_track_items_to_remove:
            task.remove_duplicate_track_items(session.lib)

        if session.config["move"]:
            operation = MoveOperation.MOVE
        elif session.config["copy"]:
            operation = MoveOperation.COPY
        elif session.config["link"]:
            operation = MoveOperation.LINK
        elif session.config["hardlink"]:
            operation = MoveOperation.HARDLINK
        elif session.config["reflink"].get() == "auto":
            operation = MoveOperation.REFLINK_AUTO
        elif session.config["reflink"]:
            operation = MoveOperation.REFLINK
        else:
            operation = None

        task.manipulate_files(
            session=session,
            operation=operation,
            write=session.config["write"].get(bool),
        )

    # Progress, cleanup, and event.
    task.finalize(session)


# ---------------------------- Utility functions ----------------------------- #
# Private functions only used in the stages above


def _apply_choice(session: ImportSession, task: ImportTask) -> None:
    """Apply the task's choice to the Album or Item it contains and add
    it to the library.
    """
    if task.skip:
        return

    # Change metadata.
    if task.apply:
        task.apply_metadata()
        plugins.send("import_task_apply", session=session, task=task)

    task.add(session.lib)

    # If ``set_fields`` is set, set those fields to the
    # configured values.
    # NOTE: This cannot be done before the ``task.add()`` call above,
    # because then the ``ImportTask`` won't have an `album` for which
    # it can set the fields.
    if config["import"]["set_fields"]:
        task.set_fields(session.lib)


def _track_duplicate_action() -> DuplicateAction:
    """Return the configured :class:`DuplicateAction` for per-track resolution.

    Uses ``import.duplicate_track_action`` when set, otherwise falls back to
    ``import.duplicate_action``.
    """
    cfg = config["import"]
    view = (
        cfg["duplicate_track_action"]
        if cfg["duplicate_track_action"].get()
        else cfg["duplicate_action"]
    )
    choice = view.as_choice(DuplicateAction.choices())
    return DuplicateAction(choice)  # type: ignore[call-arg]


def _find_track_duplicates(
    lib: library.Library, item: library.Item, keys: list[str]
) -> list[library.Item]:
    """Return library items matching `item` on all `keys`, excluding the
    item itself (so re-imports do not match their own files).

    Unlike :meth:`Item.duplicates_query`, this matches *every* library item,
    including tracks that belong to an album -- not just singletons -- so a
    track is caught regardless of how it was originally imported.
    """
    query = dbcore.AndQuery(
        [item.field_query(k, item.get(k), dbcore.MatchQuery) for k in keys]
    )
    return [other for other in lib.items(query) if other.path != item.path]


def _resolve_duplicates(session: ImportSession, task: ImportTask):
    """Check if a task conflicts with items or albums already imported
    and ask the session to resolve this.
    """
    if task.duplicate_tracks_resolved:
        # Per-track duplicate resolution already pruned (or recorded for
        # removal) the tracks of this album that exist in the library; the
        # rest are new and should be imported without a whole-album skip.
        return

    if task.choice_flag in (Action.ASIS, Action.APPLY, Action.RETAG):
        found_duplicates = task.find_duplicates(session.lib)
        if found_duplicates:
            log.debug("found duplicates: {}", [o.id for o in found_duplicates])

            task.duplicate_action = session.get_duplicate_action(
                task, found_duplicates
            )

            session.log_choice(task, True)


def _freshen_items(items: Iterable[library.Item]) -> None:
    # Clear IDs from re-tagged items so they appear "fresh" when
    # we add them back to the library.
    for item in items:
        item.id = None
        item.album_id = None


def _extend_pipeline(
    tasks: Iterable[BaseImportTask], *stages: StageCoro
) -> pipeline.MultiMessage:
    # Return pipeline extension for stages with list of tasks
    ipl: pipeline.Pipeline[StageMessage, StageCoro] = pipeline.Pipeline(
        [iter(tasks), *list(stages)]
    )
    ctx = contextvars.copy_context()

    def _ctx_iter() -> Iterator[StageMessage]:
        gen = ipl.pull()
        while True:
            try:
                yield ctx.run(next, gen)
            except StopIteration:
                return

    return pipeline.multiple(_ctx_iter())
