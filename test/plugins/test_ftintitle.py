"""Tests for the 'ftintitle' plugin."""

from __future__ import annotations

from typing import cast

import pytest

from beets import plugins
from beets.autotag import AlbumInfo, TrackInfo
from beets.importer import ImportSession, SingletonImportTask
from beets.library.models import Album
from beets.test.helper import PluginTestHelper
from beetsplug import ftintitle


class TestFtInTitlePluginFunctional(PluginTestHelper):
    plugin = "ftintitle"
    preload_plugin = False

    @pytest.mark.parametrize(
        "cfg, cmd_args, given, expected",
        [
            pytest.param(
                {},
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
                {},
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
                {},
                ("ftintitle",),
                ("Alice", "Song 1", "George"),
                ("Alice", "Song 1"),
                id="guest-artist-no-feature",
            ),
            # ---- drop (-d) variants ----
            pytest.param(
                {},
                ("ftintitle", "-d"),
                ("Alice ft Bob", "Song 1", "Alice"),
                ("Alice", "Song 1"),
                id="drop-self-ft",
            ),
            pytest.param(
                {},
                ("ftintitle", "-d"),
                ("Alice", "Song 1", "Alice"),
                ("Alice", "Song 1"),
                id="drop-self-no-ft",
            ),
            pytest.param(
                {},
                ("ftintitle", "-d"),
                ("Alice ft Bob", "Song 1", "George"),
                ("Alice", "Song 1"),
                id="drop-guest-ft",
            ),
            pytest.param(
                {},
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
            pytest.param(
                {"format": "ft. {}"},
                ("ftintitle",),
                ("Alice (ft. Bob)", "Song 1", "Alice"),
                ("Alice", "Song 1 ft. Bob"),
                id="featured-artist-in-parentheses",
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
                ("ftintitle", "-d"),
                ("Alice med Bob", "Song 1", "Alice"),
                ("Alice med Bob", "Song 1"),
                id="custom-feat-words-keep-in-artists-drop-from-title",
            ),
            # ---- preserve_album_artist variants ----
            pytest.param(
                {"format": "feat. {}", "preserve_album_artist": True},
                ("ftintitle",),
                ("Alice feat. Bob", "Song 1", "Alice"),
                ("Alice", "Song 1 feat. Bob"),
                id="skip-if-artist-and-album-artists-is-the-same-different-match",
            ),
            pytest.param(
                {"format": "feat. {}", "preserve_album_artist": False},
                ("ftintitle",),
                ("Alice feat. Bob", "Song 1", "Alice"),
                ("Alice", "Song 1 feat. Bob"),
                id="skip-if-artist-and-album-artists-is-the-same-different-match-b",
            ),
            pytest.param(
                {"format": "feat. {}", "preserve_album_artist": True},
                ("ftintitle",),
                ("Alice feat. Bob", "Song 1", "Alice feat. Bob"),
                ("Alice feat. Bob", "Song 1"),
                id="skip-if-artist-and-album-artists-is-the-same-matching-match",
            ),
            pytest.param(
                {"format": "feat. {}", "preserve_album_artist": False},
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
        self,
        cfg: dict[str, str | bool | list[str]],
        cmd_args: tuple[str, ...],
        given: tuple[str, str, str | None],
        expected: tuple[str, str],
    ) -> None:
        config = {
            "drop": False,
            "auto": True,
            "keep_in_artist": False,
            "custom_words": [],
            **cfg,
        }

        artist, title, albumartist = given
        item = self.add_item(
            path="/",
            artist=artist,
            artist_sort=artist,
            title=title,
            albumartist=albumartist,
        )

        with self.configure_plugin(config):
            self.run_command(*cmd_args)

        item.load()

        expected_artist, expected_title = expected
        assert item["artist"] == expected_artist
        assert item["title"] == expected_title

    def test_trackinfo_received_rewrites_artist_when_artist_credit_enabled(
        self,
    ) -> None:
        self.config["artist_credit"] = True
        info = TrackInfo(
            artist="Alice feat. Bob",
            artist_credit="Alice",
            artist_sort="Alice feat. Bob",
            artists=["Alice", "Bob"],
            artists_credit=["Alice"],
            title="Song",
        )

        with self.configure_plugin({"auto": True}):
            plugins.send("trackinfo_received", info=info)

        assert info.artist == "Alice"
        assert info.artist_credit == "Alice"
        assert info.artist_sort == "Alice"
        assert info.artists == ["Alice", "Bob"]
        assert info.artists_credit == ["Alice"]
        assert info.title == "Song feat. Bob"
        assert info.item_data["title"] == "Song feat. Bob"

    @pytest.mark.parametrize(
        "config, artist, title, expected_artist, expected_title",
        [
            pytest.param(
                {"auto": False},
                "Alice feat. Bob",
                "Song",
                "Alice feat. Bob",
                "Song",
                id="auto-disabled",
            ),
            pytest.param(
                {"auto": True},
                "Alice",
                "Song",
                "Alice",
                "Song",
                id="no-feature",
            ),
            pytest.param(
                {"auto": True},
                "Alice feat. Bob",
                "Song feat. Bob",
                "Alice",
                "Song feat. Bob",
                id="existing-title-feature",
            ),
        ],
    )
    def test_trackinfo_received_rewrites_or_skips_simple_cases(
        self,
        config: dict[str, bool],
        artist: str,
        title: str,
        expected_artist: str,
        expected_title: str,
    ) -> None:
        info = TrackInfo(artist=artist, title=title)

        with self.configure_plugin(config):
            plugins.send("trackinfo_received", info=info)

        assert info.artist == expected_artist
        assert info.title == expected_title

    def test_ft_in_title_reports_no_change_for_info_drop_keep_noop(
        self,
    ) -> None:
        info = TrackInfo(artist="Alice feat. Bob", title="Song")

        with self.configure_plugin({"drop": True, "keep_in_artist": True}):
            plugin = next(iter(plugins.find_plugins()))
            assert isinstance(plugin, ftintitle.FtInTitlePlugin)
            assert plugin.ft_in_title(info, "") is False

        assert info.artist == "Alice feat. Bob"
        assert info.title == "Song"

    def test_trackinfo_received_preserves_artist_credit_when_disabled(
        self,
    ) -> None:
        self.config["artist_credit"] = False
        info = TrackInfo(
            artist="Alice feat. Bob",
            artist_credit="Alice feat. Bobby",
            title="Song",
        )

        with self.configure_plugin({"auto": True}):
            plugins.send("trackinfo_received", info=info)

        assert info.artist == "Alice"
        assert info.artist_credit == "Alice feat. Bobby"
        assert info.title == "Song feat. Bob"
        assert info.item_data["artist_credit"] == "Alice feat. Bobby"

    def test_trackinfo_received_preserves_collaborative_artist_credit(
        self,
    ) -> None:
        self.config["artist_credit"] = False
        info = TrackInfo(
            artist="Alice feat. Bob",
            artist_credit="Alice & Bobby",
            title="Song",
        )

        with self.configure_plugin({"auto": True}):
            plugins.send("trackinfo_received", info=info)

        assert info.artist == "Alice"
        assert info.artist_credit == "Alice & Bobby"
        assert info.title == "Song feat. Bob"

    def test_ft_in_title_reports_no_change_for_item_drop_keep_noop(
        self,
    ) -> None:
        item = self.add_item(
            path="/",
            artist="Alice feat. Bob",
            artist_sort="",
            title="Song",
            albumartist="Alice",
        )

        with self.configure_plugin({"drop": True, "keep_in_artist": True}):
            plugin = next(iter(plugins.find_plugins()))
            assert isinstance(plugin, ftintitle.FtInTitlePlugin)
            assert (
                plugin.ft_in_title(item, item.get("albumartist") or "") is False
            )

        assert item.artist == "Alice feat. Bob"
        assert item.title == "Song"

    def test_imported_stage_rewrites_imported_items(self) -> None:
        item = self.add_item(
            path="/",
            artist="Alice feat. Bob",
            title="Song",
            albumartist="Alice",
        )

        with self.configure_plugin({"auto": True}):
            plugin = next(iter(plugins.find_plugins()))
            assert isinstance(plugin, ftintitle.FtInTitlePlugin)
            plugin.imported(
                cast(ImportSession, None), SingletonImportTask(None, item)
            )

        item.load()
        assert item.artist == "Alice"
        assert item.title == "Song feat. Bob"

    def test_albuminfo_received_rewrites_tracks_with_album_artist(self) -> None:
        track_info = TrackInfo(
            artist="Alice & Bob", artist_sort="Alice & Bob", title="Song"
        )
        info = AlbumInfo(artist="Alice", album="Album", tracks=[track_info])

        with self.configure_plugin({"auto": True}):
            plugins.send("albuminfo_received", info=info)

        assert track_info.artist == "Alice"
        assert track_info.artist_sort == "Alice"
        assert track_info.title == "Song feat. Bob"
        assert track_info.item_data["artist"] == "Alice"
        assert track_info.item_data["title"] == "Song feat. Bob"


@pytest.mark.parametrize(
    "artist,albumartist,expected",
    [
        ("Alice ft. Bob", "Alice", "Bob"),
        ("Alice feat Bob", "Alice", "Bob"),
        ("Alice featuring Bob", "Alice", "Bob"),
        ("Alice & Bob", "Alice", "Bob"),
        ("Alice and Bob", "Alice", "Bob"),
        ("Alice With Bob", "Alice", "Bob"),
        ("Alice (ft. Bob)", "Alice", "Bob"),
        ("Alice [ft. Bob]", "Bob", "Alice"),
        ("Alice defeat Bob", "Alice", None),
        ("Alice & Bob", "Bob", "Alice"),
        ("Alice ft. Bob", "Bob", "Alice"),
        ("Alice ft. Carol", "Bob", "Carol"),
    ],
)
def test_find_feat_part(
    artist: str, albumartist: str, expected: str | None
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
        ("Alice (ft. Bob)", ("Alice", "Bob")),
        ("Alice [& Bob]", ("Alice", "Bob")),
    ],
)
def test_split_on_feat(given: str, expected: tuple[str, str | None]) -> None:
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
    given: str, keywords: list[str] | None, expected: str
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
    given: str, custom_words: list[str], expected: bool
) -> None:
    assert ftintitle.contains_feat(given, custom_words) is expected


def test_album_template_value(config):
    config["ftintitle"]["custom_words"] = []

    album = Album()
    album["albumartist"] = "Foo ft. Bar"
    assert ftintitle._album_artist_no_feat(album) == "Foo"

    album["albumartist"] = "Foobar"
    assert ftintitle._album_artist_no_feat(album) == "Foobar"
