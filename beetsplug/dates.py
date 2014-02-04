

""Beetsplugin for searching in Date ranges.
"""

from beets.plugins import BeetsPlugin
from beets.dbcore.query import StringFieldQuery
import beets
import dateslib
import datetime,time


class DatesQuery(StringFieldQuery):
    @classmethod
    def value_match(self, pattern, val):
        b, e = dateslib.inputstring(pattern)
        valf = float(val)
        if b <= valf <= e:
            return pattern


class DatesPlugin(BeetsPlugin):
    def __init__(self):
        super(DatesPlugin, self).__init__()
        self.config.add({
            'prefix': '=',

        })

    def queries(self):
        prefix = beets.config['dates']['prefix'].get(basestring)
        return {prefix: DatesQuery}
