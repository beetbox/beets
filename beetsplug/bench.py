"""Some simple performance benchmarks for beets."""

from __future__ import annotations

import cProfile
import timeit
from typing import TYPE_CHECKING, Protocol

from beets import importer, plugins, ui
from beets.autotag import Source, tag_album
from beets.plugins import BeetsPlugin
from beets.util.pathformats import PF_KEY_DEFAULT
from beetsplug._utils import vfs

if TYPE_CHECKING:
    from collections.abc import Sequence

    from beets.library import Item, Library


class BenchAunique(Protocol):
    profile: bool


class BenchMatch(Protocol):
    profile: bool
    id: str | None


def aunique_benchmark(
    lib: Library, opts: BenchAunique, args: list[str]
) -> None:
    def _build_tree() -> None:
        vfs.libtree(lib)

    # Measure path generation performance with %aunique{} included.
    lib.path_formats = [
        (PF_KEY_DEFAULT, "$albumartist/$album%aunique{}/$track $title")
    ]
    if opts.profile:
        cProfile.runctx(
            "_build_tree()",
            {},
            {"_build_tree": _build_tree},
            "paths.withaunique.prof",
        )
    else:
        interval = timeit.timeit(_build_tree, number=1)
        print("With %aunique:", interval)

    # And with %aunique replaced with a "cheap" no-op function.
    lib.path_formats = [
        (PF_KEY_DEFAULT, "$albumartist/$album%lower{}/$track $title")
    ]
    if opts.profile:
        cProfile.runctx(
            "_build_tree()",
            {},
            {"_build_tree": _build_tree},
            "paths.withoutaunique.prof",
        )
    else:
        interval = timeit.timeit(_build_tree, number=1)
        print("Without %aunique:", interval)


def match_benchmark(lib: Library, opts: BenchMatch, args: list[str]) -> None:
    # If no album ID is provided, we'll match against a suitably huge
    # album.
    id_ = opts.id or "9c5c043e-bc69-4edb-81a4-1aaf9c81e6dc"

    # Get an album from the library to use as the source for the match.
    items: Sequence[Item] = i.items() if (i := lib.albums(args).get()) else []

    # Ensure fingerprinting is invoked (if enabled).
    plugins.send(
        "import_task_start",
        task=importer.ImportTask(None, None, items),
        session=importer.ImportSession(lib, None, None, None),
    )

    # Run the match.
    def _run_match() -> None:
        source = Source.from_items(items)
        tag_album(source, search_ids=[id_])

    if opts.profile:
        cProfile.runctx(
            "_run_match()", {}, {"_run_match": _run_match}, "match.prof"
        )
    else:
        interval = timeit.timeit(_run_match, number=1)
        print("match duration:", interval)


class BenchmarkPlugin(BeetsPlugin):
    """A plugin for performing some simple performance benchmarks."""

    def commands(self) -> list[ui.Subcommand]:
        aunique_bench_cmd = ui.Subcommand(
            "bench_aunique", help="benchmark for %aunique{}"
        )
        aunique_bench_cmd.parser.add_option(
            "-p",
            "--profile",
            action="store_true",
            default=False,
            help="performance profiling",
        )
        aunique_bench_cmd.func = aunique_benchmark

        match_bench_cmd = ui.Subcommand(
            "bench_match", help="benchmark for track matching"
        )
        match_bench_cmd.parser.add_option(
            "-p",
            "--profile",
            action="store_true",
            default=False,
            help="performance profiling",
        )
        match_bench_cmd.parser.add_option(
            "-i", "--id", default=None, help="album ID to match against"
        )
        match_bench_cmd.func = match_benchmark

        return [aunique_bench_cmd, match_bench_cmd]
