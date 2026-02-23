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

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

import pytest

from beets.library.models import Album
from beets.test.helper import PluginTestCase
from beetsplug import ftintitle

if TYPE_CHECKING:
    from collections.abc import Generator

    from beets.library.models import Item

ConfigValue: TypeAlias = str | bool | list[str]


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
    cfg: dict[str, ConfigValue] | None,
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
            {"format": "ft. {}", "bracket_keywords": ["mix"]},
            ("ftintitle",),
            ("Alice ft. Bob", "Song 1 (Club Mix)", "Alice"),
            ("Alice", "Song 1 ft. Bob (Club Mix)"),
            id="ft-inserted-before-matching-bracket-keyword",
        ),
        pytest.param(
            {"format": "ft. {}", "bracket_keywords": ["nomatch"]},
            ("ftintitle",),
            ("Alice ft. Bob", "Song 1 (Club Remix)", "Alice"),
            ("Alice", "Song 1 (Club Remix) ft. Bob"),
            id="ft-inserted-at-end-no-bracket-keyword-match",
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
        ("Alice, Bob & Charlie", ("Alice", "Bob & Charlie")),
        (
            "Alice, Bob & Charlie feat. Xavier",
            ("Alice, Bob & Charlie", "Xavier"),
        ),
        ("Alice and Bob", ("Alice", "Bob")),
        ("Alice With Bob", ("Alice", "Bob")),
        ("Alice defeat Bob", ("Alice defeat Bob", None)),
        ("Alice & Bob feat Charlie", ("Alice & Bob", "Charlie")),
        ("Alice & Bob ft. Charlie", ("Alice & Bob", "Charlie")),
        ("Alice & Bob featuring Charlie", ("Alice & Bob", "Charlie")),
        ("Alice and Bob feat Charlie", ("Alice and Bob", "Charlie")),
    ],
)
def test_split_on_feat(
    given: str,
    expected: tuple[str, str | None],
) -> None:
    assert ftintitle.split_on_feat(given) == expected


@pytest.mark.parametrize(
    "given,keywords,expected",
    [
        ## default keywords
        # different braces and keywords
        ("Song (Remix)", None, "Song ft. Bob (Remix)"),
        ("Song [Version]", None, "Song ft. Bob [Version]"),
        ("Song {Extended Mix}", None, "Song ft. Bob {Extended Mix}"),
        ("Song <Instrumental>", None, "Song ft. Bob <Instrumental>"),
        # two keyword clauses
        ("Song (Remix) (Live)", None, "Song ft. Bob (Remix) (Live)"),
        # brace insensitivity
        ("Song (Live) [Remix]", None, "Song ft. Bob (Live) [Remix]"),
        ("Song [Edit] (Remastered)", None, "Song ft. Bob [Edit] (Remastered)"),
        # negative cases
        ("Song", None, "Song ft. Bob"),  # no clause
        ("Song (Arbitrary)", None, "Song (Arbitrary) ft. Bob"),  # no keyword
        ("Song (", None, "Song ( ft. Bob"),  # no matching brace or keyword
        ("Song (Live", None, "Song (Live ft. Bob"),  # no matching brace with keyword
        # one keyword clause, one non-keyword clause
        ("Song (Live) (Arbitrary)", None, "Song ft. Bob (Live) (Arbitrary)"),
        ("Song (Arbitrary) (Remix)", None, "Song (Arbitrary) ft. Bob (Remix)"),
        # nested brackets - same type
        ("Song (Remix (Extended))", None, "Song ft. Bob (Remix (Extended))"),
        ("Song [Arbitrary [Description]]", None, "Song [Arbitrary [Description]] ft. Bob"),
        # nested brackets - different types
        ("Song (Remix [Extended])", None, "Song ft. Bob (Remix [Extended])"),
        # nested - returns outer start position despite inner keyword
        ("Song [Arbitrary {Extended}]", None, "Song ft. Bob [Arbitrary {Extended}]"),
        ("Song {Live <Arbitrary>}", None, "Song ft. Bob {Live <Arbitrary>}"),
        ("Song <Remaster (Arbitrary)>", None, "Song ft. Bob <Remaster (Arbitrary)>"),
        ("Song <Extended> [Live]", None, "Song ft. Bob <Extended> [Live]"),
        ("Song (Version) <Live>", None, "Song ft. Bob (Version) <Live>"),
        ("Song (Arbitrary [Description])", None, "Song (Arbitrary [Description]) ft. Bob"),
        ("Song [Description (Arbitrary)]", None, "Song [Description (Arbitrary)] ft. Bob"),
        ## custom keywords
        ("Song (Live)", ["live"], "Song ft. Bob (Live)"),
        ("Song (Concert)", ["concert"], "Song ft. Bob (Concert)"),
        ("Song (Remix)", ["custom"], "Song (Remix) ft. Bob"),
        ("Song (Custom)", ["custom"], "Song ft. Bob (Custom)"),
        ("Song", [], "Song ft. Bob"),
        ("Song (", [], "Song ( ft. Bob"),
        # Multi-word keyword tests
        ("Song (Club Mix)", ["club mix"], "Song ft. Bob (Club Mix)"),  # Positive: matches multi-word
        ("Song (Club Remix)", ["club mix"], "Song (Club Remix) ft. Bob"),  # Negative: no match
    ],
)  # fmt: skip
def test_insert_ft_into_title(
    given: str,
    keywords: list[str] | None,
    expected: str,
) -> None:
    assert (
        ftintitle.FtInTitlePlugin.insert_ft_into_title(
            given, "ft. Bob", keywords
        )
        == expected
    )


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


def test_album_template_value(config):
    config["ftintitle"]["custom_words"] = []

    album = Album()
    album["albumartist"] = "Foo ft. Bar"
    assert ftintitle._album_artist_no_feat(album) == "Foo"

    album["albumartist"] = "Foobar"
    assert ftintitle._album_artist_no_feat(album) == "Foobar"
