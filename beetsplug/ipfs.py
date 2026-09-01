"""Adds support for ipfs. Requires go-ipfs and a running ipfs daemon"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from types import SimpleNamespace
from typing import TYPE_CHECKING, Protocol

from beets import config, library, ui, util
from beets.plugins import BeetsPlugin

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from beets.dbcore import Results
    from beets.importer import ImportSession, ImportTask
    from beets.library import Album, Library


class IPFSCLIOpts(Protocol):
    _import: bool | None
    _list: bool | None
    add: bool | None
    get: bool | None
    play: bool | None
    publish: bool | None


class IPFSPlugin(BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()
        self.config.add({"auto": True, "nocopy": False})

        if self.config["auto"]:
            self.import_stages = [self.auto_add]

    def commands(self) -> list[ui.Subcommand]:
        cmd = ui.Subcommand("ipfs", help="interact with ipfs")
        cmd.parser.add_option(
            "-a", "--add", dest="add", action="store_true", help="Add to ipfs"
        )
        cmd.parser.add_option(
            "-g", "--get", dest="get", action="store_true", help="Get from ipfs"
        )
        cmd.parser.add_option(
            "-p",
            "--publish",
            dest="publish",
            action="store_true",
            help="Publish local library to ipfs",
        )
        cmd.parser.add_option(
            "-i",
            "--import",
            dest="_import",
            action="store_true",
            help="Import remote library from ipfs",
        )
        cmd.parser.add_option(
            "-l",
            "--list",
            dest="_list",
            action="store_true",
            help="Query imported libraries",
        )
        cmd.parser.add_option(
            "-m",
            "--play",
            dest="play",
            action="store_true",
            help="Play music from remote libraries",
        )

        def func(lib: Library, opts: IPFSCLIOpts, args: list[str]) -> None:
            if opts.add:
                for album in lib.albums(args):
                    if len(album.items()) == 0:
                        self._log.info(
                            "{} does not contain items, aborting", album
                        )

                    self.ipfs_add(album)
                    album.store()

            if opts.get:
                self.ipfs_get(lib, args)

            if opts.publish:
                self.ipfs_publish(lib)

            if opts._import:
                self.ipfs_import(lib, args)

            if opts._list:
                self.ipfs_list(lib, args)

            if opts.play:
                self.ipfs_play(lib, opts, args)

        cmd.func = func
        return [cmd]

    def auto_add(self, session: ImportSession, task: ImportTask) -> None:
        if task.is_album:
            if self.ipfs_add(task.album):
                task.album.store()

    def ipfs_play(
        self, lib: Library, opts: IPFSCLIOpts, args: list[str]
    ) -> None:
        from beetsplug.play import PlayPlugin

        player = PlayPlugin()
        config["play"]["relative_to"] = None
        # set opts that `_play_command` expects
        play_opts = SimpleNamespace(
            album=True, randomize=None, args=None, yes=None
        )
        with self.remote_lib(lib) as jlib:
            player._play_command(jlib, play_opts, args)

    def ipfs_add(self, album: Album) -> bool:
        try:
            album_dir = album.item_dir()
        except AttributeError:
            return False
        try:
            if album.ipfs:
                self._log.debug("{} already added", album_dir)
                # Already added to ipfs
                return False
        except AttributeError:
            pass

        self._log.info("Adding {} to ipfs", album_dir)

        if self.config["nocopy"]:
            cmd = "ipfs add --nocopy -q -r".split()
        else:
            cmd = "ipfs add -q -r".split()
        cmd.append(os.fsdecode(album_dir))
        try:
            output = util.command_output(cmd).stdout.split()
        except (OSError, subprocess.CalledProcessError) as exc:
            self._log.error("Failed to add {}, error: {}", album_dir, exc)
            return False
        length = len(output)

        for linenr, line in enumerate(output):
            line = line.strip()
            if linenr == length - 1:
                # last printed line is the album hash
                self._log.info("album: {}", line)
                album.ipfs = line
            else:
                try:
                    item = album.items()[linenr]
                    self._log.info("item: {}", line)
                    item.ipfs = line
                    item.store()
                except IndexError:
                    # if there's non music files in the to-add folder they'll
                    # get ignored here
                    pass

        return True

    def ipfs_get(self, lib: Library, queries: Sequence[str]) -> None:
        query = queries[0]
        # Check if query is a hash
        # TODO: generalize to other hashes; probably use a multihash
        # implementation
        if query.startswith("Qm") and len(query) == 46:
            self.ipfs_get_from_hash(lib, query)
        else:
            albums = self.query(lib, query)
            for album in albums:
                self.ipfs_get_from_hash(lib, album.ipfs)

    def ipfs_get_from_hash(self, lib: Library, _hash: str) -> bool | None:
        try:
            cmd = "ipfs get".split()
            cmd.append(_hash)
            util.command_output(cmd)
        except (OSError, subprocess.CalledProcessError) as err:
            self._log.error(
                "Failed to get {} from ipfs.\n{.output}", _hash, err
            )
            return False

        self._log.info("Getting {} from ipfs", _hash)
        imp = ui.commands.TerminalImportSession(
            lib, loghandler=None, query=None, paths=[_hash]
        )
        imp.run()
        shutil.rmtree(_hash)
        return None

    def ipfs_publish(self, lib: Library) -> bool | None:
        with tempfile.NamedTemporaryFile() as tmp:
            self.ipfs_added_albums(lib, tmp.name)
            try:
                if self.config["nocopy"]:
                    cmd = "ipfs add --nocopy -q ".split()
                else:
                    cmd = "ipfs add -q ".split()
                cmd.append(tmp.name)
                output = util.command_output(cmd).stdout
            except (OSError, subprocess.CalledProcessError) as err:
                msg = f"Failed to publish library. Error: {err}"
                self._log.error(msg)
                return False
            self._log.info("hash of library: {}", output)
        return None

    def ipfs_import(self, lib: Library, args: Sequence[str]) -> bool | None:
        _hash = args[0]
        if len(args) > 1:
            lib_name = args[1]
        else:
            lib_name = _hash
        remote_libs = self._remote_libs_path(lib)
        if not os.path.exists(remote_libs):
            try:
                os.makedirs(remote_libs)
            except OSError as e:
                self._log.error(
                    "Could not create {}. Error: {}",
                    os.fsdecode(remote_libs),
                    e,
                )
                return False
        path = os.path.join(remote_libs, lib_name.encode() + b".db")
        if not os.path.exists(path):
            cmd = f"ipfs get {_hash} -o".split()
            cmd.append(os.fsdecode(path))
            try:
                util.command_output(cmd)
            except (OSError, subprocess.CalledProcessError):
                self._log.error("Could not import {}", _hash)
                return False

        # add all albums from remotes into a combined library
        jpath = os.path.join(remote_libs, b"joined.db")
        jlib = library.Library(jpath)
        nlib = library.Library(path)
        for album in nlib.albums():
            if not self.already_added(album, jlib):
                new_album = []
                for item in album.items():
                    item.id = None
                    new_album.append(item)
                added_album = jlib.add_album(new_album)
                added_album.ipfs = album.ipfs
                added_album.store()
        return None

    def already_added(self, check: Album, jlib: Library) -> bool:
        for jalbum in jlib.albums():
            if jalbum.mb_albumid == check.mb_albumid:
                return True
        return False

    def ipfs_list(self, lib: Library, args: Sequence[str]) -> None:
        fmt = config["format_album"].get()
        try:
            albums = self.query(lib, args)
        except OSError:
            ui.print_("No imported libraries yet.")
            return

        for album in albums:
            ui.print_(format(album, fmt), " : ", album.ipfs.decode())

    def query(self, lib: Library, args: str | Sequence[str]) -> Results[Album]:
        with self.remote_lib(lib) as rlib:
            return rlib.albums(args)

    def _remote_libs_path(self, lib: Library) -> bytes:
        lib_root = os.path.dirname(os.fsencode(lib.path))
        return os.path.join(lib_root, b"remotes")

    @contextmanager
    def remote_lib(self, lib: Library) -> Iterator[Library]:
        remote_libs = self._remote_libs_path(lib)
        path = os.path.join(remote_libs, b"joined.db")
        if not os.path.isfile(path):
            raise OSError

        remote_lib = library.Library(path)

        try:
            yield remote_lib
        finally:
            remote_lib._close()

    def ipfs_added_albums(self, rlib: Library, tmpname: str) -> Library:
        """Returns a new library with only albums/items added to ipfs"""
        tmplib = library.Library(
            tmpname, directory="/ipfs/", set_music_dir=False
        )
        with tmplib.music_dir_context():
            for album in rlib.albums():
                try:
                    if album.ipfs:
                        self.create_new_album(album, tmplib)
                except AttributeError:
                    pass
        return tmplib

    def create_new_album(self, album: Album, tmplib: Library) -> bool | None:
        items = []
        for item in album.items():
            try:
                if not item.ipfs:
                    break
            except AttributeError:
                pass
            item_path = os.fsdecode(os.path.basename(item.path))
            # Clear current path from item
            item.path = os.fsencode(f"{album.ipfs}/{item_path}")

            item.id = None
            items.append(item)
        if len(items) < 1:
            return False
        self._log.info("Adding '{}' to temporary library", album)
        new_album = tmplib.add_album(items)
        new_album.ipfs = album.ipfs
        new_album.store(inherit=False)
        return None
