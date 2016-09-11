# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

"""Click-based tools for command-line option and argument parsing.
"""
from __future__ import division, absolute_import, print_function


import click
import itertools
import optparse
import six

from beets import config
from beets import library
from beets.compat import optparse2click


# Click extensions for `Command` and `Group` to support aliases.

class Command(click.Command):
    """A `click.Command` with aliases (i.e., alternate spellings for the
    command's name.

    For the aliases to actually work, this has to be used with a
    `click.MultiCommand` instance that knows to look for them: for
    example, `AliasGroup`, below.
    """
    def __init__(self, *args, **kwargs):
        aliases = kwargs.pop('aliases', ())
        self.aliases = aliases

        click.Command.__init__(self, *args, **kwargs)

    # Add the aliases to the end of the help output for the command.
    def format_epilog(self, ctx, formatter):
        if self.aliases:
            names = itertools.chain((self.name,), self.aliases)
            formatter.write_paragraph()
            formatter.write_text(u'Aliases: {}'.format(u', '.join(names)))
        super(Command, self).format_epilog(ctx, formatter)


class AliasGroup(click.Group):
    """A `MultiCommand` variant whose subcommands can have aliases.
    """
    @property
    def commands_by_alias(self):
        """A dictionary mapping names to commands, including by their
        aliases (if any).
        """
        out = {}
        for command in self.commands.values():
            out[command.name] = command
            if hasattr(command, 'aliases'):
                for alias in command.aliases:
                    out[alias] = command
        return out

    def get_command(self, ctx, name):
        """Look up commands by name or alias.
        """
        return self.commands_by_alias.get(name)


# Legacy compatibility for optparse-based code.

class LegacyOptionsParser(optparse.OptionParser, object):
    """For backwards compatibility with optparse code, provides helpers
    for adding common command-line options.

    This shim just wraps up a set of flags indicating the requested
    options so they can be added via Click later on.
    """
    def __init__(self, *args, **kwargs):
        super(LegacyOptionsParser, self).__init__(*args, **kwargs)
        self._album_option = False
        self._path_option = False
        self._format_option = False
        self._format_target = None

    def add_album_option(self):
        self._album_option = True

    def add_path_option(self):
        self._path_option = True

    def add_format_option(self, target=None):
        self._format_option = True
        self._format_target = target

    def add_all_common_options(self):
        """Add album, path and format options.
        """
        self.add_album_option()
        self.add_path_option()
        self.add_format_option()


class LegacySubcommand(object):
    """A backwards-compatibility shim for code that still uses the
    `optparse` API. We translate these into Click commands.
    """
    def __init__(self, name, parser=None, help='', aliases=()):
        self.name = name
        self.parser = parser or LegacyOptionsParser()
        self.aliases = aliases
        self.help = help

    def _to_click(self):
        """Create a `click.Command` from the `OptionParser`.
        """
        # Convert from the OptionParser instance to a Command.
        command = optparse2click.parser_to_click(
            self.parser,
            cls=Command,
            name=self.name,
            help=self.help,
            aliases=self.aliases,
        )

        # The callback for the command. Legacy callbacks take three
        # parameters: the library, options (an optparse namespace), and
        # args (a string list).
        def callback(**kwargs):
            opts, args = optparse2click.opts_and_args(kwargs)
            lib = click.get_current_context().find_object(Context).lib
            self.func(lib, opts, args)
        command.callback = callback

        # Unspool the requested "shortcut" options.
        if self.parser._album_option:
            command = album_option(command)
        if self.parser._path_option:
            command = path_option(command)
        if self.parser._format_option:
            command = format_option(target=self.parser._format_target)(command)

        return command


# The Context class, which holds information passed from the top-level
# beets invocation to subcommands.

class Context(object):
    """A context object that is passed to each command callback.
    """
    def __init__(self, lib=None):
        self.lib = lib


# Special-purpose decorators for common beets command-line options.

def album_option(f):
    """Add a -a/--album option to match albums instead of tracks.

    If used then the format option can auto-detect whether we're setting
    the format for items or albums.
    Sets the album property on the options extracted from the CLI.
    """
    return click.option('-a', '--album', is_eager=True, is_flag=True,
                        help=u'match albums instead of tracks')(f)


def _set_format(target, fmt):
    config[target._format_config_key].set(fmt)


def path_option(f):
    """Add a -p/--path option to display the path instead of the default
    format.

    By default this affects both items and albums. If album_option()
    is used then the target will be autodetected.

    Sets the format property to u'$path' on the options extracted from the
    CLI.
    """
    def callback(ctx, param, value):
        if not value:
            return

        if 'album' in ctx.params:
            if ctx.params['album']:
                _set_format(library.Album, '$path')
            else:
                _set_format(library.Item, '$path')
        else:
            _set_format(library.Item, '$path')
            _set_format(library.Album, '$path')

    return click.option('-p', '--path', callback=callback, is_flag=True,
                        help=u'print paths for matched items or albums')(f)


def format_option(flags=('-f', '--format'), target=None):
    """Add an -f/--format option that sets the output format for albums
    or items.

    Whether this affects albums or items is controlled by the separate
    album options (created the `album_option` decorator). It sets either
    `format_album` or `format_item` in the global configuration.
    """
    def callback(ctx, param, value):
        if not value:
            return

        value = six.text_type(value)

        _target = target
        if _target:
            if _target in ('item', 'album'):
                _target = {'item': library.Item,
                           'album': library.Album}[_target]
            _set_format(_target, value)
        else:
            if 'album' in ctx.params:
                if ctx.params['album']:
                    _set_format(library.Album, value)
                else:
                    _set_format(library.Item, value)
            else:
                _set_format(library.Item, value)
                _set_format(library.Album, value)

    def decorator(f):
        return click.option(*flags, callback=callback, expose_value=False,
                            help=u'print with custom format')(f)

    return decorator


def all_common_options(f):
    """Add the `--album`, `--path`, and `--format` command-line options.
    """
    return album_option(path_option(format_option()(f)))


pass_context = click.make_pass_decorator(Context, ensure=True)
