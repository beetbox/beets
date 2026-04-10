import pytest

from beets.test.helper import PluginTestCase
from beets.ui import UserError
from beetsplug.rewrite import RewritePlugin


class RewritePluginTest(PluginTestCase):
    plugin = "rewrite"
    preload_plugin = False

    def test_artist_rewrite_applies_to_artist_albumartist_and_album_fields(
        self,
    ):
        with self.configure_plugin({"artist .*jimi hendrix.*": "Jimi Hendrix"}):
            item = self.add_item(
                artist="The Jimi Hendrix Experience",
                albumartist="The Jimi Hendrix Experience",
            )
            album = self.lib.add_album([item])

            assert item.artist == "Jimi Hendrix"
            assert item.albumartist == "Jimi Hendrix"
            assert album.evaluate_template("$albumartist") == "Jimi Hendrix"

    def test_rewrite_all_matching_rules(self):
        with self.configure_plugin(
            {
                "artist .*hendrix.*": "hendrix catalog",
                "artist .*catalog.*": "Experience catalog",
            }
        ):
            item = self.add_item(
                artist="The Jimi Hendrix Experience",
                albumartist="The Jimi Hendrix Experience",
            )

            assert item.artist == "Experience catalog"

    def test_rewrite_is_case_insensitive_and_leaves_non_matches_unchanged(
        self,
    ):
        with self.configure_plugin(
            {"artist odd eye circle": "LOONA / ODD EYE CIRCLE"}
        ):
            matching_item = self.add_item(
                artist="ODD EYE CIRCLE",
                albumartist="ODD EYE CIRCLE",
            )
            other_item = self.add_item(artist="ARTMS", albumartist="ARTMS")

            assert matching_item.artist == "LOONA / ODD EYE CIRCLE"
            assert other_item.artist == "ARTMS"

    def test_rewrite_applied_to_all_list_values(self):
        with self.configure_plugin(
            {"genres rock": "Classic Rock", "genres pop": "Pop"}
        ):
            item = self.add_item(genres=["rock", "pop", "techno"])

            assert item.genres == ["Classic Rock", "Pop", "techno"]

    def test_invalid_rewrite_spec_raises_user_error(self):
        self.config[self.plugin].set({"artist": "Jimi Hendrix"})

        with pytest.raises(UserError, match="invalid rewrite specification"):
            RewritePlugin()

    def test_invalid_field_name_raises_user_error(self):
        self.config[self.plugin].set({"not_a_field rock": "Classic Rock"})

        with pytest.raises(
            UserError, match="invalid field name \\(not_a_field\\) in rewriter"
        ):
            RewritePlugin()
