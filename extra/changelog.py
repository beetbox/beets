#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""A tool for generating changelog entries.
See more instructions at docs/unreleased-changes/README.md
"""
import yaml
import os
import sys
import subprocess
import argparse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGES = os.path.join(BASE, 'docs', 'unreleased-changes')

# Types of changelog entries.
TYPES = ['bugfix', 'feature', 'change', 'newplugin']

# List of all built-in plugins.
PLUGINS = ['plugin/' + os.path.splitext(x)[0]
           for x in os.listdir(os.path.join(BASE, 'beetsplug'))
           if not x.endswith('.pyc') and not x.startswith('_')]

# Components of beets that can be affected by changes.
CORE_COMPONENTS = ['import', 'data', 'docs', 'dev']
COMPONENTS = CORE_COMPONENTS + PLUGINS


class ChangelogEntry(object):
    def __init__(self, title, pull_request, type, username=None,
                 components=None, related=None):
        self.title = title
        self.pr = pull_request
        self.type = type
        self.username = username
        self.components = components or []
        self.related = related or []

    def as_dict(self):
        entry = {
            'title': self.title,
            'pull_request': self.pr,
            'type': self.type,
        }
        if username:
            entry['username'] = username
        if components:
            entry['components'] = components
        return entry

    def write(self, path):
        with open(path, 'wb') as entry_file:
            yaml.safe_dump(self.as_dict(), entry_file, encoding='utf-8',
                           explicit_start=True)

    def print(self):
        print(yaml.safe_dump(self.as_dict(), explicit_start=True))

    def affects(self):
        core = [x for x in sorted(self.components) if '/' not in x]
        plugins = [':doc:`/plugins/{}`'.format(x.split('/')[1])
                   for x in sorted(self.components)
                   if x.startswith('plugin/')]
        return core + plugins

    def issues(self):
        return [':bug:`{}`'.format(i) for i in [self.pr] + self.related]


def guess_name():
    log_entry = subprocess.Popen(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                                 stdout=subprocess.PIPE).stdout.read()
    return log_entry.rstrip().decode('utf-8')


def guess_title():
    log_entry = subprocess.Popen(['git', 'log', '--format=%s', '-1'],
                                 stdout=subprocess.PIPE).stdout.read()
    return log_entry.rstrip().decode('utf-8')


def guess_username():
    return os.getenv(
            'GITHUB_USER',
            subprocess.Popen(
                ['git', 'config', 'github.user'],
                stdout=subprocess.PIPE).stdout.read())


def ask_value(name, default=None, convert=str):
    prompt = '    {}>  '.format(name)
    if default:
        print("Default (press enter to accept): {}".format(default))

    while True:
        value = input(prompt)
        if default and not value:
            print('    {} = {}'.format(name, default))
            return default
        else:
            try:
                converted = convert(value)
                if converted != value:
                    print('    {} = {}'.format(name, converted))
                return converted
            except Exception as e:
                print(e)
                print("That value wasn't valid!")


def convert_components(components_string):
    components = components_string.split()
    for component in components:
        if component not in COMPONENTS:
            raise ValueError("Unknown component '{}'".format(component))
    return components


def convert_related(related_string):
    return [int(issue) for issue in related_string.split()]


def convert_type(change_type):
    try:
        number = int(change_type) - 1
        if number < 0 or number > len(TYPES):
            raise RuntimeError("Out of range: 1 to {}".format(len(TYPES)))
        change_type = TYPES[number]
    except ValueError:
        if change_type not in TYPES:
            raise ValueError("Unknown type '{}'".format(change_type))
    return change_type


def convert_name(name):
    if name == 'HEAD':
        raise ValueError('HEAD is not a branch name (git has detached HEAD?)')
    return name.replace(' ', '-')


def convert_title(title):
    if not title:
        raise ValueError('We need to have a title')
    if len(title) < 10:
        raise ValueError('That title needs to be a bit longer')
    if len(title) > 100:
        raise ValueError('That title is a bit too long!')
    return title


def parse_arguments():
    parser = argparse.ArgumentParser(description='Create a changelog entry.')
    parser.add_argument('pull_request', type=int,
                        help='pull request number on beetbox/beets')
    parser.add_argument('--type', choices=TYPES,
                        help='type of change')
    parser.add_argument('-m', '--title',
                        help='short description of the change')
    parser.add_argument('--author',
                        help='GitHub username of the author')
    parser.add_argument('--component', action='append', choices=COMPONENTS,
                        help='component affected by the change'
                             ' (can be specified multiple times).')
    parser.add_argument('-i', '--related', action='append', type=int,
                        help='number of a related issue on beetbox/beets'
                             ' (can be specified multiple times).')
    parser.add_argument('--name',
                        help='name for the entry (filename without suffix)')
    parser.add_argument('--force', action='store_true', default=False,
                        help='overwrite existing changelog entry')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_arguments()

    name = convert_name(args.name or guess_name())
    path = os.path.join(CHANGES, name + '.yaml')
    if os.path.exists(path):
        print("WARNING: The changelog entry already exists: {}".format(path))
        if not args.force:
            print("Overwrite it with --force or choose a new --name")
            sys.exit(1)

    change_type = args.type
    if not args.type:
        print(">> What kind of change is this?")
        print("    1. bugfix    : fixes a bug in beets")
        print("    2. feature   : adds new functionality")
        print("    3. change    : changes how an existing feature is used")
        print("    4. newplugin : adds a new plugin to beets")
        print()
        change_type = ask_value('type', 'bugfix', convert_type)
        print()
        print()

    related = args.related
    if not args.related:
        print(">> Are there any related issues on beetbox/beets?")
        print("  - Separate multiple issue numbers with spaces.")
        print("  - It's OK to leave this blank.")
        print()
        related = ask_value('related', None, convert_related)
        print()
        print()

    title = args.title
    if not args.title:
        print(">> Briefly describe the change.")
        print("  - Describe what was changed rather than how it was changed.")
        print("  - Imagine that the reader doesn't have context.")
        print("  - You can use reStructuredText markup syntax.")
        print()
        title = ask_value('title', guess_title(), convert_title)
        print()
        print()

    username = None
    if args.author:
        username = args.author
    else:
        print(">> Let us know the author's GitHub username."
              " We'd love to give credit for this change!")
        print("  - You can tell us a default value by:")
        print("    * setting the GITHUB_USER environment variable")
        print("    * running: git config --global github.user USERNAME")
        print("  - It's OK to leave this blank.")
        print()
        username = ask_value('author', guess_username())
        print()
        print()

    components = args.component
    if not args.component:
        print(">> Which part of beets is affected by this change?")
        print("  - Separate multiple components with spaces.")
        print("  - Your choices:")
        print("    * plugin/* : affects a plugin (e.g. plugin/bpd)")
        print("    * import   : affects the music importer")
        print("    * data     : affects the database or music metadata")
        print("    * docs     : mostly changes documentation")
        print("    * dev      : mostly relevant to plugin developers")
        print("  - It's OK to leave this blank.")
        print()
        components = ask_value('components', None, convert_components)
        print()
        print()

    entry = ChangelogEntry(
                title=title,
                pull_request=args.pull_request,
                type=change_type,
                username=username,
                components=components,
                related=related)

    print()
    entry.write(path)
    print('Created {}'.format(os.path.relpath(path)))
    print('Now commit the new file and push it to include it in your PR.')
    print('Thanks for your contribution to beets!')
    entry.print()
