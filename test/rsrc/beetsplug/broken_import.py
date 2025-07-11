# Leads to a `ModuleNotFoundError` on plugin load, which must not be confused with
# a plugin not found.
import beets.foobarbaz  # # noqa
from beets.plugins import BeetsPlugin


class TestPlugin(BeetsPlugin):
    pass
