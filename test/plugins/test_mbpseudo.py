import json
import pathlib

import pytest

from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.library import Item
from beets.test.helper import PluginMixin
from beetsplug._typing import JSONDict
from beetsplug.mbpseudo import (
    _STATUS_PSEUDO,
    MusicBrainzPseudoReleasePlugin,
    PseudoAlbumInfo,
)


class TestPseudoAlbumInfo:
    @pytest.fixture
    def official_release(self) -> AlbumInfo:
        return AlbumInfo(
            tracks=[TrackInfo(title="百花繚乱")],
            album_id="official",
            album="百花繚乱",
        )

    @pytest.fixture
    def pseudo_release(self) -> AlbumInfo:
        return AlbumInfo(
            tracks=[TrackInfo(title="In Bloom")],
            album_id="pseudo",
            album="In Bloom",
        )

    def test_album_id_always_from_pseudo(
        self, official_release: AlbumInfo, pseudo_release: AlbumInfo
    ):
        info = PseudoAlbumInfo(pseudo_release, official_release)
        info.use_official_as_ref()
        assert info.album_id == "pseudo"

    def test_get_attr_from_pseudo(
        self, official_release: AlbumInfo, pseudo_release: AlbumInfo
    ):
        info = PseudoAlbumInfo(pseudo_release, official_release)
        assert info.album == "In Bloom"

    def test_get_attr_from_official(
        self, official_release: AlbumInfo, pseudo_release: AlbumInfo
    ):
        info = PseudoAlbumInfo(pseudo_release, official_release)
        info.use_official_as_ref()
        assert info.album == info.get_official_release().album

    def test_determine_best_ref(
        self, official_release: AlbumInfo, pseudo_release: AlbumInfo
    ):
        info = PseudoAlbumInfo(
            pseudo_release, official_release, data_source="test"
        )
        item = Item()
        item["title"] = "百花繚乱"

        assert info.determine_best_ref([item]) == "official"

        info.use_pseudo_as_ref()
        assert info.data_source == "test"


@pytest.fixture(scope="module")
def rsrc_dir(pytestconfig: pytest.Config):
    return pytestconfig.rootpath / "test" / "rsrc" / "mbpseudo"


class TestMBPseudoPlugin(PluginMixin):
    plugin = "mbpseudo"

    @pytest.fixture(scope="class")
    def plugin_config(self):
        return {"scripts": ["Latn", "Dummy"]}

    @pytest.fixture(scope="class")
    def mbpseudo_plugin(self, plugin_config) -> MusicBrainzPseudoReleasePlugin:
        self.config[self.plugin].set(plugin_config)
        return MusicBrainzPseudoReleasePlugin()

    @pytest.fixture
    def official_release(self, rsrc_dir: pathlib.Path) -> JSONDict:
        info_json = (rsrc_dir / "official_release.json").read_text(
            encoding="utf-8"
        )
        return json.loads(info_json)

    @pytest.fixture
    def pseudo_release(self, rsrc_dir: pathlib.Path) -> JSONDict:
        info_json = (rsrc_dir / "pseudo_release.json").read_text(
            encoding="utf-8"
        )
        return json.loads(info_json)

    def test_scripts_init(
        self, mbpseudo_plugin: MusicBrainzPseudoReleasePlugin
    ):
        assert mbpseudo_plugin._scripts == ["Latn", "Dummy"]

    @pytest.mark.parametrize(
        "album_id",
        [
            "a5ce1d11-2e32-45a4-b37f-c1589d46b103",
            "-5ce1d11-2e32-45a4-b37f-c1589d46b103",
        ],
    )
    def test_extract_id_uses_music_brainz_pattern(
        self,
        mbpseudo_plugin: MusicBrainzPseudoReleasePlugin,
        album_id: str,
    ):
        if album_id.startswith("-"):
            assert mbpseudo_plugin._extract_id(album_id) is None
        else:
            assert mbpseudo_plugin._extract_id(album_id) == album_id

    def test_album_info_for_pseudo_release(
        self,
        mbpseudo_plugin: MusicBrainzPseudoReleasePlugin,
        pseudo_release: JSONDict,
    ):
        album_info = mbpseudo_plugin.album_info(pseudo_release["release"])
        assert not isinstance(album_info, PseudoAlbumInfo)
        assert album_info.data_source == "MusicBrainz"
        assert album_info.albumstatus == _STATUS_PSEUDO

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
        mbpseudo_plugin: MusicBrainzPseudoReleasePlugin,
        official_release: JSONDict,
        json_key: str,
    ):
        del official_release["release"]["release-relation-list"][0][json_key]

        album_info = mbpseudo_plugin.album_info(official_release["release"])
        assert not isinstance(album_info, PseudoAlbumInfo)
        assert album_info.data_source == "MusicBrainz"

    def test_interception_skip_when_script_doesnt_match(
        self,
        mbpseudo_plugin: MusicBrainzPseudoReleasePlugin,
        official_release: JSONDict,
    ):
        official_release["release"]["release-relation-list"][0]["release"][
            "text-representation"
        ]["script"] = "Null"

        album_info = mbpseudo_plugin.album_info(official_release["release"])
        assert not isinstance(album_info, PseudoAlbumInfo)
        assert album_info.data_source == "MusicBrainz"

    def test_interception(
        self,
        mbpseudo_plugin: MusicBrainzPseudoReleasePlugin,
        official_release: JSONDict,
        pseudo_release: JSONDict,
    ):
        mbpseudo_plugin._release_getter = (
            lambda album_id, includes: pseudo_release
        )
        album_info = mbpseudo_plugin.album_info(official_release["release"])
        assert isinstance(album_info, PseudoAlbumInfo)
        assert album_info.data_source == "MusicBrainz"
