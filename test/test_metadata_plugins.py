from collections.abc import Iterable

import pytest

from beets import metadata_plugins
from beets.test.helper import PluginMixin


class ErrorMetadataMockPlugin(metadata_plugins.MetadataSourcePlugin):
    """A metadata source plugin that raises errors in all its methods."""

    def candidates(self, *args, **kwargs):
        raise ValueError("Mocked error")

    def item_candidates(self, *args, **kwargs):
        for i in range(3):
            raise ValueError("Mocked error")
            yield  # This is just to make this a generator

    def album_for_id(self, *args, **kwargs):
        raise ValueError("Mocked error")

    def track_for_id(self, *args, **kwargs):
        raise ValueError("Mocked error")


class TestMetadataPluginsException(PluginMixin):
    """Check that errors during the metadata plugins do not crash beets.
    They should be logged as errors instead.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        metadata_plugins.find_metadata_source_plugins.cache_clear()
        metadata_plugins.get_metadata_source.cache_clear()
        self.register_plugin(ErrorMetadataMockPlugin)
        yield
        self.unload_plugins()

    @pytest.fixture
    def call_method(self, method_name, args):
        def _call():
            result = getattr(metadata_plugins, method_name)(*args)
            return list(result) if isinstance(result, Iterable) else result

        return _call

    @pytest.mark.parametrize(
        "method_name,args",
        [
            ("candidates", ()),
            ("item_candidates", ()),
            ("albums_for_ids", (["some_id"],)),
            ("tracks_for_ids", (["some_id"],)),
            ("album_for_id", ("some_id", "ErrorMetadataMock")),
            ("track_for_id", ("some_id", "ErrorMetadataMock")),
        ],
    )
    def test_logging(self, caplog, call_method, method_name):
        self.config["raise_on_error"] = False

        call_method()

        assert (
            f"Error in 'ErrorMetadataMock.{method_name}': Mocked error"
            in caplog.text
        )

    @pytest.mark.parametrize(
        "method_name,args",
        [
            ("candidates", ()),
            ("item_candidates", ()),
            ("albums_for_ids", (["some_id"],)),
            ("tracks_for_ids", (["some_id"],)),
            ("album_for_id", ("some_id", "ErrorMetadataMock")),
            ("track_for_id", ("some_id", "ErrorMetadataMock")),
        ],
    )
    def test_raising(self, call_method):
        self.config["raise_on_error"] = True

        with pytest.raises(ValueError, match="Mocked error"):
            call_method()


class TestSearchApiMetadataSourcePlugin(PluginMixin):
    plugin = "none"
    preload_plugin = False

    class RaisingSearchApiMetadataMockPlugin(
        metadata_plugins.SearchApiMetadataSourcePlugin[
            metadata_plugins.IDResponse
        ]
    ):
        def get_search_query_with_filters(self, _):
            return "", {}

        def get_search_response(self, _):
            raise ValueError("Search failure")

        def album_for_id(self, _):
            return None

        def track_for_id(self, _):
            return None

    @pytest.fixture
    def search_plugin(self):
        return self.RaisingSearchApiMetadataMockPlugin()

    def test_search_api_returns_empty_when_raise_on_error_disabled(
        self, config, search_plugin, caplog
    ):
        config["raise_on_error"] = False

        assert search_plugin._search_api("track", "query", {}) == ()
        assert "Search failure" in caplog.text

    def test_search_api_raises_when_raise_on_error_enabled(
        self, config, search_plugin
    ):
        config["raise_on_error"] = True

        with pytest.raises(ValueError, match="Search failure"):
            search_plugin._search_api("track", "query", {})
