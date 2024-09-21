#!/usr/bin/env python3

"""A utility script for automating the beets release process."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import click
import tomli
from packaging.version import Version, parse

BASE = Path(__file__).parent.parent.absolute()
PYPROJECT = BASE / "pyproject.toml"
CHANGELOG = BASE / "docs" / "changelog.rst"

MD_CHANGELOG_SECTION_LIST = re.compile(r"- .+?(?=\n\n###|$)", re.DOTALL)
version_header = r"\d+\.\d+\.\d+ \([^)]+\)"
RST_LATEST_CHANGES = re.compile(
    rf"{version_header}\n--+\s+(.+?)\n\n+{version_header}", re.DOTALL
)


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
        PYPROJECT,
        lambda text, new: re.sub(r"(?<=\nversion = )[^\n]+", f'"{new}"', text),
    ),
    (
        BASE / "beets" / "__init__.py",
        lambda text, new: re.sub(
            r"(?<=__version__ = )[^\n]+", f'"{new}"', text
        ),
    ),
    (CHANGELOG, update_changelog),
    (BASE / "docs" / "conf.py", update_docs_config),
]


def validate_new_version(
    ctx: click.Context, param: click.Argument, value: Version
) -> Version:
    """Validate the version is newer than the current one."""
    with PYPROJECT.open("rb") as f:
        current = parse(tomli.load(f)["tool"]["poetry"]["version"])

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


def rst2md(text: str) -> str:
    """Use Pandoc to convert text from ReST to Markdown."""
    # Other backslashes with verbatim ranges.
    rst = re.sub(r"(?<=[\s(])`([^`]+)`(?=[^_])", r"``\1``", text)

    # Bug numbers.
    rst = re.sub(r":bug:`(\d+)`", r":bug: (#\1)", rst)

    # Users.
    rst = re.sub(r":user:`(\w+)`", r"@\1", rst)
    return (
        subprocess.check_output(
            ["/usr/bin/pandoc", "--from=rst", "--to=gfm", "--wrap=none"],
            input=rst.encode(),
        )
        .decode()
        .strip()
    )


def changelog_as_markdown() -> str:
    """Get the latest changelog entry as hacked up Markdown."""
    with CHANGELOG.open() as f:
        contents = f.read()

    m = RST_LATEST_CHANGES.search(contents)
    rst = m.group(1) if m else ""

    # Convert with Pandoc.
    md = rst2md(rst)

    # Make sections stand out
    md = re.sub(r"^(\w.+?):$", r"### \1", md, flags=re.M)

    # Highlight plugin names
    md = re.sub(
        r"^- `/?plugins/(\w+)`:?", r"- Plugin **`\1`**:", md, flags=re.M
    )

    # Highlights command names.
    md = re.sub(r"^- `(\w+)-cmd`:?", r"- Command **`\1`**:", md, flags=re.M)

    # sort list items alphabetically for each of the sections
    return MD_CHANGELOG_SECTION_LIST.sub(
        lambda m: "\n".join(sorted(m.group().splitlines())), md
    )


@click.group()
def cli():
    pass


@cli.command()
@click.argument("version", type=Version, callback=validate_new_version)
def bump(version: Version) -> None:
    """Bump the version in project files."""
    bump_version(version)


@cli.command()
def changelog():
    """Get the most recent version's changelog as Markdown."""
    print(changelog_as_markdown())


if __name__ == "__main__":
    cli()
