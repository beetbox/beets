from sys import stderr

import confuse

from .util.deprecation import deprecate_imports

__version__ = "2.12.0"
__author__ = "Adrian Sampson <adrian@radbox.org>"


def __getattr__(name: str):
    """Handle deprecated imports."""
    return deprecate_imports(
        __name__, {"art": "beetsplug._utils", "vfs": "beetsplug._utils"}, name
    )


class IncludeLazyConfig(confuse.LazyConfig):
    """A version of Confuse's LazyConfig that also merges in data from
    YAML files specified in an `include` setting.
    """

    def read(self, user: bool = True, defaults: bool = True) -> None:
        super().read(user, defaults)

        try:
            for view in self["include"].sequence():
                self.set_file(view.as_filename())
        except confuse.NotFoundError:
            pass
        except confuse.ConfigReadError as err:
            stderr.write(f"configuration `import` failed: {err.reason}")


config = IncludeLazyConfig("beets", __name__)
