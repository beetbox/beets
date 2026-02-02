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
        "method_name,error_method_name,args",
        [
            ("candidates", "candidates", ()),
            ("item_candidates", "item_candidates", ()),
            ("albums_for_ids", "albums_for_ids", (["some_id"],)),
            ("tracks_for_ids", "tracks_for_ids", (["some_id"],)),
            # Currently, singular methods call plural ones internally and log
            # errors from there
            ("album_for_id", "albums_for_ids", ("some_id", [])),
            ("track_for_id", "tracks_for_ids", ("some_id",)),
        ],
    )
    def test_logging(self, caplog, call_method, error_method_name):
        self.config["raise_on_error"] = False

        call_method()

        assert (
            f"Error in 'ErrorMetadataMock.{error_method_name}': Mocked error"
            in caplog.text
        )

    @pytest.mark.parametrize(
        "method_name,args",
        [
            ("candidates", ()),
            ("item_candidates", ()),
            ("album_for_id", ("some_id", [])),
            ("track_for_id", ("some_id",)),
        ],
    )
    def test_raising(self, call_method):
        self.config["raise_on_error"] = True

        with pytest.raises(ValueError, match="Mocked error"):
            call_method()
