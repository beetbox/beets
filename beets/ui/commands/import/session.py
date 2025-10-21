from collections import Counter
from itertools import chain
from typing import Any, NamedTuple

from beets import autotag, config, importer, logging, plugins, ui
from beets.autotag import Recommendation
from beets.util import displayable_path
from beets.util.units import human_bytes, human_seconds_short
from beetsplug.bareasc import print_

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
        path_str = ui.colorize("import_path", path_str0)
        items_str0 = f"({len(task.items)} items)"
        items_str = ui.colorize("import_path_items", items_str0)
        ui.print_(" ".join([path_str, items_str]))

        # Let plugins display info or prompt the user before we go through the
        # process of selecting candidate.
        results = plugins.send(
            "import_task_before_choice", session=self, task=task
        )
        actions = [action for action in results if action]

        if len(actions) == 1:
            return actions[0]
        elif len(actions) > 1:
            raise plugins.PluginConflictError(
                "Only one handler for `import_task_before_choice` may return "
                "an action."
            )

        # Take immediate action if appropriate.
        action = _summary_judgment(task.rec)
        if action == importer.Action.APPLY:
            match = task.candidates[0]
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
            choices = self._get_choices(task)
            choice = choose_candidate(
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
                post_choice = choice.callback(self, task)
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

    def choose_item(self, task):
        """Ask the user for a choice about tagging a single item. Returns
        either an action constant or a TrackMatch object.
        """
        ui.print_()
        ui.print_(displayable_path(task.item.path))
        candidates, rec = task.candidates, task.rec

        # Take immediate action if appropriate.
        action = _summary_judgment(task.rec)
        if action == importer.Action.APPLY:
            match = candidates[0]
            show_item_change(task.item, match)
            return match
        elif action is not None:
            return action

        while True:
            # Ask for a choice.
            choices = self._get_choices(task)
            choice = choose_candidate(
                candidates, True, rec, item=task.item, choices=choices
            )

            if choice in (importer.Action.SKIP, importer.Action.ASIS):
                return choice

            elif choice in choices:
                post_choice = choice.callback(self, task)
                if isinstance(post_choice, importer.Action):
                    return post_choice
                elif isinstance(post_choice, autotag.Proposal):
                    candidates = post_choice.candidates
                    rec = post_choice.recommendation

            else:
                # Chose a candidate.
                assert isinstance(choice, autotag.TrackMatch)
                return choice

    def resolve_duplicate(self, task, found_duplicates):
        """Decide what to do when a new album or item seems similar to one
        that's already in the library.
        """
        log.warning(
            "This {} is already in the library!",
            ("album" if task.is_album else "item"),
        )

        if config["import"]["quiet"]:
            # In quiet mode, don't prompt -- just skip.
            log.info("Skipping.")
            sel = "s"
        else:
            # Print some detail about the existing and new items so the
            # user can make an informed decision.
            for duplicate in found_duplicates:
                ui.print_(
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
                        for dup in duplicate.items():
                            print(f"  {dup}")
                    else:
                        print(f"  {duplicate}")

            ui.print_(
                "New: "
                + summarize_items(
                    task.imported_items(),
                    not task.is_album,
                )
            )
            if config["import"]["duplicate_verbose_prompt"]:
                for item in task.imported_items():
                    print(f"  {item}")

            sel = ui.input_options(
                ("Skip new", "Keep all", "Remove old", "Merge all")
            )

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
        all_choices = (
            [
                PromptChoice("a", "Apply", None),
            ]
            + choices
            + extra_choices
        )

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


def _summary_judgment(rec):
    """Determines whether a decision should be made without even asking
    the user. This occurs in quiet mode and when an action is chosen for
    NONE recommendations. Return None if the user should be queried.
    Otherwise, returns an action. May also print to the console if a
    summary judgment is made.
    """

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
        ui.print_("Skipping.")
    elif action == importer.Action.ASIS:
        ui.print_("Importing as-is.")
    return action


class PromptChoice(NamedTuple):
    short: str
    long: str
    callback: Any


def choose_candidate(
    candidates,
    singleton,
    rec,
    cur_artist=None,
    cur_album=None,
    item=None,
    itemcount=None,
    choices=[],
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
    choice_opts = tuple(c.long for c in choices)
    choice_actions = {c.short: c for c in choices}

    # Zero candidates.
    if not candidates:
        if singleton:
            ui.print_("No matching recordings found.")
        else:
            print_(f"No matching release found for {itemcount} tracks.")
            print_(
                "For help, see: "
                "https://beets.readthedocs.org/en/latest/faq.html#nomatch"
            )
        sel = ui.input_options(choice_opts)
        if sel in choice_actions:
            return choice_actions[sel]
        else:
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
            ui.print_(
                f"Finding tags for {'track' if singleton else 'album'} "
                f'"{item.artist if singleton else cur_artist} -'
                f' {item.title if singleton else cur_album}".'
            )

            ui.print_("  Candidates:")
            for i, match in enumerate(candidates):
                # Index, metadata, and distance.
                index0 = f"{i + 1}."
                index = dist_colorize(index0, match.distance)
                dist = f"({(1 - match.distance) * 100:.1f}%)"
                distance = dist_colorize(dist, match.distance)
                metadata = (
                    f"{match.info.artist} -"
                    f" {match.info.title if singleton else match.info.album}"
                )
                if i == 0:
                    metadata = dist_colorize(metadata, match.distance)
                else:
                    metadata = ui.colorize("text_highlight_minor", metadata)
                line1 = [index, distance, metadata]
                print_(f"  {' '.join(line1)}")

                # Penalties.
                penalties = penalty_string(match.distance, 3)
                if penalties:
                    print_(f"{' ' * 13}{penalties}")

                # Disambiguation
                disambig = disambig_string(match.info)
                if disambig:
                    print_(f"{' ' * 13}{disambig}")

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
        if singleton:
            show_item_change(item, match)
        else:
            show_change(cur_artist, cur_album, match)

        # Exact match => tag automatically if we're not in timid mode.
        if rec == Recommendation.strong and not config["import"]["timid"]:
            return match

        # Ask for confirmation.
        default = config["import"]["default_action"].as_choice(
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
            ui.print_("\a", end="")
        sel = ui.input_options(
            ("Apply", "More candidates") + choice_opts,
            require=require,
            default=default,
        )
        if sel == "a":
            return match
        elif sel in choice_actions:
            return choice_actions[sel]


def manual_search(session, task):
    """Get a new `Proposal` using manual search criteria.

    Input either an artist and album (for full albums) or artist and
    track name (for singletons) for manual search.
    """
    artist = ui.input_("Artist:").strip()
    name = ui.input_("Album:" if task.is_album else "Track:").strip()

    if task.is_album:
        _, _, prop = autotag.tag_album(task.items, artist, name)
        return prop
    else:
        return autotag.tag_item(task.item, artist, name)


def manual_id(session, task):
    """Get a new `Proposal` using a manually-entered ID.

    Input an ID, either for an album ("release") or a track ("recording").
    """
    prompt = f"Enter {'release' if task.is_album else 'recording'} ID:"
    search_id = ui.input_(prompt).strip()

    if task.is_album:
        _, _, prop = autotag.tag_album(task.items, search_ids=search_id.split())
        return prop
    else:
        return autotag.tag_item(task.item, search_ids=search_id.split())


def abort_action(session, task):
    """A prompt choice callback that aborts the importer."""
    raise importer.ImportAbortError()
