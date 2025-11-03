from typing import Iterable

import pytest

from beets import metadata_plugins
from beets.test.helper import PluginMixin


class ErrorMetadataMockPlugin(metadata_plugins.MetadataSourcePlugin):
    """A metadata source plugin that raises errors in all its methods."""

    data_source = "ErrorMetadataMockPlugin"

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
        ],
    )
    def test_logging(
        self,
        caplog,
        method_name,
        args,
    ):
        self.config["raise_on_error"] = False
        with caplog.at_level("ERROR"):
            # Call the method to trigger the error
            ret = getattr(metadata_plugins, method_name)(*args)
            if isinstance(ret, Iterable):
                list(ret)

            # Check that an error was logged
            assert len(caplog.records) >= 1
            logs = [record.getMessage() for record in caplog.records]
            for msg in logs:
                assert (
                    msg
                    == f"Error in 'ErrorMetadataMockPlugin.{method_name}': Mocked error"
                )

            caplog.clear()

    @pytest.mark.parametrize(
        "method_name,args",
        [
            ("candidates", ()),
            ("item_candidates", ()),
            ("album_for_id", ("some_id",)),
            ("track_for_id", ("some_id",)),
        ],
    )
    def test_raising(
        self,
        method_name,
        args,
    ):
        self.config["raise_on_error"] = True
        with pytest.raises(ValueError, match="Mocked error"):
            getattr(metadata_plugins, method_name)(*args) if not isinstance(
                args, Iterable
            ) else list(getattr(metadata_plugins, method_name)(*args))
