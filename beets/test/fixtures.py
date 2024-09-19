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
This module provides `pytest`-based fixtures for testing Beets.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest
from confuse import Configuration

import beets
import beets.util as util
from beets.library import Library


@contextmanager
def setup_config(lib_dir: Path) -> Iterator[Configuration]:
    # Initialize configuration.
    config = beets.config
    config.sources = []
    config.read(user=False, defaults=True)

    # Set configuration defaults.
    config["plugins"] = []
    config["verbose"] = 1
    config["ui"]["color"] = False
    config["threaded"] = False
    config["directory"] = str(lib_dir)

    # Provide the configuration to the test.
    yield config

    # Reset the global configuration state.
    beets.config.clear()
    beets.config._materialized = False


@contextmanager
def setup_library(
    lib_dir: Path,
    db_loc: Path | None = None,
) -> Iterator[Library]:
    # Create the Beets library object.
    db_loc = util.bytestring_path(db_loc) if db_loc is not None else ":memory:"
    lib = Library(db_loc, str(lib_dir))

    # Provide the library to the test.
    yield lib

    # Clean up the library.
    lib._close()


@pytest.fixture(scope="session")
def resource_dir(pytestconfig: pytest.Config) -> Path:
    """
    The resource directory for tests.

    Tests requiring external data (e.g. audio files) can place them within the
    resource directory (located at `test/rsrc` in the repository) and then find
    them relative to the returned path.

    If the tests for a particular component or plugin require several files,
    they should be placed within an appropriately named subdirectory.

    :return: the path to `test/rsrc` in the repository.
    """

    return pytestconfig.rootpath / "test" / "rsrc"


@pytest.fixture
def config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Configuration]:
    """
    Prepare a pristine configuration for Beets.

    This will construct and return a fresh configuration object for Beets,
    containing the default settings for the Beets library and first-party
    plugins.

    Currently, Beets internally stores configuration in the `beets.config`
    global variable.  This fixture will reset it to the same configuration
    object that is returned.  Modifications in the object returned by this
    fixture will be reflected in `beets.config`.  However, it is recommended
    to avoid the global variable and work directly with the returned object
    whenever possible.
    """

    # 'confuse' looks at `HOME`, so we set it to a tmpdir.
    monkeypatch.setenv("HOME", str(tmp_path))
    with setup_config(tmp_path / "libdir") as config:
        yield config


@pytest.fixture
@pytest.mark.usefixtures("config")
def library(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Library]:
    # Beets needs a location to store library contents.
    lib_dir = tmp_path / "libdir"
    monkeypatch.setenv("BEETSDIR", str(lib_dir))

    with setup_library(lib_dir, db_loc=None) as library:
        yield library
