import os

import pytest


def pytest_runtest_setup(item: pytest.Item):
    """Skip integration tests if INTEGRATION_TEST environment variable is not set."""
    if os.environ.get("INTEGRATION_TEST"):
        return

    if next(item.iter_markers(name="integration_test"), None):
        pytest.skip(f"INTEGRATION_TEST=1 required: {item.nodeid}")
