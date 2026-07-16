#!/usr/bin/env python3

"""A tiny tool used to test the `convert` plugin. It copies a file and appends
a specified text tag.
"""

import os
import sys
from pathlib import Path


def convert(in_file: str, out_file: str, tag: str) -> None:
    """Copy `in_file` to `out_file` and append the string `tag`."""
    with Path(out_file).open("wb") as out_f, Path(in_file).open("rb") as in_f:
        out_f.write(in_f.read())
        out_f.write(os.fsencode(tag))


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2], sys.argv[3])
