# This file is part of beets.
# Copyright 2015, winters jean-marie.
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

"""If you use the fish-shell http://fishshell.com/ ... this will do
autocomplete for you. It does the main commands and options for beet
and the plugins.
It gives you all the album and itemfields (like genre, album) but not all the
values for these. It suggest genre: or album: but not genre: Pop..Jazz...Rock
You can get that by specifying ex. --extravalues genre.
"""

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from beets.plugins import BeetsPlugin
from beets import library, ui
from beets.ui import commands
from operator import attrgetter
import os
BL_NEED2 = """complete -c beet -n '__fish_beet_needs_command' {} {}\n"""
BL_USE3 = """complete -c beet -n '__fish_beet_using_command {}' {} {}\n"""
BL_SUBS = """complete -c beet -n '__fish_at_level {} ""' {}  {}\n"""
BL_EXTRA3 = """complete -c beet -n '__fish_beet_use_extra {}' {} {}\n"""

HEAD = '''
function __fish_beet_needs_command
    set cmd (commandline -opc)
    if test (count $cmd) -eq 1
        return 0
    end
    return 1
end

function __fish_beet_using_command
    set cmd (commandline -opc)
    set needle (count $cmd)
    if test $needle -gt 1
        if begin test $argv[1] = $cmd[2];
            and not contains -- $cmd[$needle] $FIELDS; end
                return 0
        end
    end
    return 1
end

function __fish_beet_use_extra
    set cmd (commandline -opc)
    set needle (count $cmd)
    if test $argv[2]  = $cmd[$needle]
        return 0
    end
    return 1
end
'''


class FishPlugin(BeetsPlugin):

    def commands(self):
        cmd = ui.Subcommand('fish', help='make fish autocomplete beet')
        cmd.func = self.run
        cmd.parser.add_option('-f', '--noFields', action='store_true',
                              default=False,
                              help='no item/album fields for autocomplete')
        cmd.parser.add_option(
            '-e',
            '--extravalues',
            action='append',
            type='choice',
            choices=library.Item.all_keys() +
            library.Album.all_keys(),
            help='pick field, get field-values for autocomplete')
        return [cmd]

    def run(self, lib, opts, args):
        # we gather the commands from beet and from the plugins.
        # we take the album and item fields.
        # it wanted, we take the values from these fields.
        # we make a giant string of tehm formatted in a way that
        # allows fish to do autocompletion for beet.
        homeDir = os.path.expanduser("~")
        completePath = os.path.join(homeDir, '.config/fish/completions')
        try:
            os.makedirs(completePath)
        except OSError:
            if not os.path.isdir(completePath):
                raise
        pathAndFile = os.path.join(completePath, 'beet.fish')
        nobasicfields = opts.noFields  # do not complete for item/album fields
        extravalues = opts.extravalues  # ex complete all artist values
        beetcmds = sorted(
            (commands.default_commands +
             commands.plugins.commands()),
            key=attrgetter('name'))
        fields = sorted(set(
            library.Album.all_keys() + library.Item.all_keys()))
        # collect cmds and their aliases and their help message
        cmd_names_help = []
        for cmd in beetcmds:
            names = ["\?" if alias == "?" else alias for alias in cmd.aliases]
            names.append(cmd.name)
            for name in names:
                cmd_names_help.append((name, cmd.help))
        # here we go assembling the string
        totstring = HEAD + "\n"
        totstring += get_cmds_list([name[0] for name in cmd_names_help])
        totstring += '' if nobasicfields else get_standard_fields(fields)
        totstring += get_extravalues(lib, extravalues) if extravalues else ''
        totstring += "\n" + "# ====== {} =====".format(
            "setup basic beet completion") + "\n" * 2
        totstring += get_basic_beet_options()
        totstring += "\n" + "# ====== {} =====".format(
            "setup field completion for subcommands") + "\n"
        totstring += get_subcommands(
            cmd_names_help, nobasicfields, extravalues)
        # setup completion for all the command-options
        totstring += get_all_commands(beetcmds)

        with open(pathAndFile, 'w') as fish_file:
            fish_file.write(totstring)


def get_cmds_list(cmds_names):
    # make list of all commands in beet&plugins
    substr = ''
    substr += (
        "set CMDS " + " ".join(cmds_names) + ("\n" * 2)
    )
    return substr


def get_standard_fields(fields):
    # make list of item/album fields & append with ':'
    fields = (field + ":" for field in fields)
    substr = ''
    substr += (
        "set FIELDS " + " ".join(fields) + ("\n" * 2)
    )
    return substr


def get_extravalues(lib, extravalues):
    # make list of all values from a item/album field
    # so type artist: and get completion for stones, beatles ..
    word = ''
    setOfValues = get_set_of_values_for_field(lib, extravalues)
    for fld in extravalues:
        extraname = fld.upper() + 'S'
        word += (
            "set  " + extraname + " " + " ".join(sorted(setOfValues[fld]))
            + ("\n" * 2)
        )
    return word


def get_set_of_values_for_field(lib, fields):
    # get the unique values from a item/album field
    dictOfFields = {}
    for each in fields:
        dictOfFields[each] = set()
    for item in lib.items():
        for field in fields:
            dictOfFields[field].add(wrap(item[field]))
    return dictOfFields


def get_basic_beet_options():
    word = (
        BL_NEED2.format("-l format-item",
                        "-f -d 'print with custom format'") +
        BL_NEED2.format("-l format-album",
                        "-f -d 'print with custom format'") +
        BL_NEED2.format("-s  l  -l library",
                        "-f -r -d 'library database file to use'") +
        BL_NEED2.format("-s  d  -l directory",
                        "-f -r -d 'destination music directory'") +
        BL_NEED2.format("-s  v  -l verbose",
                        "-f -d 'print debugging information'") +

        BL_NEED2.format("-s  c  -l config",
                        "-f -r -d 'path to configuration file'") +
        BL_NEED2.format("-s  h  -l help",
                        "-f -d 'print this help message and exit'"))
    return word


def get_subcommands(cmd_name_and_help, nobasicfields, extravalues):
    # formatting for fish to complete our fields/values
    word = ""
    for cmdname, cmdhelp in cmd_name_and_help:
        word += "\n" + "# ------ {} -------".format(
            "fieldsetups for  " + cmdname) + "\n"
        word += (
            BL_NEED2.format(
                ("-a " + cmdname),
                ("-f " + "-d " + wrap(clean_whitespace(cmdhelp)))))

        if nobasicfields is False:
            word += (
                BL_USE3.format(
                    cmdname,
                    ("-a " + wrap("$FIELDS")),
                    ("-f " + "-d " + wrap("fieldname"))))

        if extravalues:
            for f in extravalues:
                setvar = wrap("$" + f.upper() + "S")
                word += " ".join(BL_EXTRA3.format(
                    (cmdname + " " + f + ":"),
                    ('-f ' + '-A ' + '-a ' + setvar),
                    ('-d ' + wrap(f))).split()) + "\n"
    return word


def get_all_commands(beetcmds):
    # formatting for fish to complete command-options
    word = ""
    for cmd in beetcmds:
        names = ["\?" if alias == "?" else alias for alias in cmd.aliases]
        names.append(cmd.name)
        for name in names:
            word += "\n"
            word += ("\n" * 2) + "# ====== {} =====".format(
                "completions for  " + name) + "\n"

            for option in cmd.parser._get_all_options()[1:]:
                cmd_LO = (" -l " + option._long_opts[0].replace('--', '')
                          )if option._long_opts else ''
                cmd_SO = (" -s " + option._short_opts[0].replace('-', '')
                          ) if option._short_opts else ''
                cmd_needARG = ' -r ' if option.nargs in [1] else ''
                cmd_helpstr = (" -d " + wrap(' '.join(option.help.split()))
                               ) if option.help else ''
                cmd_arglist = (' -a ' + wrap(" ".join(option.choices))
                               ) if option.choices else ''

                word += " ".join(BL_USE3.format(
                    name,
                    (cmd_needARG + cmd_SO + cmd_LO + " -f " + cmd_arglist),
                    cmd_helpstr).split()) + "\n"

            word = (word + " ".join(BL_USE3.format(
                name,
                ("-s " + "h " + "-l " + "help" + " -f "),
                ('-d ' + wrap("print help") + "\n")
            ).split()))
    return word


def clean_whitespace(word):
    # remove to much whitespace,tabs in string
    return " ".join(word.split())


def wrap(word):
    # need " or ' around strings but watch out if they're in the string
    sptoken = '\"'
    if ('"') in word and ("'") in word:
        word.replace('"', sptoken)
        return '"' + word + '"'

    tok = '"' if "'" in word else "'"
    return tok + word + tok
