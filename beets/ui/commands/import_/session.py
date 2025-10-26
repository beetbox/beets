from __future__ import annotations

from collections import Counter
from itertools import chain
from typing import TYPE_CHECKING, NamedTuple, overload

from typing_extensions import override

from beets import autotag, config, importer, logging, plugins
from beets.autotag import Recommendation, TrackMatch
from beets.ui.colors import colorize
from beets.ui.core import input_, input_options, input_yn, print_
from beets.util import displayable_path
from beets.util.units import human_bytes, human_seconds_short

from .display import (
    disambig_string,
    dist_colorize,
    penalty_string,
    show_change,
    show_item_change,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import Any, Literal

    from typing_extensions import Never

    from beets.autotag import AlbumMatch, Proposal
    from beets.library import Album, Item

# Global logger.
log: logging.BeetsLogger = logging.getLogger("beets")


class TerminalImportSession(importer.ImportSession):
    """An import session that runs in a terminal."""

    @override
    def choose_match(
        self, task: importer.ImportTask
    ) -> AlbumMatch | Literal[importer.Action.ASIS, importer.Action.SKIP]:
        """Given an initial autotagging of items, go through an interactive
        dance with the user to ask for a choice of metadata. Returns an
        AlbumMatch object, ASIS, or SKIP.
        """
        # Show what we're tagging.
        print_()

        path_str0: str = displayable_path(task.paths, "\n")
        path_str: str = colorize("import_path", path_str0)
        items_str0: str = f"({len(task.items)} items)"
        items_str: str = colorize("import_path_items", items_str0)
        print_(" ".join([path_str, items_str]))

        # Let plugins display info or prompt the user before we go through the
        # process of selecting candidate.
        results: list[Any] = plugins.send(
            "import_task_before_choice", session=self, task=task
        )
        actions: list[Any] = [action for action in results if action]

        if len(actions) == 1:
            return actions[0]
        elif len(actions) > 1:
            raise plugins.PluginConflictError(
                "Only one handler for `import_task_before_choice` may return "
                "an action."
            )

        # Take immediate action if appropriate.
        action: (
            Literal[
                importer.Action.APPLY,
                importer.Action.ASIS,
                importer.Action.SKIP,
            ]
            | None
        ) = _summary_judgment(task.rec)
        if action == importer.Action.APPLY:
            match: AlbumMatch = task.candidates[0]
            show_change(task.cur_artist, task.cur_album, match)
            return match
        elif action is not None:
            return action

        # Loop until we have a choice.
        while True:
            # Ask for a choice from the user. The result of
            # `choose_candidate` may be an `importer.Action`, an
            # `AlbumMatch` object for a specific selection, or a
            # `PromptChoice`.
            choices: list[PromptChoice] = self._get_choices(task)
            choice: (
                Literal[importer.Action.ASIS, importer.Action.SKIP]
                | AlbumMatch
                | PromptChoice
            ) = choose_candidate(
                task.candidates,
                False,
                task.rec,
                task.cur_artist,
                task.cur_album,
                itemcount=len(task.items),
                choices=choices,
            )

            # Basic choices that require no more action here.
            if choice in (importer.Action.SKIP, importer.Action.ASIS):
                # Pass selection to main control flow.
                return choice

            # Plugin-provided choices. We invoke the associated callback
            # function.
            elif choice in choices:
                assert choice.callback
                post_choice: (
                    Literal[importer.Action.ASIS, importer.Action.SKIP]
                    | Proposal
                ) = choice.callback(self, task)
                if isinstance(post_choice, importer.Action):
                    return post_choice
                elif isinstance(post_choice, autotag.Proposal):
                    # Use the new candidates and continue around the loop.
                    task.candidates = post_choice.candidates
                    task.rec = post_choice.recommendation

            # Otherwise, we have a specific match selection.
            else:
                # We have a candidate! Finish tagging. Here, choice is an
                # AlbumMatch object.
                assert isinstance(choice, autotag.AlbumMatch)
                return choice

    def choose_item(
        self, task: importer.SingletonImportTask
    ) -> Literal[importer.Action.ASIS, importer.Action.SKIP] | TrackMatch:
        """Ask the user for a choice about tagging a single item. Returns
        either an action constant or a TrackMatch object.
        """
        print_()
        print_(displayable_path(task.item.path))
        candidates: Sequence[AlbumMatch | TrackMatch]
        rec: Recommendation | None
        candidates, rec = task.candidates, task.rec

        # Take immediate action if appropriate.
        action: (
            Literal[
                importer.Action.APPLY,
                importer.Action.ASIS,
                importer.Action.SKIP,
            ]
            | None
        ) = _summary_judgment(task.rec)
        if action == importer.Action.APPLY:
            match: TrackMatch = candidates[0]
            show_item_change(task.item, match)
            return match
        elif action is not None:
            return action

        while True:
            # Ask for a choice.
            choices: list[PromptChoice] = self._get_choices(task)
            choice: (
                Literal[importer.Action.ASIS, importer.Action.SKIP]
                | TrackMatch
                | PromptChoice
            ) = choose_candidate(
                candidates, True, rec, item=task.item, choices=choices
            )

            if choice in (importer.Action.SKIP, importer.Action.ASIS):
                return choice

            elif choice in choices:
                assert choice.callback
                post_choice: (
                    Proposal
                    | Literal[importer.Action.ASIS, importer.Action.SKIP]
                ) = choice.callback(self, task)
                if isinstance(post_choice, importer.Action):
                    return post_choice
                elif isinstance(post_choice, autotag.Proposal):
                    candidates = post_choice.candidates
                    rec = post_choice.recommendation

            else:
                # Chose a candidate.
                assert isinstance(choice, autotag.TrackMatch)
                return choice

    def resolve_duplicate(
        self, task: importer.ImportTask, found_duplicates: list[Album]
    ) -> None:
        """Decide what to do when a new album or item seems similar to one
        that's already in the library.
        """
        log.warning(
            "This {} is already in the library!",
            ("album" if task.is_album else "item"),
        )

        sel: int | str
        if config["import"]["quiet"]:
            # In quiet mode, don't prompt -- just skip.
            log.info("Skipping.")
            sel = "s"
        else:
            # Print some detail about the existing and new items so the
            # user can make an informed decision.
            duplicate: Album
            for duplicate in found_duplicates:
                print_(
                    "Old: "
                    + summarize_items(
                        (
                            list(duplicate.items())
                            if task.is_album
                            else [duplicate]
                        ),
                        not task.is_album,
                    )
                )
                if config["import"]["duplicate_verbose_prompt"]:
                    if task.is_album:
                        dup: Item
                        for dup in duplicate.items():
                            print(f"  {dup}")
                    else:
                        print(f"  {duplicate}")

            print_(
                "New: "
                + summarize_items(
                    task.imported_items(),
                    not task.is_album,
                )
            )
            if config["import"]["duplicate_verbose_prompt"]:
                item: Item
                for item in task.imported_items():
                    print(f"  {item}")

            sel = input_options(
                ("Skip new", "Keep all", "Remove old", "Merge all")
            )

        assert isinstance(sel, str)
        if sel == "s":
            # Skip new.
            task.set_choice(importer.Action.SKIP)
        elif sel == "k":
            # Keep both. Do nothing; leave the choice intact.
            pass
        elif sel == "r":
            # Remove old.
            task.should_remove_duplicates = True
        elif sel == "m":
            task.should_merge_duplicates = True
        else:
            assert False

    def should_resume(self, path) -> bool:
        return input_yn(
            f"Import of the directory:\n{displayable_path(path)}\n"
            "was interrupted. Resume (Y/n)?"
        )

    def _get_choices(self, task) -> list[PromptChoice]:
        """Get the list of prompt choices that should be presented to the
        user. This consists of both built-in choices and ones provided by
        plugins.

        The `before_choose_candidate` event is sent to the plugins, with
        session and task as its parameters. Plugins are responsible for
        checking the right conditions and returning a list of `PromptChoice`s,
        which is flattened and checked for conflicts.

        If two or more choices have the same short letter, a warning is
        emitted and all but one choices are discarded, giving preference
        to the default importer choices.

        Returns a list of `PromptChoice`s.
        """
        # Standard, built-in choices.
        choices: list[PromptChoice] = [
            PromptChoice("s", "Skip", lambda s, t: importer.Action.SKIP),
            PromptChoice("u", "Use as-is", lambda s, t: importer.Action.ASIS),
        ]
        if task.is_album:
            choices += [
                PromptChoice(
                    "t", "as Tracks", lambda s, t: importer.Action.TRACKS
                ),
                PromptChoice(
                    "g", "Group albums", lambda s, t: importer.Action.ALBUMS
                ),
            ]
        choices += [
            PromptChoice("e", "Enter search", manual_search),
            PromptChoice("i", "enter Id", manual_id),
            PromptChoice("b", "aBort", abort_action),
        ]

        # Send the before_choose_candidate event and flatten list.
        extra_choices: list[PromptChoice] = list(
            chain(
                *plugins.send(
                    "before_choose_candidate", session=self, task=task
                )
            )
        )

        # Add a "dummy" choice for the other baked-in option, for
        # duplicate checking.
        all_choices: list[PromptChoice] = (
            [
                PromptChoice("a", "Apply", None),
            ]
            + choices
            + extra_choices
        )

        # Check for conflicts.
        short_letters: list[str] = [c.short for c in all_choices]
        if len(short_letters) != len(set(short_letters)):
            # Duplicate short letter has been found.
            duplicates: list[str] = [
                i for i, count in Counter(short_letters).items() if count > 1
            ]
            short: str
            for short in duplicates:
                # Keep the first of the choices, removing the rest.
                dup_choices: list[PromptChoice] = [
                    c for c in all_choices if c.short == short
                ]
                c: PromptChoice
                for c in dup_choices[1:]:
                    log.warning(
                        "Prompt choice '{0.long}' removed due to conflict "
                        "with '{1[0].long}' (short letter: '{0.short}')",
                        c,
                        dup_choices,
                    )
                    extra_choices.remove(c)

        return choices + extra_choices


def summarize_items(items: Sequence[Item], singleton):
    """Produces a brief summary line describing a set of items. Used for
    manually resolving duplicates during import.

    `items` is a list of `Item` objects. `singleton` indicates whether
    this is an album or single-item import (if the latter, them `items`
    should only have one element).
    """
    summary_parts: list[str] = []
    if not singleton:
        summary_parts.append(f"{len(items)} items")

    format_counts: dict[str, int] = {}
    item: Item
    for item in items:
        format_counts[item.format] = format_counts.get(item.format, 0) + 1
    if len(format_counts) == 1:
        # A single format.
        summary_parts.append(items[0].format)
    else:
        # Enumerate all the formats by decreasing frequencies:
        fmt: str
        count: int
        for fmt, count in sorted(
            format_counts.items(),
            key=lambda fmt_and_count: (-fmt_and_count[1], fmt_and_count[0]),
        ):
            summary_parts.append(f"{fmt} {count}")

    if items:
        average_bitrate: float = sum([item.bitrate for item in items]) / len(
            items
        )
        total_duration: int = sum([item.length for item in items])
        total_filesize: int = sum([item.filesize for item in items])
        summary_parts.append(f"{int(average_bitrate / 1000)}kbps")
        if items[0].format == "FLAC":
            sample_bits: str = (
                f"{round(int(items[0].samplerate) / 1000, 1)}kHz"
                f"/{items[0].bitdepth} bit"
            )
            summary_parts.append(sample_bits)
        summary_parts.append(human_seconds_short(total_duration))
        summary_parts.append(human_bytes(total_filesize))

    return ", ".join(summary_parts)


def _summary_judgment(
    rec,
) -> (
    Literal[importer.Action.APPLY, importer.Action.ASIS, importer.Action.SKIP]
    | None
):
    """Determines whether a decision should be made without even asking
    the user. This occurs in quiet mode and when an action is chosen for
    NONE recommendations. Return None if the user should be queried.
    Otherwise, returns an action. May also print to the console if a
    summary judgment is made.
    """

    action: (
        Literal[
            importer.Action.APPLY,
            importer.Action.ASIS,
            importer.Action.SKIP,
        ]
        | None
    )
    if config["import"]["quiet"]:
        if rec == Recommendation.strong:
            return importer.Action.APPLY
        else:
            action = config["import"]["quiet_fallback"].as_choice(
                {
                    "skip": importer.Action.SKIP,
                    "asis": importer.Action.ASIS,
                }
            )
    elif config["import"]["timid"]:
        return None
    elif rec == Recommendation.none:
        action = config["import"]["none_rec_action"].as_choice(
            {
                "skip": importer.Action.SKIP,
                "asis": importer.Action.ASIS,
                "ask": None,
            }
        )
    else:
        return None

    if action == importer.Action.SKIP:
        print_("Skipping.")
    elif action == importer.Action.ASIS:
        print_("Importing as-is.")
    return action


class PromptChoice(NamedTuple):
    short: str
    long: str
    callback: (
        Callable[
            [TerminalImportSession, importer.ImportTask],
            importer.Action | Proposal,
        ]
        | None
    )


@overload
def choose_candidate(
    candidates: Sequence[TrackMatch],
    singleton: Literal[True],
    rec: Recommendation | None,
    cur_artist: str | None = None,
    cur_album: str | None = None,
    item: Item | None = None,
    itemcount: int | None = None,
    choices: list[PromptChoice] = [],
) -> (
    Literal[importer.Action.SKIP, importer.Action.ASIS]
    | TrackMatch
    | PromptChoice
): ...


@overload
def choose_candidate(
    candidates: Sequence[AlbumMatch],
    singleton: Literal[False],
    rec: Recommendation | None,
    cur_artist: str | None = None,
    cur_album: str | None = None,
    item: Item | None = None,
    itemcount: int | None = None,
    choices: list[PromptChoice] = [],
) -> (
    Literal[importer.Action.SKIP, importer.Action.ASIS]
    | AlbumMatch
    | PromptChoice
): ...


def choose_candidate(
    candidates: Sequence[AlbumMatch | TrackMatch],
    singleton: bool,
    rec: Recommendation | None,
    cur_artist: str | None = None,
    cur_album: str | None = None,
    item: Item | None = None,
    itemcount: int | None = None,
    choices: list[PromptChoice] = [],
) -> (
    Literal[importer.Action.SKIP, importer.Action.ASIS]
    | AlbumMatch
    | TrackMatch
    | PromptChoice
):
    """Given a sorted list of candidates, ask the user for a selection
    of which candidate to use. Applies to both full albums and
    singletons  (tracks). Candidates are either AlbumMatch or TrackMatch
    objects depending on `singleton`. for albums, `cur_artist`,
    `cur_album`, and `itemcount` must be provided. For singletons,
    `item` must be provided.

    `choices` is a list of `PromptChoice`s to be used in each prompt.

    Returns one of the following:
    * the result of the choice, which may be SKIP or ASIS
    * a candidate (an AlbumMatch/TrackMatch object)
    * a chosen `PromptChoice` from `choices`
    """
    # Sanity check.
    if singleton:
        assert item is not None
    else:
        assert cur_artist is not None
        assert cur_album is not None

    # Build helper variables for the prompt choices.
    choice_opts: tuple[str, ...] = tuple(c.long for c in choices)
    choice_actions: dict[str, PromptChoice] = {c.short: c for c in choices}

    # Zero candidates.
    sel: int | str
    if not candidates:
        if singleton:
            print_("No matching recordings found.")
        else:
            print_(f"No matching release found for {itemcount} tracks.")
            print_(
                "For help, see: "
                "https://beets.readthedocs.org/en/latest/faq.html#nomatch"
            )
        sel = input_options(choice_opts)
        if isinstance(sel, str) and sel in choice_actions:
            return choice_actions[sel]
        else:
            assert False

    # Is the change good enough?
    bypass_candidates: bool = rec != Recommendation.none
    match: AlbumMatch | TrackMatch = candidates[0]

    while True:
        # Display and choose from candidates.
        require: bool = not rec or (rec <= Recommendation.low)

        if not bypass_candidates:
            # Display list of candidates.
            print_("")
            artist: str | None
            title: str | None
            print_(
                f"Finding tags for {'track' if singleton else 'album'} "
                f'"{artist if singleton and item and (artist := item.artist) else cur_artist} -'
                f' {title if singleton and item and (title := item.title) else cur_album}".'
            )

            print_("  Candidates:")
            i: int
            for i, match in enumerate(candidates):
                # Index, metadata, and distance.
                index0: str = f"{i + 1}."
                index: str = dist_colorize(index0, match.distance)
                dist: str = f"({(1 - match.distance) * 100:.1f}%)"
                distance: str = dist_colorize(dist, match.distance)
                metadata: str = (
                    f"{match.info.artist} -"
                    f" {match.info.title if singleton else match.info.album}"
                )
                if i == 0:
                    metadata = dist_colorize(metadata, match.distance)
                else:
                    metadata = colorize("text_highlight_minor", metadata)
                line1: list[str] = [index, distance, metadata]
                print_(f"  {' '.join(line1)}")

                # Penalties.
                penalties: str | None = penalty_string(match.distance, 3)
                if penalties:
                    print_(f"{' ' * 13}{penalties}")

                # Disambiguation
                disambig: str | None = disambig_string(match.info)
                if disambig:
                    print_(f"{' ' * 13}{disambig}")

            # Ask the user for a choice.
            sel = input_options(choice_opts, numrange=(1, len(candidates)))
            if isinstance(sel, int):  # Numerical selection.
                match = candidates[sel - 1]
                if sel != 1:
                    # When choosing anything but the first match,
                    # disable the default action.
                    require = True
            elif sel == "m":
                pass
            elif sel in choice_actions:
                return choice_actions[sel]

        bypass_candidates = False

        # Show what we're about to do.
        if singleton and isinstance(match, TrackMatch):
            show_item_change(item, match)
        else:
            show_change(cur_artist, cur_album, match)

        # Exact match => tag automatically if we're not in timid mode.
        if rec == Recommendation.strong and not config["import"]["timid"]:
            return match

        # Ask for confirmation.
        default: str | None = config["import"]["default_action"].as_choice(
            {
                "apply": "a",
                "skip": "s",
                "asis": "u",
                "none": None,
            }
        )
        if default is None:
            require = True
        # Bell ring when user interaction is needed.
        if config["import"]["bell"]:
            print_("\a", end="")
        sel = input_options(
            ("Apply", "More candidates") + choice_opts,
            require=require,
            default=default,
        )
        if not isinstance(sel, str):
            continue
        if sel == "a":
            return match
        elif sel in choice_actions:
            return choice_actions[sel]


def manual_search(
    session: TerminalImportSession, task: importer.ImportTask
) -> Proposal:
    """Get a new `Proposal` using manual search criteria.

    Input either an artist and album (for full albums) or artist and
    track name (for singletons) for manual search.
    """
    artist: str = input_("Artist:").strip()
    name: str = input_("Album:" if task.is_album else "Track:").strip()

    if not task.is_album and isinstance(task, importer.SingletonImportTask):
        return autotag.tag_item(task.item, artist, name)
    else:
        prop: Proposal
        _, _, prop = autotag.tag_album(task.items, artist, name)
        return prop


def manual_id(
    session: TerminalImportSession, task: importer.ImportTask
) -> Proposal:
    """Get a new `Proposal` using a manually-entered ID.

    Input an ID, either for an album ("release") or a track ("recording").
    """
    prompt: str = f"Enter {'release' if task.is_album else 'recording'} ID:"
    search_id: str = input_(prompt).strip()

    if not task.is_album and isinstance(task, importer.SingletonImportTask):
        return autotag.tag_item(task.item, search_ids=search_id.split())
    else:
        prop: Proposal
        _, _, prop = autotag.tag_album(task.items, search_ids=search_id.split())
        return prop


def abort_action(
    session: TerminalImportSession, task: importer.ImportTask
) -> Never:
    """A prompt choice callback that aborts the importer."""
    raise importer.ImportAbortError()
