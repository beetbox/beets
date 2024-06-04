#!/usr/bin/env python3

"""A utility script for automating the beets release process.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import click
from packaging.version import Version, parse

BASE = Path(__file__).parent.parent.absolute()
BEETS_INIT = BASE / "beets" / "__init__.py"


def update_docs_config(text: str, new: Version) -> str:
    new_major_minor = f"{new.major}.{new.minor}"
    text = re.sub(r"(?<=version = )[^\n]+", f'"{new_major_minor}"', text)
    return re.sub(r"(?<=release = )[^\n]+", f'"{new}"', text)


def update_changelog(text: str, new: Version) -> str:
    new_header = f"{new} ({datetime.now(timezone.utc).date():%B %d, %Y})"
    return re.sub(
        # do not match if the new version is already present
        r"\nUnreleased\n--+\n",
        rf"""
Unreleased
----------

Changelog goes here! Please add your entry to the bottom of one of the lists below!

{new_header}
{'-' * len(new_header)}
""",
        text,
    )


UpdateVersionCallable = Callable[[str, Version], str]
FILENAME_AND_UPDATE_TEXT: list[tuple[Path, UpdateVersionCallable]] = [
    (
        BEETS_INIT,
        lambda text, new: re.sub(
            r"(?<=__version__ = )[^\n]+", f'"{new}"', text
        ),
    ),
    (BASE / "docs" / "changelog.rst", update_changelog),
    (BASE / "docs" / "conf.py", update_docs_config),
]

GITHUB_USER = "beetbox"
GITHUB_REPO = "beets"


def validate_new_version(
    ctx: click.Context, param: click.Argument, value: Version
) -> Version:
    """Validate the version is newer than the current one."""
    with BEETS_INIT.open() as f:
        contents = f.read()

    m = re.search(r'(?<=__version__ = ")[^"]+', contents)
    assert m, "Current version not found in __init__.py"
    current = parse(m.group())

    if not value > current:
        msg = f"version must be newer than {current}"
        raise click.BadParameter(msg)

    return value


def bump_version(new: Version) -> None:
    """Update the version number in specified files."""
    for path, perform_update in FILENAME_AND_UPDATE_TEXT:
        with path.open("r+") as f:
            contents = f.read()
            f.seek(0)
            f.write(perform_update(contents, new))
            f.truncate()


@click.group()
def cli():
    pass


@cli.command()
@click.argument("version", type=Version, callback=validate_new_version)
def bump(version: Version) -> None:
    """Bump the version in project files."""
    bump_version(version)


if __name__ == "__main__":
    cli()
