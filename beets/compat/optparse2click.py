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

"""This is a shim to provide backwards compatibility with optparse in
Click-based applications. It translates from `OptionParser` objects to
Click's `Command` objects.
"""
from __future__ import division, absolute_import, print_function


import click
import optparse


def option_to_click(option):
    """Convert a `optparse.Option` to a `click.Option`.

    If the option should be dropped (i.e., it's a help option), return
    None.
    """
    # Get the flags and, if specified, the destination name.
    decls = []
    decls = option._long_opts + option._short_opts
    if option.dest:
        decls.append(option.dest)

    is_flag = False
    multiple = False
    callback = None
    flag_value = None
    nargs = option.nargs
    default = option.default

    # Handle the no-default sentinel.
    if default == optparse.NO_DEFAULT:
        default = None

    # The various behaviors available in optparse.
    if option.action == 'store_true':
        is_flag = True
        flag_value = True
        default = False

    elif option.action == 'store_false':
        is_flag = True
        flag_value = False
        default = True

    elif option.action == 'append':
        multiple = True

    elif option.action == 'callback':
        def option_callback_shim(ctx, param, value):
            args = option.callback_args or ()
            kwargs = option.callback_kwargs or {}
            option.callback(
                option,  # The Option object itself.
                decls[0],  # Option string.
                value,
                None,  # The OptionParser (not supported).
                *args,
                **kwargs
            )
            return value
        callback = option_callback_shim

        # Click doesn't like callbacks with nargs <= 1.
        if nargs == 0:
            is_flag = True
            default = False
        nargs = None

    elif option.action == 'help':
        return None

    op = click.Option(
        decls,

        help=option.help,
        metavar=option.metavar,
        nargs=nargs,
        default=default,

        is_flag=is_flag,
        flag_value=flag_value,
        multiple=multiple,
        callback=callback,
    )
    return op


def parser_to_click(parser, cls=click.Command, **kwargs):
    """Convert an `optparse.OptionParser` to a `click.Command`.

    `parser` is the `OptionParser`. `cls` is the `Command` subclass to
    instantiate. All other keyword arguments are passed through to the
    `Command` constructor.

    You probably want to assign the command's `callback` member after
    constructing it here.
    """
    # Convert each of the optparse options.
    params = []
    for option in parser.option_list:
        param = option_to_click(option)
        if param:
            params.append(param)

    # Add a click argument to gobble up all of the positional arguments.
    # (In optparse, these are not declared: it's entirely up to the
    # application to handle the list of strings that are passed.)
    params.append(click.Argument(['args'], nargs=-1))

    # Construct the Click command object.
    return cls(params=params, **kwargs)


def opts_and_args(kwargs):
    """Given the keyword arguments passed to a Click callback, produce
    equivalent `opts` and `args` values that resemble the return value
    from optparse.
    """
    # Get the positional arguments.
    args = kwargs.pop('args')

    # Turn the rest of the arguments into a namespace object.
    opts = optparse.Values()
    for key, value in kwargs.items():
        setattr(opts, key, value)

    return opts, args
