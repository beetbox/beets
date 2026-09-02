from __future__ import annotations

import contextvars
import itertools
import logging
import os
from typing import TYPE_CHECKING, TypeAlias

from beets import config, plugins
from beets.util import MoveOperation, displayable_path, pipeline

from .actions import Action, DuplicateAction
from .tasks import (
    ImportTask,
    ImportTaskFactory,
    SentinelImportTask,
    SingletonImportTask,
    is_subdir_of_any_in_list,
    resolve_upgrade_target,
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


def rescan_tasks(
    session: ImportSession, task: ImportTask
) -> Iterator[BaseImportTask]:
    """Re-read `task`'s directories from disk and yield fresh tasks for
    whatever music is found there now.

    Used to implement the "Rescan directory" prompt choice: the user may
    have manually cleaned up (removed duplicates, deleted junk files, etc.)
    the directory while the import was paused at the prompt, so we must not
    reuse `task.items`, which reflect the stale, pre-cleanup listing.

    Only reachable for album tasks that were discovered directly from the
    filesystem: the "Rescan directory" choice is only ever offered when
    ``task.is_album`` is true and ``task.toppath`` is set (both of which
    exclude singleton-mode sessions), and is withheld for tasks produced
    by "Group albums" (see ``group_albums`` below), whose items are
    grouped by tag rather than by directory and so have no directory
    scope a filesystem rescan could meaningfully reconstruct.

    Discovery itself is never reimplemented here: every group this
    yields comes from the exact same ``albums_in_dir`` / flat-mode /
    single-file logic ``ImportTaskFactory.paths()`` uses for the
    original scan (see below), so the two can't disagree about what
    counts as an album. What *is* reconstructed is the narrowest
    directory that walk needs to start from: rather than always
    re-walking the task's entire ``toppath`` (correct, but potentially
    very expensive -- rescanning one album inside a thousand-album
    library shouldn't mean re-scanning the other 999), this picks the
    smallest directory guaranteed to contain the whole original group
    and re-derives which of that walk's results are the ones this task
    actually came from. That reconstruction is the part genuinely
    particular to rescanning, and it's what the comments below are
    about.
    """
    assert task.toppath is not None

    # `task.paths` records the *original* directories this task was
    # discovered from -- e.g. `[album_root, disc1, disc2]` for a nested
    # multi-disc album, or `[disc1, disc2]` for two disc directories that
    # sit side by side with no wrapping parent, possibly at different
    # depths (`albums_in_dir`'s collapsing only cares whether the next
    # walked directory's *basename* matches the pattern, not how deep it
    # is, so one disc can sit nested a level deeper than its siblings).
    #
    # The only directory guaranteed to be an ancestor of every one of
    # them is their lowest common ancestor -- for a single album
    # directory, or a nested multi-disc album whose disc directories are
    # all children of the album root, that's just the album's own
    # directory; for siblings, it's whatever parent they share. That
    # ancestor is what gets walked, unrestricted, exactly as a normal
    # scan would, so multi-disc collapsing is judged from the real
    # directory listing rather than a fabricated one.
    #
    # That walk can also discover unrelated things living under that
    # ancestor (a third, unrelated album, or loose files dropped there --
    # nothing does, in the single-directory case, since there's nothing
    # else *to* find under a directory that already fully bounds the
    # group), so keep only the group(s) still related to the directories
    # this task originally came from -- either directly (unchanged), or
    # nested under one of them (the user split a directory into
    # subdirectories, or merged one of its own subdirectories back into
    # it).
    #
    # This never needs to treat a group living at the walked ancestor
    # (or at any directory *between* the ancestor and where a given
    # original directory's own collapsing began) as a candidate merge
    # target: `albums_in_dir` only keeps collapsing a group from one
    # walked directory into the next, so any such directory that really
    # was part of reconstructing one of the original groups would
    # itself have been collapsed in and so would already be in
    # `task.paths` -- matched directly, not through an ancestor
    # relationship. A group sitting at one of these directories instead
    # can't be told apart from something that was never part of this
    # task to begin with -- the same ambiguity behind the loose-file
    # and unrelated-sibling cases above. So a user merging original
    # directories' files upward into any of them isn't reconstructed
    # either; rare enough, and just as ambiguous, that it's left as a
    # no-op rescan rather than guessed at -- see
    # `test_rescan_of_sibling_multidisc_album_merged_into_parent_is_not_reimported`.
    scan_root = os.path.commonpath(task.paths)
    discovery_factory = ImportTaskFactory(scan_root, session)
    original_dirs = task.paths
    groups = (
        (dirs, paths)
        for dirs, paths in discovery_factory.paths()
        if any(
            d == o or is_subdir_of_any_in_list(d, [o])
            for d in dirs
            for o in original_dirs
        )
    )

    # The directories actually being re-read here (`task.paths`) may
    # have already been the source of *other*, separately-discovered
    # tasks still waiting further down the pipeline (e.g. a plain,
    # non-disc-named subdirectory holding its own album). This rescan
    # is now the authoritative re-read of those directories, so mark
    # them: `user_query` drops any such stale task rather than letting
    # it get processed a second time alongside whatever this rescan
    # itself finds there. Marking only `task.paths`, not the wider
    # `scan_root` they were walked from, matters when they're siblings
    # under a shared parent -- that parent can hold unrelated content
    # this rescan never touched, which must stay untouched by the mark
    # too.
    generation = session.mark_rescanned(task.paths)

    # Tasks must keep the *original* toppath, not the rescanned
    # directory: it's used for cleanup (pruning stops at `toppath`, so a
    # wrong value would leave the emptied source directory behind after a
    # move) and for resume bookkeeping (progress is recorded and later
    # reset keyed by `toppath`, so a wrong value would leave stale,
    # never-reset progress state behind).
    factory = ImportTaskFactory(task.toppath, session)
    found = False
    for dirs, paths in groups:
        if (album_task := factory.album(paths, dirs)) is not None:
            found = True
            for created_task in album_task.handle_created(session):
                # See `ImportTask.rescan_generation`: this rescan is
                # what's making `created_task` current, so it must not
                # be dropped by the very check that exists to drop
                # everything else `mark_rescanned` above just made
                # stale.
                created_task.rescan_generation = generation
                yield created_task

    if not found:
        log.info(
            "No music found after rescanning: {}", displayable_path(task.paths)
        )

    yield SentinelImportTask(task.toppath, task.paths)


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
            # Items are grouped by tag here, not by directory, so
            # there's no directory scope a filesystem rescan could
            # reconstruct. Set before `handle_created` so a plugin
            # inspecting the task from its `import_task_created`
            # handler sees it too.
            task.is_grouped = True
            for created_task in task.handle_created(session):
                # Re-applied to whatever `handle_created` actually
                # returns, not just `task` itself: a plugin listening
                # for `import_task_created` can replace it with
                # different task objects, which would otherwise
                # silently lose both of these (see
                # `_inherit_rescan_generation`).
                created_task.is_grouped = True
                _inherit_rescan_generation(session, created_task)
                tasks.append(created_task)
        tasks.append(SentinelImportTask(task.toppath, task.paths))

        out = pipeline.multiple(tasks)


@pipeline.mutator_stage
def lookup_candidates(session: ImportSession, task: ImportTask) -> None:
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


def _inherit_rescan_generation(
    session: ImportSession, child: ImportTask
) -> None:
    """Stamp `child` -- a new task freshly built in `user_query` from
    an existing task's items -- with `session`'s current rescan
    generation (see `ImportSession.rescan_generation`).

    Call this on every task actually about to continue through the
    pipeline wherever one task gets split or rebuilt into new ones
    derived from it -- as-Tracks, Group albums, duplicate-merge, and
    anywhere else added in the future -- so it doesn't look stale to
    `user_query`'s `already_rescanned` check relative to whatever's
    already happened in this session. Forgetting this at any one of
    those sites silently drops the derived task's items instead of
    raising an error, so it's easy to miss. Stamping the *session's*
    current generation rather than the source task's own is
    deliberate: for duplicate-merge in particular, the new task's
    paths can include library paths pulled in from anywhere, not just
    the source task's own directory scope, so a completely unrelated
    rescan elsewhere in the same session could otherwise still make it
    look stale.

    Call it on what `ImportTask.handle_created` *returns*, not on the
    task passed into it: a plugin listening for `import_task_created`
    can replace that task with different objects, and stamping only
    the original leaves the replacements at the default `0` -- silently
    dropped all the same, just one step further downstream. See
    `rescan_tasks` for the pattern this follows.
    """
    child.rescan_generation = session.rescan_generation


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

    # A "Rescan directory" choice on an earlier task may have already
    # re-read this task's directory from disk more recently than this
    # task was created (e.g. this task is a plain subdirectory that a
    # rescan of its parent walked back over) -- drop it rather than
    # processing stale, pre-rescan state a second time. Comparing
    # against `task.rescan_generation` (0 unless this task is itself a
    # rescan's output) exempts a rescan's own output from being
    # considered stale by its own marking, while still letting a
    # *later* rescan correctly supersede it.
    if session.already_rescanned(task.paths, task.rescan_generation):
        return pipeline.BUBBLE

    # Ask the user for a choice.
    task.choose_match(session)
    plugins.send("import_task_choice", session=session, task=task)

    # Rescan: re-read the directory from disk and re-run the match.
    if task.choice_flag is Action.RESCAN:
        # `choice_flag` can also be set by a plugin listening for
        # `import_task_choice`, not only via the choices `_get_choices`
        # actually offers. Guard against being asked to rescan a task
        # with no filesystem scope to rescan: a singleton task (e.g.
        # one produced by "as Tracks", whose `paths` is a single item
        # file, not an album directory), one with no `toppath` (e.g. a
        # query- or merge-produced task), or one produced by "Group
        # albums" (see `rescan_tasks`'s docstring).
        if not task.is_album or task.toppath is None or task.is_grouped:
            log.warning(
                "Ignoring a Rescan directory choice for a task with no "
                "directory scope to rescan: {}",
                displayable_path(task.paths),
            )
            task.choice_flag = Action.SKIP
        else:
            return _extend_pipeline(
                rescan_tasks(session, task),
                lookup_candidates(session),
                user_query(session),
            )

    # As-tracks: transition to singleton workflow.
    if task.choice_flag is Action.TRACKS:
        # Set up a little pipeline for dealing with the singletons.
        def emitter(task: ImportTask) -> Iterator[BaseImportTask]:
            for item in task.items:
                task = SingletonImportTask(task.toppath, item)
                for created_task in task.handle_created(session):
                    # Stamped on what `handle_created` actually
                    # returns, not on `task` itself: a plugin listening
                    # for `import_task_created` can replace it with a
                    # different task object, which would otherwise
                    # silently lose this (see
                    # `_inherit_rescan_generation`).
                    _inherit_rescan_generation(session, created_task)
                    yield created_task
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
        _inherit_rescan_generation(session, merged_task)

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
        if task.duplicate_action in (
            DuplicateAction.REMOVE,
            DuplicateAction.UPGRADE,
        ):
            task.remove_duplicates(session.lib)

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


def _resolve_duplicates(session: ImportSession, task: ImportTask) -> None:
    """Check if a task conflicts with items or albums already imported
    and ask the session to resolve this.
    """
    if task.choice_flag in (Action.ASIS, Action.APPLY, Action.RETAG):
        found_duplicates = task.find_duplicates(session.lib)
        if found_duplicates:
            log.debug("found duplicates: {}", [o.id for o in found_duplicates])

            task.duplicate_action = session.get_duplicate_action(
                task, found_duplicates
            )

            if task.duplicate_action is DuplicateAction.UPGRADE:
                if task.apply:
                    # Apply metadata early so items carry their final
                    # (post-tag) identity before we match them against
                    # old library items, which store post-tag metadata
                    # too. `_apply_choice` re-applies it later, which is
                    # harmless (metadata application is idempotent).
                    task.apply_metadata()
                keys = config["import"]["duplicate_keys"]["item"].as_str_seq()
                kept, superseded, old_album_ids = resolve_upgrade_target(
                    task.imported_items(), found_duplicates, keys
                )
                if not kept:
                    log.debug("upgrade: no track was an improvement, declining")
                    task.duplicate_action = DuplicateAction.SKIP
                else:
                    task.apply_upgrade(kept, superseded, old_album_ids)

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
