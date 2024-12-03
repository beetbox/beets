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
from typing_extensions import TypeAlias

BASE = Path(__file__).parent.parent.absolute()
PYPROJECT = BASE / "pyproject.toml"
CHANGELOG = BASE / "docs" / "changelog.rst"

MD_CHANGELOG_SECTION_LIST = re.compile(r"- .+?(?=\n\n###|$)", re.DOTALL)
version_header = r"\d+\.\d+\.\d+ \([^)]+\)"
RST_LATEST_CHANGES = re.compile(
    rf"{version_header}\n--+\s+(.+?)\n\n+{version_header}", re.DOTALL
)
Replacement: TypeAlias = "tuple[str, str | Callable[[re.Match[str]], str]]"
RST_REPLACEMENTS: list[Replacement] = [
    (r"(?<=[\s(])`([^`]+)`(?=[^_])", r"``\1``"),  # ticks with verbatim ranges.
    (r":bug:`(\d+)`", r":bug: (#\1)"),  # Issue numbers.
    (r":user:`(\w+)`", r"@\1"),  # Users.
]
MD_REPLACEMENTS: list[Replacement] = [
    (r"^  ( *- )", r"\1"),  # remove list indentation
    (r"^(\w.+?):$", r"### \1"),  # make sections headers
    (r"^- `/?plugins/(\w+)`:?", r"- Plugin **`\1`**:"),  # highlight plugins
    (r"^- `(\w+)-cmd`:?", r"- Command **`\1`**:"),  # highlight commands
    (r"### [^\n]+\n+(?=### )", ""),  # remove empty sections
]


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

New features:
Bug fixes:
For packagers:
Other changes:

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
    return (
        subprocess.check_output(
            ["pandoc", "--from=rst", "--to=gfm", "--wrap=none"],
            input=text.encode(),
        )
        .decode()
        .strip()
    )


def get_changelog_contents() -> str | None:
    if m := RST_LATEST_CHANGES.search(CHANGELOG.read_text()):
        return m.group(1)

    return None


def changelog_as_markdown(rst: str) -> str:
    """Get the latest changelog entry as hacked up Markdown."""
    for pattern, repl in RST_REPLACEMENTS:
        rst = re.sub(pattern, repl, rst, flags=re.M)

    md = rst2md(rst)

    for pattern, repl in MD_REPLACEMENTS:
        md = re.sub(pattern, repl, md, flags=re.M)

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
    if changelog := get_changelog_contents():
        print(changelog_as_markdown(changelog))


if __name__ == "__main__":
    cli()
