# This file is part of beets.
# Copyright 2014, Fabrice Laporte.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""Enrich path formatting with %bucket_alpha and %bucket_date functions
"""

from datetime import datetime
import logging
import re
import string
from beets import plugins
# from beets import config

log = logging.getLogger('beets')


def extract_years(lst):
    """Extract years from a list of strings"""

    def make_date(s):
        """Convert string representing a year to int
        """
        d = int(s)
        if d < 100:  # two digits imply it is 20th century
            d = 1900 + d
        return d

    res = []
    for bucket in lst:
        yearspan_str = re.findall('\d+', bucket)
        yearspan = [make_date(x) for x in yearspan_str]
        res.append(yearspan)
    return res


class BucketPlugin(plugins.BeetsPlugin):
    def __init__(self):
        super(BucketPlugin, self).__init__()
        self.template_funcs['bucket'] = self._tmpl_bucket

        self.config.add({
            'bucket_year': [],
            'bucket_alpha': [],
        })
        self.setup()

    def setup(self):
        """Setup plugin from config options
        """

        yearranges = extract_years(self.config['bucket_year'].get())
        self.yearbounds = sorted([y for ys in yearranges for y in ys])
        self.yearranges = [self.make_year_range(b) for b in yearranges]
        self.alpharanges = [self.make_alpha_range(b) for b in
                            self.config['bucket_alpha'].get()]

    def make_year_range(self, ys):
        """Express year-span as a list of years [from...to].
           If input year-span only contain the from year, the to is defined
           as the from year of the next year-span minus one.
        """
        if len(ys) == 1:  # miss upper bound
            lb_idx = self.yearbounds.index(ys[0])
            try:
                ys.append(self.yearbounds[lb_idx + 1])
            except:
                ys.append(datetime.now().year)
        return range(ys[0], ys[-1] + 1)

    def make_alpha_range(self, s):
        """Express chars range as a list of chars [from...to]
        """
        bucket = sorted([x for x in s.lower() if x.isalnum()])
        beginIdx = string.ascii_lowercase.index(bucket[0])
        endIdx = string.ascii_lowercase.index(bucket[-1])
        return string.ascii_lowercase[beginIdx:endIdx + 1]

    def find_bucket_timerange(self, date):
        """Find folder whose range contains date
        1960-1970
        60s-70s
        """
        for (i, r) in enumerate(self.yearranges):
            if int(date) in r:
                return self.config['bucket_year'].get()[i]
        return date

    def find_bucket_alpha(self, s):
        for (i, r) in enumerate(self.alpharanges):
            if s.lower()[0] in r:
                return self.config['bucket_alpha'].get()[i]
        return s[0].upper()

    def _tmpl_bucket(self, text, field=None):
        if not field and text.isdigit():
            field = 'year'

        if field == 'year':
            func = self.find_bucket_timerange
        else:
            func = self.find_bucket_alpha
        return func(text)
