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

from pathlib import Path
from typing import Iterator

import pytest
from confuse import Configuration

import beets
from beets.library import Library


@pytest.fixture(scope="session")
def resource_dir(pytestconfig: pytest.Config) -> Path:
    """
    A fixture returning the resource directory for tests.
    """

    return pytestconfig.rootpath / "test" / "rsrc"


@pytest.fixture
def config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Configuration]:
    """
    A fixture for Beets configuration.
    """

    # 'confuse' looks at `HOME`, so we set it to a tmpdir.
    monkeypatch.setenv("HOME", str(tmp_path))

    # Initialize configuration.
    config = beets.config
    config.sources = []
    config.read(user=False, defaults=True)

    # Set configuration defaults.
    config["plugins"] = []
    config["verbose"] = 1
    config["ui"]["color"] = False
    config["threaded"] = False
    config["directory"] = str(tmp_path)

    # Provide the configuration to the test.
    yield config

    # Reset the global configuration state.
    beets.config.clear()
    beets.config._materialized = False


@pytest.fixture
def library(
    tmp_path_factory: pytest.TempPathFactory,
    config: Configuration,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Library]:
    """
    A fixture for the Beets library.
    """

    # Beets needs a location to store library contents.
    lib_dir = tmp_path_factory.mktemp("lib_dir")
    monkeypatch.setenv("BEETSDIR", str(lib_dir))

    # Create the Beets library object.
    lib = Library(":memory:", str(lib_dir))

    # Provide the library to the test.
    yield lib

    # Clean up the library.
    lib._close()
