from confuse import ConfigValueError

from beets.dbcore import types
from beets.plugins import BeetsPlugin


class TypesPlugin(BeetsPlugin):
    @property
    def item_types(self):
        return self._types()

    @property
    def album_types(self):
        return self._types()

    def _types(self):
        if not self.config.exists():
            return {}

        mytypes = {}
        for key, value in self.config.items():
            if value.get() == "int":
                mytypes[key] = types.INTEGER
            elif value.get() == "float":
                mytypes[key] = types.FLOAT
            elif value.get() == "bool":
                mytypes[key] = types.BOOLEAN
            elif value.get() == "date":
                mytypes[key] = types.DATE
            else:
                raise ConfigValueError(
                    f"unknown type '{value}' for the '{key}' field"
                )
        return mytypes
