#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""A utility script for automating the beets release process.
"""
import click
import os
import re
import subprocess
from contextlib import contextmanager
import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGELOG = os.path.join(BASE, 'docs', 'changelog.rst')


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
                r'__version__\s*=\s*u[\'"]([0-9\.]+)[\'"]',
                "__version__ = u'{version}'",
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
                r'\s*version\s*=\s*[\'"]([0-9\.]+)[\'"]',
                "    version='{version}',",
            )
        ]
    ),
]

GITHUB_USER = 'beetbox'
GITHUB_REPO = 'beets'


def bump_version(version):
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
            found = False
            for line in f:
                for pattern, template in locations:
                    match = re.match(pattern, line)
                    if match:
                        # Check that this version is actually newer.
                        old_version = match.group(1)
                        old_parts = [int(p) for p in old_version.split('.')]
                        assert version_parts > old_parts, \
                            "version must be newer than {}".format(
                                old_version
                            )

                        # Insert the new version.
                        out_lines.append(template.format(
                            version=version,
                            major=major,
                            minor=minor,
                        ) + '\n')

                        found = True
                        break

                else:
                    # Normal line.
                    out_lines.append(line)

            if not found:
                print("No pattern found in {}".format(filename))

        # Write the file back.
        with open(filename, 'w') as f:
            f.write(''.join(out_lines))

    # Generate bits to insert into changelog.
    header_line = '{} (in development)'.format(version)
    header = '\n\n' + header_line + '\n' + '-' * len(header_line) + '\n\n'
    header += 'Changelog goes here!\n'

    # Insert into the right place.
    with open(CHANGELOG) as f:
        contents = f.read()
    location = contents.find('\n\n')  # First blank line.
    contents = contents[:location] + header + contents[location:]

    # Write back.
    with open(CHANGELOG, 'w') as f:
        f.write(contents)


@release.command()
@click.argument('version')
def bump(version):
    """Bump the version number.
    """
    bump_version(version)


def get_latest_changelog():
    """Extract the first section of the changelog.
    """
    started = False
    lines = []
    with open(CHANGELOG) as f:
        for line in f:
            if re.match(r'^--+$', line.strip()):
                # Section boundary. Start or end.
                if started:
                    # Remove last line, which is the header of the next
                    # section.
                    del lines[-1]
                    break
                else:
                    started = True

            elif started:
                lines.append(line)
    return ''.join(lines).strip()


def rst2md(text):
    """Use Pandoc to convert text from ReST to Markdown.
    """
    pandoc = subprocess.Popen(
        ['pandoc', '--from=rst', '--to=markdown', '--no-wrap'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, _ = pandoc.communicate(text.encode('utf-8'))
    md = stdout.decode('utf-8').strip()

    # Fix up odd spacing in lists.
    return re.sub(r'^-   ', '- ', md, flags=re.M)


def changelog_as_markdown():
    """Get the latest changelog entry as hacked up Markdown.
    """
    rst = get_latest_changelog()

    # Replace plugin links with plugin names.
    rst = re.sub(r':doc:`/plugins/(\w+)`', r'``\1``', rst)

    # References with text.
    rst = re.sub(r':ref:`([^<]+)(<[^>]+>)`', r'\1', rst)

    # Other backslashes with verbatim ranges.
    rst = re.sub(r'(\s)`([^`]+)`([^_])', r'\1``\2``\3', rst)

    # Command links with command names.
    rst = re.sub(r':ref:`(\w+)-cmd`', r'``\1``', rst)

    # Bug numbers.
    rst = re.sub(r':bug:`(\d+)`', r'#\1', rst)

    # Users.
    rst = re.sub(r':user:`(\w+)`', r'@\1', rst)

    # Convert with Pandoc.
    md = rst2md(rst)

    # Restore escaped issue numbers.
    md = re.sub(r'\\#(\d+)\b', r'#\1', md)

    return md


@release.command()
def changelog():
    """Get the most recent version's changelog as Markdown.
    """
    print(changelog_as_markdown())


def get_version(index=0):
    """Read the current version from the changelog.
    """
    with open(CHANGELOG) as f:
        cur_index = 0
        for line in f:
            match = re.search(r'^\d+\.\d+\.\d+', line)
            if match:
                if cur_index == index:
                    return match.group(0)
                else:
                    cur_index += 1


@release.command()
def version():
    """Display the current version.
    """
    print(get_version())


@release.command()
def datestamp():
    """Enter today's date as the release date in the changelog.
    """
    dt = datetime.datetime.now()
    stamp = '({} {}, {})'.format(dt.strftime('%B'), dt.day, dt.year)
    marker = '(in development)'

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
                lines.append('-' * underline_length + '\n')
                underline_length = None
            else:
                lines.append(line)

    with open(CHANGELOG, 'w') as f:
        for line in lines:
            f.write(line)


@release.command()
def prep():
    """Run all steps to prepare a release.

    - Tag the commit.
    - Build the sdist package.
    - Generate the Markdown changelog to ``changelog.md``.
    - Bump the version number to the next version.
    """
    cur_version = get_version()

    # Tag.
    subprocess.check_output(['git', 'tag', 'v{}'.format(cur_version)])

    # Build.
    with chdir(BASE):
        subprocess.check_call(['python2', 'setup.py', 'sdist'])

    # Generate Markdown changelog.
    cl = changelog_as_markdown()
    with open(os.path.join(BASE, 'changelog.md'), 'w') as f:
        f.write(cl)

    # Version number bump.
    # FIXME It should be possible to specify this as an argument.
    version_parts = [int(n) for n in cur_version.split('.')]
    version_parts[-1] += 1
    next_version = u'.'.join(map(str, version_parts))
    bump_version(next_version)


@release.command()
def publish():
    """Unleash a release unto the world.

    - Push the tag to GitHub.
    - Upload to PyPI.
    """
    version = get_version(1)

    # Push to GitHub.
    with chdir(BASE):
        subprocess.check_call(['git', 'push'])
        subprocess.check_call(['git', 'push', '--tags'])

    # Upload to PyPI.
    path = os.path.join(BASE, 'dist', 'beets-{}.tar.gz'.format(version))
    subprocess.check_call(['twine', 'upload', path])


@release.command()
def ghrelease():
    """Create a GitHub release using the `github-release` command-line
    tool.

    Reads the changelog to upload from `changelog.md`. Uploads the
    tarball from the `dist` directory.
    """
    version = get_version(1)
    tag = 'v' + version

    # Load the changelog.
    with open(os.path.join(BASE, 'changelog.md')) as f:
        cl_md = f.read()

    # Create the release.
    subprocess.check_call([
        'github-release', 'release',
        '-u', GITHUB_USER, '-r', GITHUB_REPO,
        '--tag', tag,
        '--name', '{} {}'.format(GITHUB_REPO, version),
        '--description', cl_md,
    ])

    # Attach the release tarball.
    tarball = os.path.join(BASE, 'dist', 'beets-{}.tar.gz'.format(version))
    subprocess.check_call([
        'github-release', 'upload',
        '-u', GITHUB_USER, '-r', GITHUB_REPO,
        '--tag', tag,
        '--name', os.path.basename(tarball),
        '--file', tarball,
    ])


if __name__ == '__main__':
    release()
