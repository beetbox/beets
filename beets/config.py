from sys import stderr

import confuse
from typing_extensions import override


class IncludeLazyConfig(confuse.LazyConfig):
    """A version of Confuse's LazyConfig that also merges in data from
    YAML files specified in an `include` setting.
    """

    @override
    def read(self, user: bool = True, defaults: bool = True) -> None:
        super().read(user, defaults)

        try:
            view: confuse.Subview
            for view in self["include"]:
                self.set_file(view.as_filename())
        except confuse.NotFoundError:
            pass
        except confuse.ConfigReadError as err:
            _ = stderr.write(f"configuration `import` failed: {err.reason}")


config: IncludeLazyConfig = IncludeLazyConfig("beets", __name__)
