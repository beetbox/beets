# This file is part of beets.
# Copyright 2016-2019, Adrian Sampson.
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

import warnings
warnings.warn(
    "beets.util.confit is deprecated; use confuse instead",
    # Show the location of the `import confit` statement as the warning's
    # source, rather than this file, such that the offending module can be
    # identified easily.
    stacklevel=2,
)

# Import everything from the confuse module into this module.
for key, value in confuse.__dict__.items():
    if key not in ['__name__']:
        globals()[key] = value


# Cleanup namespace.
del key, value, warnings, confuse
