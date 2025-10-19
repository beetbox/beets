import inspect
import os

import pytest

from beets.autotag.distance import Distance
from beets.dbcore.query import Query
from beets.util import cached_classproperty


def skip_marked_items(items: list[pytest.Item], marker_name: str, reason: str):
    for item in (i for i in items if i.get_closest_marker(marker_name)):
        test_name = item.nodeid.split("::", 1)[-1]
        item.add_marker(pytest.mark.skip(f"{reason}: {test_name}"))


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
):
    if not os.environ.get("INTEGRATION_TEST") == "true":
        skip_marked_items(
            items, "integration_test", "INTEGRATION_TEST=1 required"
        )

    if not os.environ.get("LYRICS_UPDATED") == "true":
        skip_marked_items(
            items, "on_lyrics_update", "No change in lyrics source code"
        )


def pytest_make_parametrize_id(config, val, argname):
    """Generate readable test identifiers for pytest parametrized tests.

    Provides custom string representations for:
    - Query classes/instances: use class name
    - Lambda functions: show abbreviated source
    - Other values: use standard repr()
    """
    if inspect.isclass(val) and issubclass(val, Query):
        return val.__name__

    if inspect.isfunction(val) and val.__name__ == "<lambda>":
        return inspect.getsource(val).split("lambda")[-1][:30]

    return repr(val)


def pytest_assertrepr_compare(op, left, right):
    if isinstance(left, Distance) or isinstance(right, Distance):
        return [f"Comparing Distance: {float(left)} {op} {float(right)}"]


@pytest.fixture(autouse=True)
def clear_cached_classproperty():
    cached_classproperty.cache.clear()
