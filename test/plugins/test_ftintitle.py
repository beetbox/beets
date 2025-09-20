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

from typing import Dict, Generator, Optional, Tuple, Union

import pytest

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
    env: FtInTitlePluginFunctional, cfg: Optional[Dict[str, Union[str, bool]]]
) -> None:
    cfg = {} if cfg is None else cfg
    defaults = {
        "drop": False,
        "auto": True,
        "keep_in_artist": False,
    }
    env.config["ftintitle"].set(defaults)
    env.config["ftintitle"].set(cfg)


def add_item(
    env: FtInTitlePluginFunctional,
    path: str,
    artist: str,
    title: str,
    albumartist: Optional[str],
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
    ],
)
def test_ftintitle_functional(
    env: FtInTitlePluginFunctional,
    cfg: Optional[Dict[str, Union[str, bool]]],
    cmd_args: Tuple[str, ...],
    given: Tuple[str, str, Optional[str]],
    expected: Tuple[str, str],
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
    expected: Optional[str],
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
    expected: Tuple[str, Optional[str]],
) -> None:
    assert ftintitle.split_on_feat(given) == expected


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
