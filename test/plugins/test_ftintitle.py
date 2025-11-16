# This file is part of beets.
# Copyright 2016, Fabrice Laporte.
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

"""Tests for the 'ftintitle' plugin."""

from collections.abc import Generator
from typing import cast

import pytest

from beets.importer import ImportSession, ImportTask
from beets.library.models import Item
from beets.test.helper import PluginTestCase
from beetsplug import ftintitle


class FtInTitlePluginFunctional(PluginTestCase):
    plugin = "ftintitle"


@pytest.fixture
def env() -> Generator[FtInTitlePluginFunctional, None, None]:
    case = FtInTitlePluginFunctional(methodName="runTest")
    case.setUp()
    try:
        yield case
    finally:
        case.tearDown()


def set_config(
    env: FtInTitlePluginFunctional,
    cfg: dict[str, str | bool | list[str]] | None,
) -> None:
    cfg = {} if cfg is None else cfg
    defaults = {
        "drop": False,
        "auto": True,
        "keep_in_artist": False,
        "custom_words": [],
    }
    env.config["ftintitle"].set(defaults)
    env.config["ftintitle"].set(cfg)


def add_item(
    env: FtInTitlePluginFunctional,
    path: str,
    artist: str,
    title: str,
    albumartist: str | None,
) -> Item:
    return env.add_item(
        path=path,
        artist=artist,
        artist_sort=artist,
        title=title,
        albumartist=albumartist,
    )


class DummyImportTask:
    """Minimal stand-in for ImportTask used to exercise import hooks."""

    def __init__(self, items: list[Item]) -> None:
        self._items = items

    def imported_items(self) -> list[Item]:
        return self._items


@pytest.mark.parametrize(
    "cfg, cmd_args, given, expected",
    [
        pytest.param(
            None,
            ("ftintitle",),
            ("Alice", "Song 1", "Alice"),
            ("Alice", "Song 1"),
            id="no-featured-artist",
        ),
        pytest.param(
            {"format": "feat {0}"},
            ("ftintitle",),
            ("Alice ft. Bob", "Song 1", None),
            ("Alice", "Song 1 feat Bob"),
            id="no-albumartist-custom-format",
        ),
        pytest.param(
            None,
            ("ftintitle",),
            ("Alice", "Song 1", None),
            ("Alice", "Song 1"),
            id="no-albumartist-no-feature",
        ),
        pytest.param(
            {"format": "featuring {0}"},
            ("ftintitle",),
            ("Alice ft Bob", "Song 1", "George"),
            ("Alice", "Song 1 featuring Bob"),
            id="guest-artist-custom-format",
        ),
        pytest.param(
            None,
            ("ftintitle",),
            ("Alice", "Song 1", "George"),
            ("Alice", "Song 1"),
            id="guest-artist-no-feature",
        ),
        # ---- drop (-d) variants ----
        pytest.param(
            None,
            ("ftintitle", "-d"),
            ("Alice ft Bob", "Song 1", "Alice"),
            ("Alice", "Song 1"),
            id="drop-self-ft",
        ),
        pytest.param(
            None,
            ("ftintitle", "-d"),
            ("Alice", "Song 1", "Alice"),
            ("Alice", "Song 1"),
            id="drop-self-no-ft",
        ),
        pytest.param(
            None,
            ("ftintitle", "-d"),
            ("Alice ft Bob", "Song 1", "George"),
            ("Alice", "Song 1"),
            id="drop-guest-ft",
        ),
        pytest.param(
            None,
            ("ftintitle", "-d"),
            ("Alice", "Song 1", "George"),
            ("Alice", "Song 1"),
            id="drop-guest-no-ft",
        ),
        # ---- custom format variants ----
        pytest.param(
            {"format": "feat. {}"},
            ("ftintitle",),
            ("Alice ft Bob", "Song 1", "Alice"),
            ("Alice", "Song 1 feat. Bob"),
            id="custom-format-feat-dot",
        ),
        pytest.param(
            {"format": "featuring {}"},
            ("ftintitle",),
            ("Alice feat. Bob", "Song 1", "Alice"),
            ("Alice", "Song 1 featuring Bob"),
            id="custom-format-featuring",
        ),
        pytest.param(
            {"format": "with {}"},
            ("ftintitle",),
            ("Alice feat Bob", "Song 1", "Alice"),
            ("Alice", "Song 1 with Bob"),
            id="custom-format-with",
        ),
        # ---- keep_in_artist variants ----
        pytest.param(
            {"format": "feat. {}", "keep_in_artist": True},
            ("ftintitle",),
            ("Alice ft Bob", "Song 1", "Alice"),
            ("Alice ft Bob", "Song 1 feat. Bob"),
            id="keep-in-artist-add-to-title",
        ),
        pytest.param(
            {"format": "feat. {}", "keep_in_artist": True},
            ("ftintitle", "-d"),
            ("Alice ft Bob", "Song 1", "Alice"),
            ("Alice ft Bob", "Song 1"),
            id="keep-in-artist-drop-from-title",
        ),
        # ---- custom_words variants ----
        pytest.param(
            {"format": "featuring {}", "custom_words": ["med"]},
            ("ftintitle",),
            ("Alice med Bob", "Song 1", "Alice"),
            ("Alice", "Song 1 featuring Bob"),
            id="custom-feat-words",
        ),
        pytest.param(
            {
                "format": "featuring {}",
                "keep_in_artist": True,
                "custom_words": ["med"],
            },
            ("ftintitle",),
            ("Alice med Bob", "Song 1", "Alice"),
            ("Alice med Bob", "Song 1 featuring Bob"),
            id="custom-feat-words-keep-in-artists",
        ),
        pytest.param(
            {
                "format": "featuring {}",
                "keep_in_artist": True,
                "custom_words": ["med"],
            },
            (
                "ftintitle",
                "-d",
            ),
            ("Alice med Bob", "Song 1", "Alice"),
            ("Alice med Bob", "Song 1"),
            id="custom-feat-words-keep-in-artists-drop-from-title",
        ),
        # ---- preserve_album_artist variants ----
        pytest.param(
            {
                "format": "feat. {}",
                "preserve_album_artist": True,
            },
            ("ftintitle",),
            ("Alice feat. Bob", "Song 1", "Alice"),
            ("Alice", "Song 1 feat. Bob"),
            id="skip-if-artist-and-album-artists-is-the-same-different-match",
        ),
        pytest.param(
            {
                "format": "feat. {}",
                "preserve_album_artist": False,
            },
            ("ftintitle",),
            ("Alice feat. Bob", "Song 1", "Alice"),
            ("Alice", "Song 1 feat. Bob"),
            id="skip-if-artist-and-album-artists-is-the-same-different-match-b",
        ),
        pytest.param(
            {
                "format": "feat. {}",
                "preserve_album_artist": True,
            },
            ("ftintitle",),
            ("Alice feat. Bob", "Song 1", "Alice feat. Bob"),
            ("Alice feat. Bob", "Song 1"),
            id="skip-if-artist-and-album-artists-is-the-same-matching-match",
        ),
        pytest.param(
            {
                "format": "feat. {}",
                "preserve_album_artist": False,
            },
            ("ftintitle",),
            ("Alice feat. Bob", "Song 1", "Alice feat. Bob"),
            ("Alice", "Song 1 feat. Bob"),
            id="skip-if-artist-and-album-artists-is-the-same-matching-match-b",
        ),
        # ---- titles with brackets/parentheses ----
        pytest.param(
            {"format": "ft. {}"},
            ("ftintitle",),
            ("Alice ft. Bob", "Song 1 (Carol Remix)", "Alice"),
            ("Alice", "Song 1 ft. Bob (Carol Remix)"),
            id="title-with-brackets-insert-before",
        ),
        pytest.param(
            {"format": "ft. {}", "keep_in_artist": True},
            ("ftintitle",),
            ("Alice ft. Bob", "Song 1 (Carol Remix)", "Alice"),
            ("Alice ft. Bob", "Song 1 ft. Bob (Carol Remix)"),
            id="title-with-brackets-keep-in-artist",
        ),
        pytest.param(
            {"format": "ft. {}"},
            ("ftintitle",),
            ("Alice ft. Bob", "Song 1 (Remix) (Live)", "Alice"),
            ("Alice", "Song 1 ft. Bob (Remix) (Live)"),
            id="title-with-multiple-brackets-uses-first-with-keyword",
        ),
        pytest.param(
            {"format": "ft. {}"},
            ("ftintitle",),
            ("Alice ft. Bob", "Song 1 (Arbitrary)", "Alice"),
            ("Alice", "Song 1 (Arbitrary) ft. Bob"),
            id="title-with-brackets-no-keyword-appends",
        ),
        pytest.param(
            {"format": "ft. {}"},
            ("ftintitle",),
            ("Alice ft. Bob", "Song 1 [Edit]", "Alice"),
            ("Alice", "Song 1 ft. Bob [Edit]"),
            id="title-with-square-brackets-keyword",
        ),
        pytest.param(
            {"format": "ft. {}"},
            ("ftintitle",),
            ("Alice ft. Bob", "Song 1 <Version>", "Alice"),
            ("Alice", "Song 1 ft. Bob <Version>"),
            id="title-with-angle-brackets-keyword",
        ),
        # multi-word keyword
        pytest.param(
            {"format": "ft. {}", "bracket_keywords": ["club mix"]},
            ("ftintitle",),
            ("Alice ft. Bob", "Song 1 (Club Mix)", "Alice"),
            ("Alice", "Song 1 ft. Bob (Club Mix)"),
            id="multi-word-keyword-positive-match",
        ),
        pytest.param(
            {"format": "ft. {}", "bracket_keywords": ["club mix"]},
            ("ftintitle",),
            ("Alice ft. Bob", "Song 1 (Club Remix)", "Alice"),
            ("Alice", "Song 1 (Club Remix) ft. Bob"),
            id="multi-word-keyword-negative-no-match",
        ),
    ],
)
def test_ftintitle_functional(
    env: FtInTitlePluginFunctional,
    cfg: dict[str, str | bool | list[str]] | None,
    cmd_args: tuple[str, ...],
    given: tuple[str, str, str | None],
    expected: tuple[str, str],
) -> None:
    set_config(env, cfg)
    ftintitle.FtInTitlePlugin()

    artist, title, albumartist = given
    item = add_item(env, "/", artist, title, albumartist)

    env.run_command(*cmd_args)
    item.load()

    expected_artist, expected_title = expected
    assert item["artist"] == expected_artist
    assert item["title"] == expected_title


def test_imported_stage_moves_featured_artist(
    env: FtInTitlePluginFunctional,
) -> None:
    """The import-stage hook should fetch config settings and process items."""
    set_config(env, None)
    plugin = ftintitle.FtInTitlePlugin()
    item = add_item(
        env,
        "/imported-hook",
        "Alice feat. Bob",
        "Song 1 (Carol Remix)",
        "Various Artists",
    )
    task = DummyImportTask([item])

    plugin.imported(
        cast(ImportSession, None),
        cast(ImportTask, task),
    )
    item.load()

    assert item["artist"] == "Alice"
    assert item["title"] == "Song 1 feat. Bob (Carol Remix)"


@pytest.mark.parametrize(
    "artist,albumartist,expected",
    [
        ("Alice ft. Bob", "Alice", "Bob"),
        ("Alice feat Bob", "Alice", "Bob"),
        ("Alice featuring Bob", "Alice", "Bob"),
        ("Alice & Bob", "Alice", "Bob"),
        ("Alice and Bob", "Alice", "Bob"),
        ("Alice With Bob", "Alice", "Bob"),
        ("Alice defeat Bob", "Alice", None),
        ("Alice & Bob", "Bob", "Alice"),
        ("Alice ft. Bob", "Bob", "Alice"),
        ("Alice ft. Carol", "Bob", "Carol"),
    ],
)
def test_find_feat_part(
    artist: str,
    albumartist: str,
    expected: str | None,
) -> None:
    assert ftintitle.find_feat_part(artist, albumartist) == expected


@pytest.mark.parametrize(
    "given,expected",
    [
        ("Alice ft. Bob", ("Alice", "Bob")),
        ("Alice feat Bob", ("Alice", "Bob")),
        ("Alice feat. Bob", ("Alice", "Bob")),
        ("Alice featuring Bob", ("Alice", "Bob")),
        ("Alice & Bob", ("Alice", "Bob")),
        ("Alice and Bob", ("Alice", "Bob")),
        ("Alice With Bob", ("Alice", "Bob")),
        ("Alice defeat Bob", ("Alice defeat Bob", None)),
    ],
)
def test_split_on_feat(
    given: str,
    expected: tuple[str, str | None],
) -> None:
    assert ftintitle.split_on_feat(given) == expected


@pytest.mark.parametrize(
    "given,expected",
    [
        # different braces and keywords
        ("Song (Remix)", 5),
        ("Song [Version]", 5),
        ("Song {Extended Mix}", 5),
        ("Song <Instrumental>", 5),
        # two keyword clauses
        ("Song (Remix) (Live)", 5),
        # brace insensitivity
        ("Song (Live) [Remix]", 5),
        ("Song [Edit] (Remastered)", 5),
        # negative cases
        ("Song", None),  # no clause
        ("Song (Arbitrary)", None),  # no keyword
        ("Song (", None),  # no matching brace or keyword
        ("Song (Live", None),  # no matching brace with keyword
        # one keyword clause, one non-keyword clause
        ("Song (Live) (Arbitrary)", 5),
        ("Song (Arbitrary) (Remix)", 17),
        # nested brackets - same type
        ("Song (Remix (Extended))", 5),
        ("Song [Arbitrary [Description]]", None),
        # nested brackets - different types
        ("Song (Remix [Extended])", 5),
        # nested - returns outer start position despite inner keyword
        ("Song [Arbitrary {Extended}]", 5),
        ("Song {Live <Arbitrary>}", 5),
        ("Song <Remaster (Arbitrary)>", 5),
        ("Song <Extended> [Live]", 5),
        ("Song (Version) <Live>", 5),
        ("Song (Arbitrary [Description])", None),
        ("Song [Description (Arbitrary)]", None),
    ],
)
def test_find_bracket_position(given: str, expected: int | None) -> None:
    assert ftintitle.find_bracket_position(given) == expected


@pytest.mark.parametrize(
    "given,keywords,expected",
    [
        ("Song (Live)", ["live"], 5),
        ("Song (Live)", None, 5),
        ("Song (Arbitrary)", None, None),
        ("Song (Concert)", ["concert"], 5),
        ("Song (Concert)", None, None),
        ("Song (Remix)", ["custom"], None),
        ("Song (Custom)", ["custom"], 5),
        ("Song (Live)", [], 5),
        ("Song (Anything)", [], 5),
        ("Song (Remix)", [], 5),
        ("Song", [], None),
        ("Song (", [], None),
        # Multi-word keyword tests
        ("Song (Club Mix)", ["club mix"], 5),  # Positive: matches multi-word
        ("Song (Club Remix)", ["club mix"], None),  # Negative: no match
    ],
)
def test_find_bracket_position_custom_keywords(
    given: str, keywords: list[str] | None, expected: int | None
) -> None:
    assert ftintitle.find_bracket_position(given, keywords) == expected


@pytest.mark.parametrize(
    "given,expected",
    [
        ("Alice ft. Bob", True),
        ("Alice feat. Bob", True),
        ("Alice feat Bob", True),
        ("Alice featuring Bob", True),
        ("Alice (ft. Bob)", True),
        ("Alice (feat. Bob)", True),
        ("Alice [ft. Bob]", True),
        ("Alice [feat. Bob]", True),
        ("Alice defeat Bob", False),
        ("Aliceft.Bob", False),
        ("Alice (defeat Bob)", False),
        ("Live and Let Go", False),
        ("Come With Me", False),
    ],
)
def test_contains_feat(given: str, expected: bool) -> None:
    assert ftintitle.contains_feat(given) is expected


@pytest.mark.parametrize(
    "given,custom_words,expected",
    [
        ("Alice ft. Bob", [], True),
        ("Alice feat. Bob", [], True),
        ("Alice feat Bob", [], True),
        ("Alice featuring Bob", [], True),
        ("Alice (ft. Bob)", [], True),
        ("Alice (feat. Bob)", [], True),
        ("Alice [ft. Bob]", [], True),
        ("Alice [feat. Bob]", [], True),
        ("Alice defeat Bob", [], False),
        ("Aliceft.Bob", [], False),
        ("Alice (defeat Bob)", [], False),
        ("Live and Let Go", [], False),
        ("Come With Me", [], False),
        ("Alice x Bob", ["x"], True),
        ("Alice x Bob", ["X"], True),
        ("Alice och Xavier", ["x"], False),
        ("Alice ft. Xavier", ["x"], True),
        ("Alice med Carol", ["med"], True),
        ("Alice med Carol", [], False),
    ],
)
def test_custom_words(
    given: str, custom_words: list[str] | None, expected: bool
) -> None:
    if custom_words is None:
        custom_words = []
    assert ftintitle.contains_feat(given, custom_words) is expected
