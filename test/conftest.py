import inspect
import os

import pytest

from beets.autotag import Distance
from beets.dbcore.query import Query
from beets.test._common import DummyIO
from beets.test.helper import RUNNING_IN_CI, ConfigMixin, TestHelper
from beets.test.helper import is_importable as check_import
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

    for item in items:
        if marker := item.get_closest_marker("requires_import"):
            force_ci = marker.kwargs.get("force_ci", True)
            if (
                force_ci
                and RUNNING_IN_CI
                # only apply this to our repository, to allow other projects to
                # run tests without installing all dependencies
                and os.environ.get("GITHUB_REPOSITORY", "") == "beetbox/beets"
            ):
                continue

            modname = marker.args[0]
            if not check_import(modname):
                test_name = item.nodeid.split("::", 1)[-1]
                item.add_marker(
                    pytest.mark.skip(
                        f"{modname!r} is not installed: {test_name}"
                    )
                )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "integration_test: mark a test as an integration test"
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
    return None


@pytest.fixture(autouse=True)
def clear_cached_classproperty():
    cached_classproperty.clear_cache()


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

    return check_import


# Shared fixtures amortize the expensive TestHelper setup across multiple tests.
#
# TestHelper resets and reloads the beets configuration, so recreating it for
# every test can slow large suites noticeably.
#
# Inheriting from TestHelper gives each test function isolated state. Use the
# fixtures below instead when a broader scope is safe and the suite benefits
# from reusing the same helper instance.
@pytest.fixture(scope="session")
def session_helper():
    """Share beets test state across the full test session.

    Use this for suites that tolerate shared library contents and global
    configuration. Tests should target specific records rather than assume a
    completely fresh overall state.
    """
    with TestHelper() as helper:
        yield helper


@pytest.fixture(scope="module")
def module_helper():
    """Share beets test state within one test module.

    Use this when tests in the same file can reuse setup and side effects, but
    later modules should still begin from a clean environment.
    """
    with TestHelper() as helper:
        yield helper


@pytest.fixture(scope="class")
def class_helper():
    """Share beets test state within one test class.

    Use this when methods in a class can build on the same setup, while nearby
    classes still need independent libraries, files, or configuration.
    """
    with TestHelper() as helper:
        yield helper
