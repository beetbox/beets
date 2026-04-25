from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor as BaseThreadPoolExecutor
from threading import Event

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


def test_albums_for_ids_calls_each_plugin_once(monkeypatch):
    start_workers = Event()

    class Plugin:
        def __init__(self, name):
            self.data_source = name
            self.calls: list[list[str]] = []

        def albums_for_ids(self, ids):
            self.calls.append(list(ids))
            return [self.data_source]

    plugins = [Plugin("discogs"), Plugin("musicbrainz"), Plugin("tidal")]

    class PluginSequence:
        def __iter__(self):
            yield from plugins
            start_workers.set()

    class DelayedStartExecutor:
        def __init__(self):
            self._executor = BaseThreadPoolExecutor(max_workers=1)

        def submit(self, fn, *args, **kwargs):
            return self._executor.submit(self._run, fn, args, kwargs)

        def _run(self, fn, args, kwargs):
            start_workers.wait()
            return fn(*args, **kwargs)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self._executor.shutdown(wait=True)
            return False

    monkeypatch.setattr(
        metadata_plugins,
        "find_metadata_source_plugins",
        lambda: PluginSequence(),
    )
    monkeypatch.setattr(
        metadata_plugins, "ThreadPoolExecutor", DelayedStartExecutor
    )

    assert set(metadata_plugins.albums_for_ids(["42"])) == {
        "discogs",
        "musicbrainz",
        "tidal",
    }
    assert [plugin.calls for plugin in plugins] == [
        [["42"]],
        [["42"]],
        [["42"]],
    ]
