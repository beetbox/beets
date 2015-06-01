# This file is part of beets.
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

"""Adds support for ipfs. Requires go-ipfs and a running ipfs daemon
"""
from beets import ui, util, library, config
from beets.plugins import BeetsPlugin

import subprocess
import shutil
import os
import tempfile


class IPFSPlugin(BeetsPlugin):

    def __init__(self):
        super(IPFSPlugin, self).__init__()

    def commands(self):
        cmd = ui.Subcommand('ipfs',
                            help='interact with ipfs')
        cmd.parser.add_option('-a', '--add', dest='add',
                                    action='store_true',
                                    help='Add to ipfs')
        cmd.parser.add_option('-g', '--get', dest='get',
                                    action='store_true',
                                    help='Get from ipfs')
        cmd.parser.add_option('-p', '--publish', dest='publish',
                                    action='store_true',
                                    help='Publish local library to ipfs')
        cmd.parser.add_option('-i', '--import', dest='_import',
                                    action='store_true',
                                    help='Import remote library from ipfs')
        cmd.parser.add_option('-l', '--list', dest='_list',
                                    action='store_true',
                                    help='Query imported libraries')

        def func(lib, opts, args):
            if opts.add:
                for album in lib.albums(ui.decargs(args)):
                    self.ipfs_add(album)
                    album.store()

            if opts.get:
                self.ipfs_get(lib, ui.decargs(args))

            if opts.publish:
                self.ipfs_publish(lib)

            if opts._import:
                self.ipfs_import(lib, ui.decargs(args))

            if opts._list:
                self.ipfs_list(lib, ui.decargs(args))

        cmd.func = func
        return [cmd]

    def ipfs_add(self, lib):
        try:
            album_dir = lib.item_dir()
        except AttributeError:
            return
        self._log.info('Adding {0} to ipfs', album_dir)

        cmd = "ipfs add -q -r".split()
        cmd.append(album_dir)
        try:
            output = util.command_output(cmd)
        except (OSError, subprocess.CalledProcessError) as exc:
            self._log.error(u'Failed to add {0}, error: {1}', album_dir, exc)
            return False
        length = len(output)

        for linenr, line in enumerate(output.split()):
            line = line.strip()
            if linenr == length - 1:
                # last printed line is the album hash
                self._log.info("album: {0}", line)
                lib.ipfs = line
            else:
                try:
                    item = lib.items()[linenr]
                    self._log.info("item: {0}", line)
                    item.ipfs = line
                    item.store()
                except IndexError:
                    # if there's non music files in the to-add folder they'll
                    # get ignored here
                    pass

        return True

    def ipfs_get(self, lib, query):
        query = query[0]
        # Check if query is a hash
        if query.startswith("Qm") and len(query) == 46:
            self.ipfs_get_from_hash(lib, query)
        else:
            albums = self.query(lib, query)
            for album in albums:
                self.ipfs_get_from_hash(lib, album.ipfs)

    def ipfs_get_from_hash(self, lib, _hash):
        try:
            cmd = "ipfs get".split()
            cmd.append(_hash)
            util.command_output(cmd)
        except (OSError, subprocess.CalledProcessError) as err:
            self._log.error('Failed to get {0} from ipfs.\n{1}',

                            _hash, err.output)
            return False

        self._log.info('Getting {0} from ipfs', _hash)
        imp = ui.commands.TerminalImportSession(lib, loghandler=None,
                                                query=None, paths=[_hash])
        imp.run()
        shutil.rmtree(_hash)

    def ipfs_publish(self, lib):
        with tempfile.NamedTemporaryFile() as tmp:
            self.ipfs_added_albums(lib, tmp.name)
            try:
                cmd = "ipfs add -q ".split()
                cmd.append(tmp.name)
                output = util.command_output(cmd)
            except (OSError, subprocess.CalledProcessError) as err:
                msg = "Failed to publish library. Error: {0}".format(err)
                self._log.error(msg)
                return False
            self._log.info("hash of library: {0}", output)

    def ipfs_import(self, lib, args):
        _hash = args[0]
        if len(args) > 1:
            lib_name = args[1]
        else:
            lib_name = _hash
        lib_root = os.path.dirname(lib.path)
        remote_libs = lib_root + "/remotes"
        if not os.path.exists(remote_libs):
            os.makedirs(remote_libs)
        path = remote_libs + "/" + lib_name + ".db"
        cmd = "ipfs get {0} -o".format(_hash).split()
        cmd.append(path)
        try:
            util.command_output(cmd)
        except (OSError, subprocess.CalledProcessError):
            self._log.error("Could not import {0}".format(_hash))
            return False

        # add all albums from remotes into a combined library
        jpath = remote_libs + "/joined.db"
        jlib = library.Library(jpath)
        nlib = library.Library(path)
        for album in nlib.albums():
            if not self.already_added(album, jlib):
                for item in album.items():
                    jlib.add(item)
                jlib.add(album)

    def already_added(self, check, jlib):
        for jalbum in jlib.albums():
            if jalbum.mb_albumid == check.mb_albumid:
                return True
        return False

    def ipfs_list(self, lib, args):
        fmt = config['format_album'].get()
        try:
            albums = self.query(lib, args)
        except IOError:
            ui.print_("No imported libraries yet.")
            return

        for album in albums:
            ui.print_(format(album, fmt), " : ", album.ipfs)

    def query(self, lib, args):
        lib_root = os.path.dirname(lib.path)
        remote_libs = lib_root + "/remotes"
        path = remote_libs + "/joined.db"
        if not os.path.isfile(path):
            raise IOError
        rlib = library.Library(path)
        albums = rlib.albums(args)
        return albums

    def ipfs_added_albums(self, rlib, tmpname):
        """ Returns a new library with only albums/items added to ipfs
        """
        tmplib = library.Library(tmpname)
        for album in rlib.albums():
            try:
                if album.ipfs:
                    for item in album.items():
                        # Clear current path from item
                        item.path = ''
                        tmplib.add(item)
                    album.artpath = ''
                    self._log.info("Adding '{0}' to temporary library", album)
                    tmplib.add(album)
            except AttributeError:
                pass
        return tmplib
