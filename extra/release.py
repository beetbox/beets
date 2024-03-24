#!/usr/bin/env python3

"""A utility script for automating the beets release process.
"""
import argparse
import datetime
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGELOG = os.path.join(BASE, "docs", "changelog.rst")
parser = argparse.ArgumentParser()
parser.add_argument("version", type=str)

# Locations (filenames and patterns) of the version number.
VERSION_LOCS = [
    (
        os.path.join(BASE, "beets", "__init__.py"),
        [
            (
                r'__version__\s*=\s*[\'"]([0-9\.]+)[\'"]',
                "__version__ = '{version}'",
            )
        ],
    ),
    (
        os.path.join(BASE, "docs", "conf.py"),
        [
            (
                r'version\s*=\s*[\'"]([0-9\.]+)[\'"]',
                "version = '{minor}'",
            ),
            (
                r'release\s*=\s*[\'"]([0-9\.]+)[\'"]',
                "release = '{version}'",
            ),
        ],
    ),
    (
        os.path.join(BASE, "setup.py"),
        [
            (
                r'\s*version\s*=\s*[\'"]([0-9\.]+)[\'"]',
                "    version='{version}',",
            )
        ],
    ),
]

GITHUB_USER = "beetbox"
GITHUB_REPO = "beets"


def bump_version(version: str):
    """Update the version number in setup.py, docs config, changelog,
    and root module.
    """
    version_parts = [int(p) for p in version.split(".")]
    assert len(version_parts) == 3, "invalid version number"
    minor = "{}.{}".format(*version_parts)
    major = "{}".format(*version_parts)

    # Replace the version each place where it lives.
    for filename, locations in VERSION_LOCS:
        # Read and transform the file.
        out_lines = []
        with open(filename) as f:
            found = False
            for line in f:
                for pattern, template in locations:
                    match = re.match(pattern, line)
                    if match:
                        # Check that this version is actually newer.
                        old_version = match.group(1)
                        old_parts = [int(p) for p in old_version.split(".")]
                        assert (
                            version_parts > old_parts
                        ), "version must be newer than {}".format(old_version)

                        # Insert the new version.
                        out_lines.append(
                            template.format(
                                version=version,
                                major=major,
                                minor=minor,
                            )
                            + "\n"
                        )

                        found = True
                        break
                else:
                    # Normal line.
                    out_lines.append(line)
            if not found:
                print(f"No pattern found in {filename}")
        # Write the file back.
        with open(filename, "w") as f:
            f.write("".join(out_lines))

    update_changelog(version)


def update_changelog(version: str):
    # Generate bits to insert into changelog.
    header_line = f"{version} (in development)"
    header = "\n\n" + header_line + "\n" + "-" * len(header_line) + "\n\n"
    header += (
        "Changelog goes here! Please add your entry to the bottom of"
        " one of the lists below!\n"
    )
    # Insert into the right place.
    with open(CHANGELOG) as f:
        contents = f.readlines()

    contents = [
        line
        for line in contents
        if not re.match(r"Changelog goes here!.*", line)
    ]
    contents = "".join(contents)
    contents = re.sub("\n{3,}", "\n\n", contents)

    location = contents.find("\n\n")  # First blank line.
    contents = contents[:location] + header + contents[location:]
    # Write back.
    with open(CHANGELOG, "w") as f:
        f.write(contents)


def datestamp():
    """Enter today's date as the release date in the changelog."""
    dt = datetime.datetime.now()
    stamp = "({} {}, {})".format(dt.strftime("%B"), dt.day, dt.year)
    marker = "(in development)"

    lines = []
    underline_length = None
    with open(CHANGELOG) as f:
        for line in f:
            if marker in line:
                # The header line.
                line = line.replace(marker, stamp)
                lines.append(line)
                underline_length = len(line.strip())
            elif underline_length:
                # This is the line after the header. Rewrite the dashes.
                lines.append("-" * underline_length + "\n")
                underline_length = None
            else:
                lines.append(line)

    with open(CHANGELOG, "w") as f:
        for line in lines:
            f.write(line)


def prep(args: argparse.Namespace):
    # Version number bump.
    datestamp()
    bump_version(args.version)


if __name__ == "__main__":
    args = parser.parse_args()
    prep(args)
