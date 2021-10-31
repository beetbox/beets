# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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


import confuse
import os
from sys import stderr

__version__ = '1.5.1'
__author__ = 'Adrian Sampson <adrian@radbox.org>'


class IncludeLazyConfig(confuse.LazyConfig):
    """A version of Confuse's LazyConfig that also merges in data from
    YAML files specified in an `include` setting.
    """
    def read(self, user=True, defaults=True):
        super().read(user, defaults)

        path = self.user_config_path()
        if not os.path.isfile(path):
            with open(path, 'w+') as file:
                file.write(self.dump())

        try:
            for view in self['include']:
                self.set_file(view.as_filename())
        except confuse.NotFoundError:
            pass
        except confuse.ConfigReadError as err:
            stderr.write("configuration `import` failed: {}"
                         .format(err.reason))


config = IncludeLazyConfig('beets', __name__)
