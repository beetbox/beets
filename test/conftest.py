# This file is part of beets.
# Copyright 2024, Arav K.
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

"""
Automatic configuration for `pytest`.
"""

import os

import pytest

# Pull in Beets' test fixtures.
pytest_plugins = "beets.test.fixtures"


def pytest_runtest_setup(item: pytest.Item):
    """Skip integration tests if INTEGRATION_TEST environment variable is not set."""
    if os.environ.get("INTEGRATION_TEST"):
        return

    if next(item.iter_markers(name="integration_test"), None):
        pytest.skip(f"INTEGRATION_TEST=1 required: {item.nodeid}")
