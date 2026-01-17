from __future__ import annotations

import json
from copy import deepcopy
from typing import TYPE_CHECKING

import pytest

from beets.autotag import AlbumMatch
from beets.autotag.distance import Distance
from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.library import Item
from beets.test.helper import PluginMixin
from beetsplug.musicbrainz import (
    MultiPseudoAlbumInfo,
    MusicBrainzPlugin,
    PseudoAlbumInfo,
)

if TYPE_CHECKING:
    import pathlib

    from beetsplug._typing import JSONDict


@pytest.fixture(scope="module")
def rsrc_dir(pytestconfig: pytest.Config):
    return pytestconfig.rootpath / "test" / "rsrc" / "musicbrainz"


@pytest.fixture
def official_release(rsrc_dir: pathlib.Path) -> JSONDict:
    info_json = (rsrc_dir / "official_release.json").read_text(encoding="utf-8")
    return json.loads(info_json)


@pytest.fixture
def pseudo_release(rsrc_dir: pathlib.Path) -> JSONDict:
    info_json = (rsrc_dir / "pseudo_release.json").read_text(encoding="utf-8")
    return json.loads(info_json)


@pytest.fixture
def official_release_info() -> AlbumInfo:
    return AlbumInfo(
        tracks=[TrackInfo(title="百花繚乱")],
        album_id="official",
        album="百花繚乱",
    )


@pytest.fixture
def pseudo_release_info() -> AlbumInfo:
    return AlbumInfo(
        tracks=[TrackInfo(title="In Bloom")],
        album_id="pseudo",
        album="In Bloom",
    )


@pytest.mark.usefixtures("config")
class TestPseudoAlbumInfo:
    def test_album_id_always_from_pseudo(
        self, official_release_info: AlbumInfo, pseudo_release_info: AlbumInfo
    ):
        info = PseudoAlbumInfo(pseudo_release_info, official_release_info)
        info.use_official_as_ref()
        assert info.album_id == "pseudo"

    def test_get_attr_from_pseudo(
        self, official_release_info: AlbumInfo, pseudo_release_info: AlbumInfo
    ):
        info = PseudoAlbumInfo(pseudo_release_info, official_release_info)
        info.use_pseudo_as_ref()
        assert info.album == "In Bloom"

    def test_get_attr_from_official(
        self, official_release_info: AlbumInfo, pseudo_release_info: AlbumInfo
    ):
        info = PseudoAlbumInfo(pseudo_release_info, official_release_info)
        info.use_official_as_ref()
        assert info.album == info.get_official_release().album

    def test_determine_best_ref(
        self, official_release_info: AlbumInfo, pseudo_release_info: AlbumInfo
    ):
        info = PseudoAlbumInfo(
            pseudo_release_info, official_release_info, data_source="test"
        )
        item = Item(title="百花繚乱")

        assert info.determine_best_ref([item]) == "official"

        info.use_pseudo_as_ref()
        assert info.data_source == "test"


class TestMBPseudoMixin(PluginMixin):
    plugin = "musicbrainz"

    @pytest.fixture(autouse=True)
    def patch_get_release(
        self,
        monkeypatch,
        official_release: JSONDict,
        pseudo_release: JSONDict,
    ):
        def mock_get_release(_, album_id: str, **kwargs):
            if album_id == official_release["id"]:
                return deepcopy(official_release)
            else:
                return deepcopy(pseudo_release)

        monkeypatch.setattr(
            "beetsplug._utils.musicbrainz.MusicBrainzAPI.get_release",
            mock_get_release,
        )

    @pytest.fixture(scope="class")
    def plugin_config(self):
        return {"pseudo_releases": {"scripts": ["Latn", "Dummy"]}}

    @pytest.fixture
    def musicbrainz_plugin(self, plugin_config) -> MusicBrainzPlugin:
        self.config[self.plugin].set(plugin_config)
        return MusicBrainzPlugin()

    @staticmethod
    def get_album_info(
        musicbrainz_plugin: MusicBrainzPlugin,
        raw: JSONDict,
    ) -> AlbumInfo:
        if info := musicbrainz_plugin.album_for_id(raw["id"]):
            return info
        else:
            raise AssertionError("AlbumInfo is None")


class TestMBPseudoReleases(TestMBPseudoMixin):
    def test_scripts_init(self, musicbrainz_plugin: MusicBrainzPlugin):
        assert musicbrainz_plugin._scripts == ["Latn", "Dummy"]

    def test_reimport_logic(
        self,
        musicbrainz_plugin: MusicBrainzPlugin,
        official_release_info: AlbumInfo,
        pseudo_release_info: AlbumInfo,
    ):
        pseudo_info = PseudoAlbumInfo(
            pseudo_release_info, official_release_info
        )

        item = Item()
        item["title"] = "百花繚乱"

        # if items don't have mb_*, they are not modified
        musicbrainz_plugin._determine_pseudo_album_info_ref([item], pseudo_info)
        assert pseudo_info.album == item.title

        pseudo_info.use_pseudo_as_ref()
        assert pseudo_info.album == "In Bloom"

        item["mb_albumid"] = "mb_aid"
        item["mb_trackid"] = "mb_tid"
        assert item.get("mb_albumid") == "mb_aid"
        assert item.get("mb_trackid") == "mb_tid"

        # if items have mb_*, they are deleted
        musicbrainz_plugin._determine_pseudo_album_info_ref([item], pseudo_info)
        assert pseudo_info.album == item.title
        assert item.get("mb_albumid") == ""
        assert item.get("mb_trackid") == ""

    def test_album_info_for_pseudo_release(
        self,
        musicbrainz_plugin: MusicBrainzPlugin,
        pseudo_release: JSONDict,
    ):
        album_info = self.get_album_info(musicbrainz_plugin, pseudo_release)
        assert isinstance(album_info, PseudoAlbumInfo)
        assert album_info.data_source == "MusicBrainz"
        assert album_info.albumstatus == "Official"

    @pytest.mark.parametrize(
        "json_key",
        [
            "type",
            "direction",
            "release",
        ],
    )
    def test_interception_skip_when_rel_values_dont_match(
        self,
        musicbrainz_plugin: MusicBrainzPlugin,
        official_release: JSONDict,
        json_key: str,
    ):
        for r in official_release["release-relations"]:
            del r[json_key]

        album_info = self.get_album_info(musicbrainz_plugin, official_release)
        assert not isinstance(album_info, PseudoAlbumInfo)
        assert album_info.data_source == "MusicBrainz"

    def test_interception_skip_when_script_doesnt_match(
        self,
        musicbrainz_plugin: MusicBrainzPlugin,
        official_release: JSONDict,
    ):
        for r in official_release["release-relations"]:
            r["release"]["text-representation"]["script"] = "Null"

        album_info = self.get_album_info(musicbrainz_plugin, official_release)
        assert not isinstance(album_info, PseudoAlbumInfo)
        assert album_info.data_source == "MusicBrainz"

    def test_interception_skip_when_relations_missing(
        self,
        musicbrainz_plugin: MusicBrainzPlugin,
        official_release: JSONDict,
    ):
        del official_release["release-relations"]
        album_info = self.get_album_info(musicbrainz_plugin, official_release)
        assert not isinstance(album_info, PseudoAlbumInfo)
        assert album_info.data_source == "MusicBrainz"

    def test_interception(
        self,
        musicbrainz_plugin: MusicBrainzPlugin,
        official_release: JSONDict,
    ):
        album_info = self.get_album_info(musicbrainz_plugin, official_release)
        assert isinstance(album_info, PseudoAlbumInfo)
        assert album_info.data_source == "MusicBrainz"

    def test_final_adjustment_skip(
        self,
        musicbrainz_plugin: MusicBrainzPlugin,
    ):
        match = AlbumMatch(
            distance=Distance(),
            info=AlbumInfo(tracks=[], data_source="mb"),
            mapping={},
            extra_items=[],
            extra_tracks=[],
        )
        musicbrainz_plugin._adjust_final_album_match(match)

    def test_final_adjustment(
        self,
        musicbrainz_plugin: MusicBrainzPlugin,
        official_release_info: AlbumInfo,
        pseudo_release_info: AlbumInfo,
    ):
        pseudo_album_info = PseudoAlbumInfo(
            pseudo_release=pseudo_release_info,
            official_release=official_release_info,
            data_source=musicbrainz_plugin.data_source,
        )
        pseudo_album_info.use_official_as_ref()

        item = Item()
        item["title"] = "百花繚乱"

        match = AlbumMatch(
            distance=Distance(),
            info=pseudo_album_info,
            mapping={item: pseudo_album_info.tracks[0]},
            extra_items=[],
            extra_tracks=[],
        )

        musicbrainz_plugin._adjust_final_album_match(match)

        assert match.info.data_source == "MusicBrainz"
        assert match.info.album_id == "pseudo"
        assert match.info.album == "In Bloom"


class TestMBMultiplePseudoReleases(PluginMixin):
    plugin = "musicbrainz"

    @pytest.fixture(autouse=True)
    def patch_get_release(
        self,
        monkeypatch,
        official_release: JSONDict,
        pseudo_release: JSONDict,
    ):
        def mock_get_release(_, album_id: str, **kwargs):
            if album_id == official_release["id"]:
                return official_release
            elif album_id == pseudo_release["id"]:
                return pseudo_release
            else:
                clone = deepcopy(pseudo_release)
                clone["id"] = album_id
                clone["text-representation"]["language"] = "jpn"
                return clone

        monkeypatch.setattr(
            "beetsplug._utils.musicbrainz.MusicBrainzAPI.get_release",
            mock_get_release,
        )

    @pytest.fixture(scope="class")
    def plugin_config(self):
        return {
            "pseudo_releases": {
                "scripts": ["Latn", "Dummy"],
                "multiple_allowed": True,
            }
        }

    @pytest.fixture
    def musicbrainz_plugin(self, config, plugin_config) -> MusicBrainzPlugin:
        self.config[self.plugin].set(plugin_config)
        config["import"]["languages"] = ["jp", "en"]
        return MusicBrainzPlugin()

    def test_multiple_releases(
        self,
        musicbrainz_plugin: MusicBrainzPlugin,
        official_release: JSONDict,
        pseudo_release: JSONDict,
    ):
        album_info = musicbrainz_plugin.album_for_id(official_release["id"])
        assert isinstance(album_info, MultiPseudoAlbumInfo)
        assert album_info.data_source == "MusicBrainz"
        assert len(album_info.unwrap()) == 2
        assert (
            album_info.unwrap()[0].album_id
            == "mockedid-0bc1-49eb-b8c4-34473d279a43"
        )
        assert (
            album_info.unwrap()[1].album_id
            == "dc3ee2df-0bc1-49eb-b8c4-34473d279a43"
        )


class TestMBPseudoReleasesCustomTagsOnly(TestMBPseudoMixin):
    @pytest.fixture(scope="class")
    def plugin_config(self):
        return {
            "pseudo_releases": {
                "scripts": ["Latn", "Dummy"],
                "custom_tags_only": True,
            }
        }

    def test_custom_tags(
        self,
        config,
        musicbrainz_plugin: MusicBrainzPlugin,
        official_release: JSONDict,
    ):
        config["import"]["languages"] = []
        album_info = self.get_album_info(musicbrainz_plugin, official_release)
        assert not isinstance(album_info, PseudoAlbumInfo)
        assert album_info.data_source == "MusicBrainz"
        assert album_info["album_transl"] == "In Bloom"
        assert album_info["album_artist_transl"] == "Lilas Ikuta"
        assert album_info.tracks[0]["title_transl"] == "In Bloom"
        assert album_info.tracks[0]["artist_transl"] == "Lilas Ikuta"

    def test_custom_tags_with_import_languages(
        self,
        config,
        musicbrainz_plugin: MusicBrainzPlugin,
        official_release: JSONDict,
    ):
        config["import"]["languages"] = []
        config["import"]["languages"] = ["en", "jp"]
        album_info = self.get_album_info(musicbrainz_plugin, official_release)
        assert not isinstance(album_info, PseudoAlbumInfo)
        assert album_info.data_source == "MusicBrainz"
        assert album_info["album_transl"] == "In Bloom"
        assert album_info["album_artist_transl"] == "Lilas Ikuta"
        assert album_info.tracks[0]["title_transl"] == "In Bloom"
        assert album_info.tracks[0]["artist_transl"] == "Lilas Ikuta"
