# This file is part of beets.
# Copyright 2015, Adrian Sampson.
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

"""This module provides the default commands for beets' command-line
interface.
"""

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

import os
import re

import beets
from beets import ui
from beets.ui import print_, decargs, show_path_changes
from beets import plugins
from beets import util
from beets.util import syspath, normpath, ancestry, displayable_path
from beets import library
from beets import config
from beets import logging
from beets.util.confit import _package_path
from beets.ui.terminal_import_session import TerminalImportSession

VARIOUS_ARTISTS = u'Various Artists'

# Global logger.
log = logging.getLogger('beets')

# The list of default subcommands. This is populated with Subcommand
# objects that can be fed to a SubcommandsOptionParser.
default_commands = []


# Utilities.

def _do_query(lib, query, album, also_items=True):
    """For commands that operate on matched items, performs a query
    and returns a list of matching items and a list of matching
    albums. (The latter is only nonempty when album is True.) Raises
    a UserError if no items match. also_items controls whether, when
    fetching albums, the associated items should be fetched also.
    """
    if album:
        albums = list(lib.albums(query))
        items = []
        if also_items:
            for al in albums:
                items += al.items()

    else:
        albums = []
        items = list(lib.items(query))

    if album and not albums:
        raise ui.UserError('No matching albums found.')
    elif not album and not items:
        raise ui.UserError('No matching items found.')

    return items, albums


# fields: Shows a list of available fields for queries and format strings.

def fields_func(lib, opts, args):
    def _print_rows(names):
        names.sort()
        print_("  " + "\n  ".join(names))

    fs, pfs = library.Item.get_fields()
    print_("Item fields:")
    _print_rows(fs)
    print_("Template fields from plugins:")
    _print_rows(pfs)

    fs, pfs = library.Album.get_fields()
    print_("Album fields:")
    _print_rows(fs)
    print_("Template fields from plugins:")
    _print_rows(pfs)


fields_cmd = ui.Subcommand(
    'fields',
    help='show fields available for queries and format strings'
)
fields_cmd.func = fields_func
default_commands.append(fields_cmd)


# help: Print help text for commands

class HelpCommand(ui.Subcommand):

    def __init__(self):
        super(HelpCommand, self).__init__(
            'help', aliases=('?',),
            help='give detailed help on a specific sub-command',
        )

    def func(self, lib, opts, args):
        if args:
            cmdname = args[0]
            helpcommand = self.root_parser._subcommand_for_name(cmdname)
            if not helpcommand:
                raise ui.UserError("unknown command '{0}'".format(cmdname))
            helpcommand.print_help()
        else:
            self.root_parser.print_help()


default_commands.append(HelpCommand())


# import: Autotagger and importer.

def import_files(lib, paths, query):
    """Import the files in the given list of paths or matching the
    query.
    """
    # Check the user-specified directories.
    for path in paths:
        if not os.path.exists(syspath(normpath(path))):
            raise ui.UserError(u'no such file or directory: {0}'.format(
                displayable_path(path)))

    # Check parameter consistency.
    if config['import']['quiet'] and config['import']['timid']:
        raise ui.UserError("can't be both quiet and timid")

    # Open the log.
    if config['import']['log'].get() is not None:
        logpath = syspath(config['import']['log'].as_filename())
        try:
            loghandler = logging.FileHandler(logpath)
        except IOError:
            raise ui.UserError(u"could not open log file for writing: "
                               u"{0}".format(displayable_path(logpath)))
    else:
        loghandler = None

    # Never ask for input in quiet mode.
    if config['import']['resume'].get() == 'ask' and \
            config['import']['quiet']:
        config['import']['resume'] = False

    session = TerminalImportSession(lib, loghandler, paths, query)
    session.run()

    # Emit event.
    plugins.send('import', lib=lib, paths=paths)


def import_func(lib, opts, args):
    config['import'].set_args(opts)

    # Special case: --copy flag suppresses import_move (which would
    # otherwise take precedence).
    if opts.copy:
        config['import']['move'] = False

    if opts.library:
        query = decargs(args)
        paths = []
    else:
        query = None
        paths = args
        if not paths:
            raise ui.UserError('no path specified')

    import_files(lib, paths, query)


import_cmd = ui.Subcommand(
    'import', help='import new music', aliases=('imp', 'im')
)
import_cmd.parser.add_option(
    '-c', '--copy', action='store_true', default=None,
    help="copy tracks into library directory (default)"
)
import_cmd.parser.add_option(
    '-C', '--nocopy', action='store_false', dest='copy',
    help="don't copy tracks (opposite of -c)"
)
import_cmd.parser.add_option(
    '-w', '--write', action='store_true', default=None,
    help="write new metadata to files' tags (default)"
)
import_cmd.parser.add_option(
    '-W', '--nowrite', action='store_false', dest='write',
    help="don't write metadata (opposite of -w)"
)
import_cmd.parser.add_option(
    '-a', '--autotag', action='store_true', dest='autotag',
    help="infer tags for imported files (default)"
)
import_cmd.parser.add_option(
    '-A', '--noautotag', action='store_false', dest='autotag',
    help="don't infer tags for imported files (opposite of -a)"
)
import_cmd.parser.add_option(
    '-p', '--resume', action='store_true', default=None,
    help="resume importing if interrupted"
)
import_cmd.parser.add_option(
    '-P', '--noresume', action='store_false', dest='resume',
    help="do not try to resume importing"
)
import_cmd.parser.add_option(
    '-q', '--quiet', action='store_true', dest='quiet',
    help="never prompt for input: skip albums instead"
)
import_cmd.parser.add_option(
    '-l', '--log', dest='log',
    help='file to log untaggable albums for later review'
)
import_cmd.parser.add_option(
    '-s', '--singletons', action='store_true',
    help='import individual tracks instead of full albums'
)
import_cmd.parser.add_option(
    '-t', '--timid', dest='timid', action='store_true',
    help='always confirm all actions'
)
import_cmd.parser.add_option(
    '-L', '--library', dest='library', action='store_true',
    help='retag items matching a query'
)
import_cmd.parser.add_option(
    '-i', '--incremental', dest='incremental', action='store_true',
    help='skip already-imported directories'
)
import_cmd.parser.add_option(
    '-I', '--noincremental', dest='incremental', action='store_false',
    help='do not skip already-imported directories'
)
import_cmd.parser.add_option(
    '--flat', dest='flat', action='store_true',
    help='import an entire tree as a single album'
)
import_cmd.parser.add_option(
    '-g', '--group-albums', dest='group_albums', action='store_true',
    help='group tracks in a folder into separate albums'
)
import_cmd.parser.add_option(
    '--pretend', dest='pretend', action='store_true',
    help='just print the files to import'
)
import_cmd.func = import_func
default_commands.append(import_cmd)


# list: Query and show library contents.

def list_items(lib, query, album, fmt=''):
    """Print out items in lib matching query. If album, then search for
    albums instead of single items.
    """
    if album:
        for album in lib.albums(query):
            ui.print_(format(album, fmt))
    else:
        for item in lib.items(query):
            ui.print_(format(item, fmt))


def list_func(lib, opts, args):
    list_items(lib, decargs(args), opts.album)


list_cmd = ui.Subcommand('list', help='query the library', aliases=('ls',))
list_cmd.parser.add_all_common_options()
list_cmd.func = list_func
default_commands.append(list_cmd)


# update: Update library contents according to on-disk tags.

def update_items(lib, query, album, move, pretend):
    """For all the items matched by the query, update the library to
    reflect the item's embedded tags.
    """
    with lib.transaction():
        items, _ = _do_query(lib, query, album)

        # Walk through the items and pick up their changes.
        affected_albums = set()
        for item in items:
            # Item deleted?
            if not os.path.exists(syspath(item.path)):
                ui.print_(format(item))
                ui.print_(ui.colorize('text_error', u'  deleted'))
                if not pretend:
                    item.remove(True)
                affected_albums.add(item.album_id)
                continue

            # Did the item change since last checked?
            if item.current_mtime() <= item.mtime:
                log.debug(u'skipping {0} because mtime is up to date ({1})',
                          displayable_path(item.path), item.mtime)
                continue

            # Read new data.
            try:
                item.read()
            except library.ReadError as exc:
                log.error(u'error reading {0}: {1}',
                          displayable_path(item.path), exc)
                continue

            # Special-case album artist when it matches track artist. (Hacky
            # but necessary for preserving album-level metadata for non-
            # autotagged imports.)
            if not item.albumartist:
                old_item = lib.get_item(item.id)
                if old_item.albumartist == old_item.artist == item.artist:
                    item.albumartist = old_item.albumartist
                    item._dirty.discard('albumartist')

            # Check for and display changes.
            changed = ui.show_model_changes(item,
                                            fields=library.Item._media_fields)

            # Save changes.
            if not pretend:
                if changed:
                    # Move the item if it's in the library.
                    if move and lib.directory in ancestry(item.path):
                        item.move()

                    item.store()
                    affected_albums.add(item.album_id)
                else:
                    # The file's mtime was different, but there were no
                    # changes to the metadata. Store the new mtime,
                    # which is set in the call to read(), so we don't
                    # check this again in the future.
                    item.store()

        # Skip album changes while pretending.
        if pretend:
            return

        # Modify affected albums to reflect changes in their items.
        for album_id in affected_albums:
            if album_id is None:  # Singletons.
                continue
            album = lib.get_album(album_id)
            if not album:  # Empty albums have already been removed.
                log.debug(u'emptied album {0}', album_id)
                continue
            first_item = album.items().get()

            # Update album structure to reflect an item in it.
            for key in library.Album.item_keys:
                album[key] = first_item[key]
            album.store()

            # Move album art (and any inconsistent items).
            if move and lib.directory in ancestry(first_item.path):
                log.debug(u'moving album {0}', album_id)
                album.move()


def update_func(lib, opts, args):
    update_items(lib, decargs(args), opts.album, opts.move, opts.pretend)


update_cmd = ui.Subcommand(
    'update', help='update the library', aliases=('upd', 'up',)
)
update_cmd.parser.add_album_option()
update_cmd.parser.add_format_option()
update_cmd.parser.add_option(
    '-M', '--nomove', action='store_false', default=True, dest='move',
    help="don't move files in library"
)
update_cmd.parser.add_option(
    '-p', '--pretend', action='store_true',
    help="show all changes but do nothing"
)
update_cmd.func = update_func
default_commands.append(update_cmd)


# remove: Remove items from library, delete files.

def remove_items(lib, query, album, delete):
    """Remove items matching query from lib. If album, then match and
    remove whole albums. If delete, also remove files from disk.
    """
    # Get the matching items.
    items, albums = _do_query(lib, query, album)

    # Prepare confirmation with user.
    print_()
    if delete:
        fmt = u'$path - $title'
        prompt = 'Really DELETE %i file%s (y/n)?' % \
                 (len(items), 's' if len(items) > 1 else '')
    else:
        fmt = ''
        prompt = 'Really remove %i item%s from the library (y/n)?' % \
                 (len(items), 's' if len(items) > 1 else '')

    # Show all the items.
    for item in items:
        ui.print_(format(item, fmt))

    # Confirm with user.
    if not ui.input_yn(prompt, True):
        return

    # Remove (and possibly delete) items.
    with lib.transaction():
        for obj in (albums if album else items):
            obj.remove(delete)


def remove_func(lib, opts, args):
    remove_items(lib, decargs(args), opts.album, opts.delete)


remove_cmd = ui.Subcommand(
    'remove', help='remove matching items from the library', aliases=('rm',)
)
remove_cmd.parser.add_option(
    "-d", "--delete", action="store_true",
    help="also remove files from disk"
)
remove_cmd.parser.add_album_option()
remove_cmd.func = remove_func
default_commands.append(remove_cmd)


# stats: Show library/query statistics.

def show_stats(lib, query, exact):
    """Shows some statistics about the matched items."""
    items = lib.items(query)

    total_size = 0
    total_time = 0.0
    total_items = 0
    artists = set()
    albums = set()
    album_artists = set()

    for item in items:
        if exact:
            total_size += os.path.getsize(item.path)
        else:
            total_size += int(item.length * item.bitrate / 8)
        total_time += item.length
        total_items += 1
        artists.add(item.artist)
        album_artists.add(item.albumartist)
        if item.album_id:
            albums.add(item.album_id)

    size_str = '' + ui.human_bytes(total_size)
    if exact:
        size_str += ' ({0} bytes)'.format(total_size)

    print_("""Tracks: {0}
Total time: {1}{2}
{3}: {4}
Artists: {5}
Albums: {6}
Album artists: {7}""".format(
        total_items,
        ui.human_seconds(total_time),
        ' ({0:.2f} seconds)'.format(total_time) if exact else '',
        'Total size' if exact else 'Approximate total size',
        size_str,
        len(artists),
        len(albums),
        len(album_artists)),
    )


def stats_func(lib, opts, args):
    show_stats(lib, decargs(args), opts.exact)


stats_cmd = ui.Subcommand(
    'stats', help='show statistics about the library or a query'
)
stats_cmd.parser.add_option(
    '-e', '--exact', action='store_true',
    help='exact size and time'
)
stats_cmd.func = stats_func
default_commands.append(stats_cmd)


# version: Show current beets version.

def show_version(lib, opts, args):
    print_('beets version %s' % beets.__version__)
    # Show plugins.
    names = sorted(p.name for p in plugins.find_plugins())
    if names:
        print_('plugins:', ', '.join(names))
    else:
        print_('no plugins loaded')


version_cmd = ui.Subcommand(
    'version', help='output version information'
)
version_cmd.func = show_version
default_commands.append(version_cmd)


# modify: Declaratively change metadata.

def modify_items(lib, mods, dels, query, write, move, album, confirm):
    """Modifies matching items according to user-specified assignments and
    deletions.

    `mods` is a dictionary of field and value pairse indicating
    assignments. `dels` is a list of fields to be deleted.
    """
    # Parse key=value specifications into a dictionary.
    model_cls = library.Album if album else library.Item

    for key, value in mods.items():
        mods[key] = model_cls._parse(key, value)

    # Get the items to modify.
    items, albums = _do_query(lib, query, album, False)
    objs = albums if album else items

    # Apply changes *temporarily*, preview them, and collect modified
    # objects.
    print_('Modifying {0} {1}s.'
           .format(len(objs), 'album' if album else 'item'))
    changed = set()
    for obj in objs:
        obj.update(mods)
        for field in dels:
            try:
                del obj[field]
            except KeyError:
                pass
        if ui.show_model_changes(obj):
            changed.add(obj)

    # Still something to do?
    if not changed:
        print_('No changes to make.')
        return

    # Confirm action.
    if confirm:
        if write and move:
            extra = ', move and write tags'
        elif write:
            extra = ' and write tags'
        elif move:
            extra = ' and move'
        else:
            extra = ''

        if not ui.input_yn('Really modify%s (Y/n)?' % extra):
            return

    # Apply changes to database and files
    with lib.transaction():
        for obj in changed:
            if move:
                cur_path = obj.path
                if lib.directory in ancestry(cur_path):  # In library?
                    log.debug(u'moving object {0}', displayable_path(cur_path))
                    obj.move()

            obj.try_sync(write)


def modify_parse_args(args):
    """Split the arguments for the modify subcommand into query parts,
    assignments (field=value), and deletions (field!).  Returns the result as
    a three-tuple in that order.
    """
    mods = {}
    dels = []
    query = []
    for arg in args:
        if arg.endswith('!') and '=' not in arg and ':' not in arg:
            dels.append(arg[:-1])  # Strip trailing !.
        elif '=' in arg and ':' not in arg.split('=', 1)[0]:
            key, val = arg.split('=', 1)
            mods[key] = val
        else:
            query.append(arg)
    return query, mods, dels


def modify_func(lib, opts, args):
    query, mods, dels = modify_parse_args(decargs(args))
    if not mods and not dels:
        raise ui.UserError('no modifications specified')
    write = opts.write if opts.write is not None else \
        config['import']['write'].get(bool)
    modify_items(lib, mods, dels, query, write, opts.move, opts.album,
                 not opts.yes)


modify_cmd = ui.Subcommand(
    'modify', help='change metadata fields', aliases=('mod',)
)
modify_cmd.parser.add_option(
    '-M', '--nomove', action='store_false', default=True, dest='move',
    help="don't move files in library"
)
modify_cmd.parser.add_option(
    '-w', '--write', action='store_true', default=None,
    help="write new metadata to files' tags (default)"
)
modify_cmd.parser.add_option(
    '-W', '--nowrite', action='store_false', dest='write',
    help="don't write metadata (opposite of -w)"
)
modify_cmd.parser.add_album_option()
modify_cmd.parser.add_format_option(target='item')
modify_cmd.parser.add_option(
    '-y', '--yes', action='store_true',
    help='skip confirmation'
)
modify_cmd.func = modify_func
default_commands.append(modify_cmd)


# move: Move/copy files to the library or a new base directory.

def move_items(lib, dest, query, copy, album, pretend):
    """Moves or copies items to a new base directory, given by dest. If
    dest is None, then the library's base directory is used, making the
    command "consolidate" files.
    """
    items, albums = _do_query(lib, query, album, False)
    objs = albums if album else items

    action = 'Copying' if copy else 'Moving'
    entity = 'album' if album else 'item'
    log.info(u'{0} {1} {2}{3}.', action, len(objs), entity,
             's' if len(objs) > 1 else '')
    if pretend:
        if album:
            show_path_changes([(item.path, item.destination(basedir=dest))
                               for obj in objs for item in obj.items()])
        else:
            show_path_changes([(obj.path, obj.destination(basedir=dest))
                               for obj in objs])
    else:
        for obj in objs:
            log.debug(u'moving: {0}', util.displayable_path(obj.path))

            obj.move(copy, basedir=dest)
            obj.store()


def move_func(lib, opts, args):
    dest = opts.dest
    if dest is not None:
        dest = normpath(dest)
        if not os.path.isdir(dest):
            raise ui.UserError('no such directory: %s' % dest)

    move_items(lib, dest, decargs(args), opts.copy, opts.album, opts.pretend)


move_cmd = ui.Subcommand(
    'move', help='move or copy items', aliases=('mv',)
)
move_cmd.parser.add_option(
    '-d', '--dest', metavar='DIR', dest='dest',
    help='destination directory'
)
move_cmd.parser.add_option(
    '-c', '--copy', default=False, action='store_true',
    help='copy instead of moving'
)
move_cmd.parser.add_option(
    '-p', '--pretend', default=False, action='store_true',
    help='show how files would be moved, but don\'t touch anything')
move_cmd.parser.add_album_option()
move_cmd.func = move_func
default_commands.append(move_cmd)


# write: Write tags into files.

def write_items(lib, query, pretend, force):
    """Write tag information from the database to the respective files
    in the filesystem.
    """
    items, albums = _do_query(lib, query, False, False)

    for item in items:
        # Item deleted?
        if not os.path.exists(syspath(item.path)):
            log.info(u'missing file: {0}', util.displayable_path(item.path))
            continue

        # Get an Item object reflecting the "clean" (on-disk) state.
        try:
            clean_item = library.Item.from_path(item.path)
        except library.ReadError as exc:
            log.error(u'error reading {0}: {1}',
                      displayable_path(item.path), exc)
            continue

        # Check for and display changes.
        changed = ui.show_model_changes(item, clean_item,
                                        library.Item._media_tag_fields, force)
        if (changed or force) and not pretend:
            item.try_sync()


def write_func(lib, opts, args):
    write_items(lib, decargs(args), opts.pretend, opts.force)


write_cmd = ui.Subcommand('write', help='write tag information to files')
write_cmd.parser.add_option(
    '-p', '--pretend', action='store_true',
    help="show all changes but do nothing"
)
write_cmd.parser.add_option(
    '-f', '--force', action='store_true',
    help="write tags even if the existing tags match the database"
)
write_cmd.func = write_func
default_commands.append(write_cmd)


# config: Show and edit user configuration.

def config_func(lib, opts, args):
    # Make sure lazy configuration is loaded
    config.resolve()

    # Print paths.
    if opts.paths:
        filenames = []
        for source in config.sources:
            if not opts.defaults and source.default:
                continue
            if source.filename:
                filenames.append(source.filename)

        # In case the user config file does not exist, prepend it to the
        # list.
        user_path = config.user_config_path()
        if user_path not in filenames:
            filenames.insert(0, user_path)

        for filename in filenames:
            print_(filename)

    # Open in editor.
    elif opts.edit:
        config_edit()

    # Dump configuration.
    else:
        print_(config.dump(full=opts.defaults, redact=opts.redact))


def config_edit():
    """Open a program to edit the user configuration.
    An empty config file is created if no existing config file exists.
    """
    path = config.user_config_path()
    editor = os.environ.get('EDITOR')
    try:
        if not os.path.isfile(path):
            open(path, 'w+').close()
        util.interactive_open(path, editor)
    except OSError as exc:
        message = "Could not edit configuration: {0}".format(exc)
        if not editor:
            message += ". Please set the EDITOR environment variable"
        raise ui.UserError(message)

config_cmd = ui.Subcommand('config',
                           help='show or edit the user configuration')
config_cmd.parser.add_option(
    '-p', '--paths', action='store_true',
    help='show files that configuration was loaded from'
)
config_cmd.parser.add_option(
    '-e', '--edit', action='store_true',
    help='edit user configuration with $EDITOR'
)
config_cmd.parser.add_option(
    '-d', '--defaults', action='store_true',
    help='include the default configuration'
)
config_cmd.parser.add_option(
    '-c', '--clear', action='store_false',
    dest='redact', default=True,
    help='do not redact sensitive fields'
)
config_cmd.func = config_func
default_commands.append(config_cmd)


# completion: print completion script

def print_completion(*args):
    for line in completion_script(default_commands + plugins.commands()):
        print_(line, end='')
    if not any(map(os.path.isfile, BASH_COMPLETION_PATHS)):
        log.warn(u'Warning: Unable to find the bash-completion package. '
                 u'Command line completion might not work.')

BASH_COMPLETION_PATHS = map(syspath, [
    u'/etc/bash_completion',
    u'/usr/share/bash-completion/bash_completion',
    u'/usr/share/local/bash-completion/bash_completion',
    u'/opt/local/share/bash-completion/bash_completion',  # SmartOS
    u'/usr/local/etc/bash_completion',  # Homebrew
])


def completion_script(commands):
    """Yield the full completion shell script as strings.

    ``commands`` is alist of ``ui.Subcommand`` instances to generate
    completion data for.
    """
    base_script = os.path.join(_package_path('beets.ui'), 'completion_base.sh')
    with open(base_script, 'r') as base_script:
        yield base_script.read()

    options = {}
    aliases = {}
    command_names = []

    # Collect subcommands
    for cmd in commands:
        name = cmd.name
        command_names.append(name)

        for alias in cmd.aliases:
            if re.match(r'^\w+$', alias):
                aliases[alias] = name

        options[name] = {'flags': [], 'opts': []}
        for opts in cmd.parser._get_all_options()[1:]:
            if opts.action in ('store_true', 'store_false'):
                option_type = 'flags'
            else:
                option_type = 'opts'

            options[name][option_type].extend(
                opts._short_opts + opts._long_opts
            )

    # Add global options
    options['_global'] = {
        'flags': ['-v', '--verbose'],
        'opts': '-l --library -c --config -d --directory -h --help'.split(' ')
    }

    # Add flags common to all commands
    options['_common'] = {
        'flags': ['-h', '--help']
    }

    # Start generating the script
    yield "_beet() {\n"

    # Command names
    yield "  local commands='%s'\n" % ' '.join(command_names)
    yield "\n"

    # Command aliases
    yield "  local aliases='%s'\n" % ' '.join(aliases.keys())
    for alias, cmd in aliases.items():
        yield "  local alias__%s=%s\n" % (alias, cmd)
    yield '\n'

    # Fields
    yield "  fields='%s'\n" % ' '.join(
        set(library.Item._fields.keys() + library.Album._fields.keys())
    )

    # Command options
    for cmd, opts in options.items():
        for option_type, option_list in opts.items():
            if option_list:
                option_list = ' '.join(option_list)
                yield "  local %s__%s='%s'\n" % (option_type, cmd, option_list)

    yield '  _beet_dispatch\n'
    yield '}\n'


completion_cmd = ui.Subcommand(
    'completion',
    help='print shell script that provides command line completion'
)
completion_cmd.func = print_completion
completion_cmd.hide = True
default_commands.append(completion_cmd)
