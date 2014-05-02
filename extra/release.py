#!/usr/bin/env python3
"""A utility script for automating the beets release process.
"""
import click
import os
import re
import subprocess
from contextlib import contextmanager

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextmanager
def chdir(d):
    """A context manager that temporary changes the working directory.
    """
    olddir = os.getcwd()
    os.chdir(d)
    yield
    os.chdir(olddir)


@click.group()
def release():
    pass


# Locations (filenames and patterns) of the version number.
VERSION_LOCS = [
    (
        os.path.join(BASE, 'beets', '__init__.py'),
        [
            (
                r'__version__\s*=\s*[\'"]([0-9\.]+)[\'"]',
                "__version__ = '{version}'",
            )
        ]
    ),
    (
        os.path.join(BASE, 'docs', 'conf.py'),
        [
            (
                r'version\s*=\s*[\'"]([0-9\.]+)[\'"]',
                "version = '{minor}'",
            ),
            (
                r'release\s*=\s*[\'"]([0-9\.]+)[\'"]',
                "release = '{version}'",
            ),
        ]
    ),
    (
        os.path.join(BASE, 'setup.py'),
        [
            (
                r'version\s*=\s*[\'"]([0-9\.]+)[\'"]',
                "    version='{minor}',",
            )
        ]
    ),
]

@release.command()
@click.argument('version')
def bump(version):
    """Update the version number in setup.py, docs config, changelog,
    and root module.
    """
    version_parts = [int(p) for p in version.split('.')]
    assert len(version_parts) == 3, "invalid version number"
    minor = '{}.{}'.format(*version_parts)
    major = '{}'.format(*version_parts)

    # Replace the version each place where it lives.
    for filename, locations in VERSION_LOCS:
        # Read and transform the file.
        out_lines = []
        with open(filename) as f:
            for line in f:
                for pattern, template in locations:
                    match = re.match(pattern, line)
                    if match:
                        # Check that this version is actually newer.
                        old_version = match.group(1)
                        old_parts = [int(p) for p in old_version.split('.')]
                        assert version_parts > old_parts, \
                                "version must be newer than {}".format(old_version)

                        # Insert the new version.
                        out_lines.append(template.format(
                            version=version,
                            major=major,
                            minor=minor,
                        ) + '\n')

                        break
                    
                else:
                    # Normal line.
                    out_lines.append(line)

        # Write the file back.
        with open(filename, 'w') as f:
            f.write(''.join(out_lines))
    
    # Generate bits to insert into changelog.
    header_line = '{} (in development)'.format(version)
    header = '\n\n' + header_line + '\n' + '-' * len(header_line) + '\n\n'
    header += 'Changelog goes here!\n'

    # Insert into the right place.
    changelog = os.path.join(BASE, 'docs', 'changelog.rst')
    with open(changelog) as f:
        contents = f.read()
    location = contents.find('\n\n')  # First blank line.
    contents = contents[:location] + header + contents[location:]

    # Write back.
    with open(changelog, 'w') as f:
        f.write(contents)


@release.command()
def build():
    """Use `setup.py` to build a source tarball.
    """
    with chdir(BASE):
        subprocess.check_call(['python2', 'setup.py', 'sdist'])


if __name__ == '__main__':
    release()
