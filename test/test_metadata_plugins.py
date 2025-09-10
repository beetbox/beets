from typing import Iterable

import pytest
from confuse import AttrDict

from beets import metadata_plugins
from beets.test.helper import PluginMixin


class ErrorMetadataMockPlugin(metadata_plugins.MetadataSourcePlugin):
    """A metadata source plugin that raises errors in all its methods."""

    def candidates(self, *args, **kwargs):
        raise ValueError("Mocked error")

    def item_candidates(self, *args, **kwargs):
        raise ValueError("Mocked error")

    def album_for_id(self, *args, **kwargs):
        raise ValueError("Mocked error")

    def track_for_id(self, *args, **kwargs):
        raise ValueError("Mocked error")

    def track_distance(self, *args, **kwargs):
        raise ValueError("Mocked error")

    def album_distance(self, *args, **kwargs):
        raise ValueError("Mocked error")


class TestMetadataPluginsException(PluginMixin):
    """Check that errors during the metadata plugins do not crash beets.
    They should be logged as errors instead.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        self.register_plugin(ErrorMetadataMockPlugin)
        yield
        self.unload_plugins()

    @pytest.mark.parametrize(
        "method_name,args",
        [
            ("candidates", ()),
            ("item_candidates", ()),
            ("album_for_id", ("some_id",)),
            ("track_for_id", ("some_id",)),
            ("track_distance", (None, AttrDict({"data_source": "mock"}))),
            ("album_distance", (None, AttrDict({"data_source": "mock"}), None)),
        ],
    )
    def test_error_handling_candidates(
        self,
        caplog,
        method_name,
        args,
    ):
        with caplog.at_level("ERROR"):
            # Call the method to trigger the error
            ret = getattr(metadata_plugins, method_name)(*args)
            if isinstance(ret, Iterable):
                list(ret)

            # Check that an error was logged
            assert len(caplog.records) == 1
            logs = [record.getMessage() for record in caplog.records]
            assert logs == ["Error in 'ErrorMetadataMockPlugin': Mocked error"]
            caplog.clear()
