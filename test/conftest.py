import importlib.util
import inspect
import os
from functools import cache

import pytest

from beets.autotag.distance import Distance
from beets.dbcore.query import Query
from beets.test._common import DummyIO
from beets.test.helper import ConfigMixin
from beets.util import cached_classproperty


@cache
def _is_importable(modname: str) -> bool:
    return bool(importlib.util.find_spec(modname))


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

    for item in items:
        if marker := item.get_closest_marker("requires_import"):
            force_ci = marker.kwargs.get("force_ci", True)
            if (
                force_ci
                and os.environ.get("GITHUB_ACTIONS") == "true"
                # only apply this to our repository, to allow other projects to
                # run tests without installing all dependencies
                and os.environ.get("GITHUB_REPOSITORY", "") == "beetbox/beets"
            ):
                continue

            modname = marker.args[0]
            if not _is_importable(modname):
                test_name = item.nodeid.split("::", 1)[-1]
                item.add_marker(
                    pytest.mark.skip(
                        f"{modname!r} is not installed: {test_name}"
                    )
                )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration_test: mark a test as an integration test",
    )
    config.addinivalue_line(
        "markers",
        "on_lyrics_update: run test only when lyrics source code changes",
    )
    config.addinivalue_line(
        "markers",
        (
            "requires_import(module, force_ci=True): run test only if module"
            " is importable (use force_ci=False to allow CI to skip the test too)"
        ),
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


@pytest.fixture(scope="module")
def config():
    """Provide a fresh beets configuration for a module, when requested."""
    return ConfigMixin().config


@pytest.fixture
def io(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    capteesys: pytest.CaptureFixture[str],
) -> DummyIO:
    """Fixture for tests that need controllable stdin and captured stdout.

    This fixture builds a per-test ``DummyIO`` helper and exposes it to the
    test. When used on a test class, it attaches the helper as ``self.io``
    attribute to make it available to all test methods, including
    ``unittest.TestCase``-based ones.
    """
    io = DummyIO(monkeypatch, capteesys)

    if request.instance:
        request.instance.io = io

    return io


@pytest.fixture
def is_importable():
    """Fixture that provides a function to check if a module can be imported."""

    return _is_importable
