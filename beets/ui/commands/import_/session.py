from __future__ import annotations

from collections import Counter
from itertools import chain
from typing import TYPE_CHECKING, Literal

from beets import config, importer, logging, plugins, ui
from beets.autotag import AlbumMatch, Recommendation, TrackMatch
from beets.importer import DuplicateAction
from beets.library import Album
from beets.util import PromptChoice, displayable_path
from beets.util.color import colorize
from beets.util.units import human_bytes, human_seconds_short

from .display import show_change

if TYPE_CHECKING:
    from beets.autotag import Source
    from beets.importer import AnyImportTask
    from beets.library import AnyLibModel, Item

# Global logger.
log = logging.getLogger("beets")


class TerminalImportSession(importer.ImportSession):
    """An import session that runs in a terminal."""

    def choose_match(self, task):
        """Given an initial autotagging of items, go through an interactive
        dance with the user to ask for a choice of metadata. Returns an
        AlbumMatch object, ASIS, or SKIP.
        """
        # Show what we're tagging.
        ui.print_()

        path_str0 = displayable_path(task.paths, "\n")
        path_str = colorize("import_path", path_str0)
        items_str0 = f"({len(task.items)} items)"
        items_str = colorize("import_path_items", items_str0)
        ui.print_(" ".join([path_str, items_str]))

        # Let plugins display info or prompt the user before we go through the
        # process of selecting candidate.
        results = plugins.send(
            "import_task_before_choice", session=self, task=task
        )
        actions = [action for action in results if action]

        if len(actions) == 1:
            return actions[0]
        if len(actions) > 1:
            raise plugins.PluginConflictError(
                "Only one handler for `import_task_before_choice` may return "
                "an action."
            )

        # Take immediate action if appropriate.
        action = _summary_judgment(task.candidates.recommendation)
        if action == importer.Action.APPLY:
            match = task.candidates[0]
            show_change(task.source, match)
            return match
        if action is not None:
            return action

        # Loop until we have a choice.
        while True:
            # Ask for a choice from the user. The result of
            # `choose_candidate` may be an `importer.Action`, an
            # `AlbumMatch` object for a specific selection, or a
            # `PromptChoice`.
            choices = self._get_choices(task)
            choice = choose_candidate(
                task.candidates,
                task.candidates.recommendation,
                task.source,
                choices=choices,
            )

            # Basic choices that require no more action here.
            if choice in (importer.Action.SKIP, importer.Action.ASIS):
                # Pass selection to main control flow.
                return choice

            # Plugin-provided choices. We invoke the associated callback
            # function.
            if choice in choices:
                post_choice = choice.callback(self, task)
                if isinstance(post_choice, importer.Action):
                    return post_choice
            # Otherwise, we have a specific match selection.
            else:
                # We have a candidate! Finish tagging. Here, choice is an
                # AlbumMatch object.
                assert isinstance(choice, AlbumMatch)
                return choice

    def choose_item(self, task):
        """Ask the user for a choice about tagging a single item. Returns
        either an action constant or a TrackMatch object.
        """
        ui.print_()
        ui.print_(displayable_path(task.item.path))

        # Take immediate action if appropriate.
        action = _summary_judgment(task.candidates.recommendation)
        if action == importer.Action.APPLY:
            match = task.candidates[0]
            show_change(task.source, match)
            return match
        if action is not None:
            return action

        while True:
            # Ask for a choice.
            choices = self._get_choices(task)
            choice = choose_candidate(
                task.candidates,
                task.candidates.recommendation,
                task.source,
                choices=choices,
            )

            if choice in (importer.Action.SKIP, importer.Action.ASIS):
                return choice

            if choice in choices:
                post_choice = choice.callback(self, task)
                if isinstance(post_choice, importer.Action):
                    return post_choice
            else:
                # Chose a candidate.
                assert isinstance(choice, TrackMatch)
                return choice

    def _report_item_summary(
        self, prefix: Literal["Old", "New"], items: list[Item], is_album: bool
    ) -> None:
        ui.print_(f"{prefix}: {summarize_items(items, not is_album)}")
        if self.config["duplicate_verbose_prompt"].get(bool):
            for dup in items:
                print(f"  {dup}")

    def _get_duplicate_action_from_user(
        self,
        task: importer.AnyImportTask,
        found_duplicates: list[Album] | list[Item],
    ) -> str:
        """Decide what to do when a new album or item seems similar to one
        that's already in the library.
        """
        is_album = task.is_album
        log.warning("This {.source.type} is already in the library!", task)

        if config["import"]["quiet"]:
            # In quiet mode, don't prompt -- just skip.
            log.info("Skipping.")
            return "s"
        # Print some detail about the existing and new items so the
        # user can make an informed decision.
        for duplicate in found_duplicates:
            self._report_item_summary(
                "Old",
                (
                    list(duplicate.items())
                    if isinstance(duplicate, Album)
                    else [duplicate]
                ),
                is_album,
            )

        self._report_item_summary("New", task.imported_items(), is_album)

        return ui.input_options(DuplicateAction.strict_options())

    def get_duplicate_action(
        self, task: importer.AnyImportTask, found_duplicates: list[AnyLibModel]
    ) -> DuplicateAction:
        action = super().get_duplicate_action(task, found_duplicates)
        if action is DuplicateAction.ASK:
            return DuplicateAction(
                self._get_duplicate_action_from_user(task, found_duplicates)
            )  # type: ignore[call-arg]

        return action

    def should_resume(self, path):
        return ui.input_yn(
            f"Import of the directory:\n{displayable_path(path)}\n"
            "was interrupted. Resume (Y/n)?"
        )

    def _get_choices(self, task):
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
        choices = [
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
        extra_choices = list(
            chain(
                *plugins.send(
                    "before_choose_candidate", session=self, task=task
                )
            )
        )

        # Add a "dummy" choice for the other baked-in option, for
        # duplicate checking.
        all_choices = [
            PromptChoice("a", "Apply", None),
            *choices,
            *extra_choices,
        ]

        # Check for conflicts.
        short_letters = [c.short for c in all_choices]
        if len(short_letters) != len(set(short_letters)):
            # Duplicate short letter has been found.
            duplicates = [
                i for i, count in Counter(short_letters).items() if count > 1
            ]
            for short in duplicates:
                # Keep the first of the choices, removing the rest.
                dup_choices = [c for c in all_choices if c.short == short]
                for c in dup_choices[1:]:
                    log.warning(
                        "Prompt choice '{0.long}' removed due to conflict "
                        "with '{1[0].long}' (short letter: '{0.short}')",
                        c,
                        dup_choices,
                    )
                    extra_choices.remove(c)

        return choices + extra_choices


def summarize_items(items, singleton):
    """Produces a brief summary line describing a set of items. Used for
    manually resolving duplicates during import.

    `items` is a list of `Item` objects. `singleton` indicates whether
    this is an album or single-item import (if the latter, them `items`
    should only have one element).
    """
    summary_parts = []
    if not singleton:
        summary_parts.append(f"{len(items)} items")

    format_counts = {}
    for item in items:
        format_counts[item.format] = format_counts.get(item.format, 0) + 1
    if len(format_counts) == 1:
        # A single format.
        summary_parts.append(items[0].format)
    else:
        # Enumerate all the formats by decreasing frequencies:
        for fmt, count in sorted(
            format_counts.items(),
            key=lambda fmt_and_count: (-fmt_and_count[1], fmt_and_count[0]),
        ):
            summary_parts.append(f"{fmt} {count}")

    if items:
        average_bitrate = sum([item.bitrate for item in items]) / len(items)
        total_duration = sum([item.length for item in items])
        total_filesize = sum([item.filesize for item in items])
        summary_parts.append(f"{int(average_bitrate / 1000)}kbps")
        if items[0].format == "FLAC":
            sample_bits = (
                f"{round(int(items[0].samplerate) / 1000, 1)}kHz"
                f"/{items[0].bitdepth} bit"
            )
            summary_parts.append(sample_bits)
        summary_parts.append(human_seconds_short(total_duration))
        summary_parts.append(human_bytes(total_filesize))

    return ", ".join(summary_parts)


def _summary_judgment(rec: Recommendation) -> importer.Action | None:
    """Determines whether a decision should be made without even asking
    the user. This occurs in quiet mode and when an action is chosen for
    NONE recommendations. Return None if the user should be queried.
    Otherwise, returns an action. May also print to the console if a
    summary judgment is made.
    """

    action: importer.Action | None
    if config["import"]["quiet"]:
        if rec == Recommendation.strong:
            return importer.Action.APPLY
        action = config["import"]["quiet_fallback"].as_choice(
            {"skip": importer.Action.SKIP, "asis": importer.Action.ASIS}
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
        ui.print_("Skipping.")
    elif action == importer.Action.ASIS:
        ui.print_("Importing as-is.")
    return action


def choose_candidate(candidates, rec, source: Source, choices=[]):
    """Ask the user for a selection of which candidate to use.

    Applies to both full albums and singletons (tracks). Candidates are either
    AlbumMatch or TrackMatch objects.

    `rec` is the autotagging recommendation for the candidates.
    `source` is the Source object describing the item or album being imported.
    `choices` is a list of `PromptChoice`s to be used in each prompt.

    Returns one of the following:
    * the result of the choice, which may be SKIP or ASIS
    * a candidate (an AlbumMatch/TrackMatch object)
    * a chosen `PromptChoice` from `choices`
    """
    # Build helper variables for the prompt choices.
    choice_opts = tuple(c.long for c in choices)
    choice_actions = {c.short: c for c in choices}

    # Zero candidates.
    if not candidates:
        if source.type == "track":
            ui.print_("No matching recordings found.")
        else:
            ui.print_(
                f"No matching release found for {len(source.items)} tracks."
            )
            ui.print_(
                "For help, see: "
                "https://beets.readthedocs.org/en/latest/faq.html#nomatch"
            )
        sel = ui.input_options(choice_opts)
        if sel in choice_actions:
            return choice_actions[sel]
        assert False

    # Is the change good enough?
    bypass_candidates = False
    if rec != Recommendation.none:
        match = candidates[0]
        bypass_candidates = True

    while True:
        # Display and choose from candidates.
        require = rec <= Recommendation.low

        if not bypass_candidates:
            # Display list of candidates.
            ui.print_("")
            ui.print_(f'Finding tags for {source.type} "{source.desc}".')

            ui.print_("  Candidates:")
            for i, match in enumerate(candidates):
                # Index, metadata, and distance.
                dist_color = match.distance.color
                line_parts = [
                    colorize(dist_color, f"{i + 1}."),
                    match.distance.string,
                    colorize(
                        dist_color if i == 0 else "text_highlight_minor",
                        f"{match.info.artist} - {match.info.name}",
                    ),
                ]
                ui.print_(f"  {' '.join(line_parts)}")

                # Penalties.
                if penalty_keys := match.distance.generic_penalty_keys:
                    if len(penalty_keys) > 3:
                        penalty_keys = [*penalty_keys[:3], "..."]
                    penalty_text = colorize(
                        "changed", f"\u2260 {', '.join(penalty_keys)}"
                    )
                    ui.print_(f"{' ' * 13}{penalty_text}")

                # Disambiguation
                if disambig := match.disambig_string:
                    ui.print_(f"{' ' * 13}{disambig}")

            # Ask the user for a choice.
            sel = ui.input_options(choice_opts, numrange=(1, len(candidates)))
            if sel == "m":
                pass
            elif sel in choice_actions:
                return choice_actions[sel]
            else:  # Numerical selection.
                match = candidates[sel - 1]
                if sel != 1:
                    # When choosing anything but the first match,
                    # disable the default action.
                    require = True
        bypass_candidates = False

        # Show what we're about to do.
        show_change(source, match)

        # Exact match => tag automatically if we're not in timid mode.
        if rec == Recommendation.strong and not config["import"]["timid"]:
            return match

        # Ask for confirmation.
        default = config["import"]["default_action"].as_choice(
            {"apply": "a", "skip": "s", "asis": "u", "none": None}
        )
        if default is None:
            require = True
        # Bell ring when user interaction is needed.
        if config["import"]["bell"]:
            ui.print_("\a", end="")
        sel = ui.input_options(
            ("Apply", "More candidates", *choice_opts),
            require=require,
            default=default,
        )
        if sel == "a":
            return match
        if sel in choice_actions:
            return choice_actions[sel]


def manual_search(session, task: AnyImportTask):
    """Resolve candidates using a manual search.

    Input either an artist and album (for full albums) or artist and
    track name (for singletons) for manual search.
    """
    task.candidates.search(
        ui.input_("Artist:").strip(),
        ui.input_(f"{task.source.type.capitalize()}:").strip(),
    )


def manual_id(session, task: AnyImportTask):
    """Resolve candidates using a manually-entered ID.

    Input an ID, either for an album ("release") or a track ("recording").
    """
    task.candidates.search_ids(
        ui.input_(f"Enter {task.source.type} ID:").strip().split()
    )


def abort_action(session, task):
    """A prompt choice callback that aborts the importer."""
    raise importer.ImportAbortError()
