# This file is part of beets.
# Copyright 2015, Franois-Xavier Thomas.
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
autocomplete for you.
It does the main commands and options for beet and the plugins.
It gives you all the album and itemfields (like genre, album) but
not all the values for these. It suggest genre: or album:
but not genre: Pop..Jazz...Rock
You can get that by specifying ex. --extrafields genre.
"""

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from beets.plugins import BeetsPlugin
from beets import library, ui
from beets.ui import commands
from operator import attrgetter
import os


class fishPlugin(BeetsPlugin):
    def commands(self):
        cmd = ui.Subcommand('fish', help='make fish autocomplete beet')
        cmd.func = self.run
        cmd.parser.add_option('-f', '--noFields', action='store_true',
                              default=False,
                              help='add fields')
        cmd.parser.add_option('-e', '--extraFields',
                              action='append',
                              type='choice',
                              choices=library.Item.all_keys() +
                              library.Album.all_keys(),
                              help='extra fields to autocomplete')
        return [cmd]

    def run(self, lib, opts, args):
        homeDir = os.path.expanduser("~")
        completePath = os.path.join(homeDir, '.config/fish/completions')
        try:
            os.makedirs(completePath)
        except OSError:
            if not os.path.isdir(completePath):
                raise
        pathAndFile = os.path.join(completePath, 'beet.fish')
        with open(pathAndFile, 'w') as fish_file:
            fish_file.write(get_fishfile(opts, lib))


def cleanWhitespace(word):
    # remove to much whitespace in string
    return " ".join(word.split()) if " " in word else word


def wrap(word):
    tok = '"' if "'" in word else "'"
    return tok + word + tok


def getSetOfValuesForField(lib, fields):
    # collect the different values for a field in sets
    dictOfFields = {}
    for each in fields:
        dictOfFields[each] = set()
    for item in lib.items():
        for field in fields:
            dictOfFields[field].add(wrap(item[field]))
    return dictOfFields


def getBasicBeetOptions():
    word = (
        bl_need2.format("-l format-item",
                        "-f -d 'print with custom format'") +
        bl_need2.format("-l format-album",
                        "-f -d 'print with custom format'") +
        bl_need2.format("-s  l  -l library",
                        "-f -r -d 'library database file to use'") +
        bl_need2.format("-s  d  -l directory",
                        "-f -r -d 'destination music directory'") +
        bl_need2.format("-s  v  -l verbose",
                        "-f -d 'print debugging information'") +
        bl_need2.format("-s  c  -l config",
                        "-f -r -d 'path to configuration file'") +
        bl_need2.format("-s  h  -l help",
                        "-f -d 'print this help message and exit'"))
    return word


def getSubarguments(zippy, opts):
    word = ""
    for cmdname, cmdhelp in zippy:
        word += ("\n" * 2) + "# ------ {} -------".format(
            "fieldsetups for  " + cmdname) + "\n"
        word += (
            bl_need2.format(
                ("-a " + cmdname),
                ("-f " + "-d " + wrap(cleanWhitespace(cmdhelp)))))

        if opts.noFields is False:
            word += (
                bl_use3.format(
                    cmdname,
                    ("-a " + wrap("$FIELDS")),
                    ("-f " + "-d " + wrap("fieldname"))))
        if opts.extraFields:
            for f in opts.extraFields:
                setvar = wrap("$" + f.upper() + "S")
                word += " ".join(bl_extra3.format(
                    (cmdname + " " + f + ":"),
                    ('-f ' + '-A ' + '-a ' + setvar),
                    ('-d ' + wrap(f))).split()) + "\n"
    return word


def getAllCommands(cmds):
    word = ""
    for cmd in cmds:
        name = cmd.name
        word += ("\n" * 2) + "# ====== {} =====".format(
            "completions for  " + cmd.name) + "\n"
        if cmd.aliases:
            word += "# === {} =".format(
                "aliases for " + cmd.name) + "\n"
            for alias in cmd.aliases:
                alias = alias if alias != "?" else "\?"
                word += "abbr -a {} {}".format(
                    alias, name) + "\n"

        word += "\n"

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

            word += " ".join(bl_use3.format(
                name,
                (cmd_needARG + cmd_SO + cmd_LO + " -f " + cmd_arglist),
                cmd_helpstr).split()) + "\n"

        word = (word + " ".join(bl_use3.format(
            name,
            ("-s " + "h " + "-l " + "help" + " -f "),
            ('-d ' + wrap("print help") + "\n")
        ).split()))
    return word


def get_fishfile(opts, lib):
    cmds = sorted((commands.default_commands +
                  commands.plugins.commands()),  key=attrgetter('name'))
    cmds_helps = [cmd.help for cmd in cmds]
    fields = sorted(set(library.Album.all_keys() + library.Item.all_keys()))

    totstring = head

    cmds_names = [cmd.name for cmd in cmds]
    totstring += (
        "set CMDS " + " ".join(cmds_names) + ("\n" * 2)
    )
    fields = (field + ":" for field in fields)
    if opts.noFields is False:
        totstring += (
            "set FIELDS " + " ".join(fields) + ("\n" * 2)
        )
    if opts.extraFields:
        setOfValues = getSetOfValuesForField(lib,  opts.extraFields)
        for fld in opts.extraFields:
            extraname = fld.upper() + 'S'
            totstring += (
                "set  " + extraname + " " + " ".join(sorted(setOfValues[fld]))
                + ("\n" * 2)
            )
    # Collect subcommands
    totstring += ("\n" * 2) + "# ====== {} =====".format(
        "basic beet options") + ("\n" * 2)

    totstring += getBasicBeetOptions()

    totstring += ("\n" * 2) + "# ====== {} =====".format(
        "basic beet subarguments") + ("\n" * 2)

    cmds_zipped = zip(cmds_names, cmds_helps)
    totstring += getSubarguments(cmds_zipped, opts)

    totstring += "\n"
    totstring += getAllCommands(cmds)

    return totstring

bl_need2 = """complete -c beet -n '__fish_beet_needs_command' {} {}\n"""
bl_use3 = """complete -c beet -n '__fish_beet_using_command {}' {} {}\n"""
bl_subs = """complete -c beet -n '__fish_at_level {} ""' {}  {}\n"""
bl_extra3 = """complete -c beet -n '__fish_beet_use_extra {}' {} {}\n"""

head = '''
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
