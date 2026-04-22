# This file is part of beets.
# Copyright 2016, Jakob Schnitzer.
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

"""Converts tracks or albums to external directory"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
import tempfile
import threading
from functools import cached_property
from string import Template
from typing import TYPE_CHECKING, NamedTuple

import mediafile
from confuse import ConfigTypeError, Optional

from beets import plugins, ui, util
from beets.library import Item, parse_query_string
from beets.plugins import BeetsPlugin
from beets.util import par_map
from beets.util.artresizer import ArtResizer
from beets.util.m3u import M3UFile
from beetsplug._utils import art

if TYPE_CHECKING:
    import optparse
    from collections.abc import Generator

    from beets.importer import ImportSession, ImportTask
    from beets.library import Album, Library
    from beets.util.functemplate import Template as FuncTemplate

_fs_lock = threading.Lock()
# Keep track of temporary transcoded files for deletion.
_temp_files: list[bytes] = []

# Some convenient alternate names for formats.
ALIASES = {
    "windows media": "wma",
    "vorbis": "ogg",
}

LOSSLESS_FORMATS = ["ape", "flac", "alac", "wave", "aiff"]


class FormatCommand(NamedTuple):
    command: bytes
    ext: bytes


def replace_ext(path: bytes, ext: bytes) -> bytes:
    """Return the path with its extension replaced by `ext`.

    The new extension must not contain a leading dot.
    """
    ext_dot = b"." + ext
    return os.path.splitext(path)[0] + ext_dot


class ConvertPlugin(BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()
        self.config.add(
            {
                "dest": None,
                "pretend": False,
                "link": False,
                "hardlink": False,
                "threads": os.cpu_count(),
                "format": "mp3",
                "id3v23": "inherit",
                "write_metadata": True,
                "formats": {
                    "aac": {
                        "command": (
                            "ffmpeg -i $source -y -vn -acodec aac -aq 1 $dest"
                        ),
                        "extension": "m4a",
                    },
                    "alac": {
                        "command": (
                            "ffmpeg -i $source -y -vn -acodec alac $dest"
                        ),
                        "extension": "m4a",
                    },
                    "flac": "ffmpeg -i $source -y -vn -acodec flac $dest",
                    "mp3": "ffmpeg -i $source -y -vn -aq 2 $dest",
                    "opus": (
                        "ffmpeg -i $source -y -vn -acodec libopus -ab 96k $dest"
                    ),
                    "ogg": (
                        "ffmpeg -i $source -y -vn -acodec libvorbis -aq 3 $dest"
                    ),
                    "wma": "ffmpeg -i $source -y -vn -acodec wmav2 -vn $dest",
                },
                "max_bitrate": None,
                "auto": False,
                "auto_keep": False,
                "tmpdir": None,
                "quiet": False,
                "embed": True,
                "paths": {},
                "no_convert": "",
                "never_convert_lossy_files": False,
                "copy_album_art": False,
                "album_art_maxwidth": 0,
                "delete_originals": False,
                "playlist": None,
                "force": False,
                "keep_new": False,
            }
        )
        self.early_import_stages = [self.auto_convert, self.auto_convert_keep]

        self.register_listener("import_task_files", self._cleanup)

    def commands(self) -> list[ui.Subcommand]:
        cmd = ui.Subcommand("convert", help="convert to external location")
        cmd.parser.add_option(
            "-p",
            "--pretend",
            action="store_true",
            default=self.config["pretend"].get(),
            help="show actions but do nothing",
        )
        cmd.parser.add_option(
            "-t",
            "--threads",
            action="store",
            type="int",
            default=self.config["threads"].get(),
            help=(
                "change the number of threads, defaults to maximum available"
                " processors"
            ),
        )
        cmd.parser.add_option(
            "-k",
            "--keep-new",
            action="store_true",
            dest="keep_new",
            default=self.config["keep_new"].get(),
            help="keep only the converted and move the old files",
        )
        cmd.parser.add_option(
            "-d",
            "--dest",
            action="store",
            default=self.config["dest"].get(),
            help="set the destination directory",
        )
        cmd.parser.add_option(
            "-f",
            "--format",
            action="store",
            default=self.config["format"].get(),
            help="set the target format of the tracks",
        )
        cmd.parser.add_option(
            "-y",
            "--yes",
            action="store_true",
            help="do not ask for confirmation",
        )
        cmd.parser.add_option(
            "-l",
            "--link",
            action="store_true",
            default=self.config["link"].get(),
            help="symlink files that do not need transcoding.",
        )
        cmd.parser.add_option(
            "-H",
            "--hardlink",
            action="store_true",
            default=self.config["hardlink"].get(),
            help=(
                "hardlink files that do not need transcoding. Overrides --link."
            ),
        )
        cmd.parser.add_option(
            "-m",
            "--playlist",
            action="store",
            default=self.config["playlist"].get(),
            help="""create an m3u8 playlist file containing
                              the converted files. The playlist file will be
                              saved below the destination directory, thus
                              PLAYLIST could be a file name or a relative path.
                              To ensure a working playlist when transferred to
                              a different computer, or opened from an external
                              drive, relative paths pointing to media files
                              will be used.""",
        )
        cmd.parser.add_option(
            "-F",
            "--force",
            action="store_true",
            default=self.config["force"].get(),
            help=(
                "force transcoding. Ignores no_convert, "
                "never_convert_lossy_files, and max_bitrate"
            ),
        )
        cmd.parser.add_album_option()
        cmd.func = self.convert_func
        return [cmd]

    @cached_property
    def dest(self) -> bytes:
        dest = self.config["dest"].get()
        if not dest:
            raise ui.UserError("no convert destination set")
        return util.bytestring_path(dest)

    @cached_property
    def threads(self) -> int:
        return self.config["threads"].get(int)

    @cached_property
    def path_formats(self) -> dict[str, FuncTemplate]:
        return ui.get_path_formats(self.config["paths"] or None)

    @cached_property
    def fmt(self) -> str:
        return self.config["format"].as_str().lower()

    @cached_property
    def playlist(self) -> bytes | None:
        if (playlist := self.config["playlist"].get()) is not None:
            return os.path.join(self.dest, util.bytestring_path(playlist))

        return None

    @cached_property
    def pretend(self) -> bool:
        return self.config["pretend"].get(bool)

    @cached_property
    def force(self) -> bool:
        return self.config["force"].get(bool)

    @cached_property
    def hardlink(self) -> bool:
        return self.config["hardlink"].get(bool)

    @cached_property
    def link(self) -> bool:
        return not self.hardlink and self.config["link"].get(bool)

    @cached_property
    def command(self) -> FormatCommand:
        """Return the command template and the extension from the config."""
        fmt = ALIASES.get(self.fmt, self.fmt)

        try:
            format_info = self.config["formats"][fmt].get(dict)
            command = format_info["command"]
            extension = format_info.get("extension", fmt)
        except KeyError:
            raise ui.UserError(
                f'convert: format {fmt} needs the "command" field'
            )
        except ConfigTypeError:
            command = self.config["formats"][fmt].get(str)
            extension = fmt

        # Convenience and backwards-compatibility shortcuts.
        keys = self.config.keys()
        if "command" in keys:
            command = self.config["command"].as_str()
        elif "opts" in keys:
            # Undocumented option for backwards compatibility with < 1.3.1.
            command = (
                f"ffmpeg -i $source -y {self.config['opts'].as_str()} $dest"
            )
        if "extension" in keys:
            extension = self.config["extension"].as_str()

        return FormatCommand(command.encode("utf-8"), extension.encode("utf-8"))

    def auto_convert(self, session: ImportSession, task: ImportTask) -> None:
        if self.config["auto"]:
            par_map(
                lambda item: self.convert_on_import(session.lib, item),
                task.imported_items(),
            )

    def auto_convert_keep(
        self, session: ImportSession, task: ImportTask
    ) -> None:
        if self.config["auto_keep"]:
            items = task.imported_items()

            # Filter items based on should_transcode function
            items = [item for item in items if self.should_transcode(item)]

            self._parallel_convert(items, keep_new=False)

    # Utilities converted from functions to methods on logging overhaul

    def encode(
        self,
        command_bytes: bytes,
        source_bytes: bytes,
        dest_bytes: bytes,
        pretend: bool = False,
    ) -> None:
        """Encode source to destination using given command template.

        Raises `subprocess.CalledProcessError` if the command exited with a
        non-zero status code.
        """
        quiet = self.config["quiet"].get(bool)

        if not quiet and not pretend:
            self._log.info("Encoding {}", util.displayable_path(source_bytes))

        command = os.fsdecode(command_bytes)
        source = os.fsdecode(source_bytes)
        dest = os.fsdecode(dest_bytes)

        # Substitute $source and $dest in the argument list.
        args = shlex.split(command)
        encode_cmd = []
        for i, arg in enumerate(args):
            args[i] = Template(arg).safe_substitute(
                {
                    "source": source,
                    "dest": dest,
                }
            )
            encode_cmd.append(os.fsdecode(args[i]))

        if pretend:
            self._log.info("{}", " ".join(args))
            return

        try:
            util.command_output(encode_cmd)
        except subprocess.CalledProcessError as exc:
            # Something went wrong (probably Ctrl+C), remove temporary files
            self._log.info(
                "Encoding {} failed. Cleaning up...",
                util.displayable_path(source),
            )
            self._log.debug(
                "Command {0} exited with status {1.returncode}: {1.output}",
                args,
                exc,
            )
            util.remove(dest)
            util.prune_dirs(os.path.dirname(dest))
            raise
        except OSError as exc:
            raise ui.UserError(
                f"convert: couldn't invoke {' '.join(args)!r}: {exc}"
            )

        if not quiet and not pretend:
            self._log.info(
                "Finished encoding {}", util.displayable_path(source)
            )

    def in_no_convert(self, item: Item) -> bool:
        no_convert_query = self.config["no_convert"].as_str()

        if no_convert_query:
            query, _ = parse_query_string(no_convert_query, Item)
            return query.match(item)
        else:
            return False

    def should_transcode(self, item: Item) -> bool:
        """Determine whether the item should be transcoded as part of
        conversion (i.e., its bitrate is high or it has the wrong format).

        If ``force`` is True, safety checks like ``no_convert`` and
        ``never_convert_lossy_files`` are ignored and the item is always
        transcoded.
        """
        if self.force:
            return True
        if self.in_no_convert(item) or (
            self.config["never_convert_lossy_files"].get(bool)
            and item.format.lower() not in LOSSLESS_FORMATS
        ):
            return False
        maxbr = self.config["max_bitrate"].get(Optional(int))
        if maxbr is not None and item.bitrate >= 1000 * maxbr:
            return True
        return self.fmt != item.format.lower()

    def convert_item(
        self, keep_new: bool
    ) -> Generator[tuple[Item | None, bytes | None, bytes | None], Item, None]:
        """A pipeline thread that converts `Item` objects from a
        library.
        """
        pretend, link, hardlink = self.pretend, self.link, self.hardlink
        command, ext = self.command
        item, original, converted = None, None, None

        while True:
            item = yield (item, original, converted)
            dest = item.destination(
                basedir=self.dest, path_formats=self.path_formats
            )

            # Ensure that desired item is readable before processing it. Needed
            # to avoid any side-effect of the conversion (linking, keep_new,
            # refresh) if we already know that it will fail.
            try:
                mediafile.MediaFile(util.syspath(item.path))
            except mediafile.UnreadableFileError as exc:
                self._log.error("Could not open file to convert: {}", exc)
                continue

            # When keeping the new file in the library, we first move the
            # current (pristine) file to the destination. We'll then copy it
            # back to its old path or transcode it to a new path.
            if keep_new:
                original = dest
                converted = item.path
                if self.should_transcode(item):
                    converted = replace_ext(converted, ext)
            else:
                original = item.path
                if self.should_transcode(item):
                    dest = replace_ext(dest, ext)
                converted = dest

            # Ensure that only one thread tries to create directories at a
            # time. (The existence check is not atomic with the directory
            # creation inside this function.)
            if not pretend:
                with _fs_lock:
                    util.mkdirall(dest)

            if os.path.exists(util.syspath(dest)):
                self._log.info(
                    "Skipping {.filepath} (target file exists)", item
                )
                continue

            if keep_new:
                if pretend:
                    self._log.info(
                        "mv {.filepath} {}",
                        item,
                        util.displayable_path(original),
                    )
                else:
                    self._log.info(
                        "Moving to {}", util.displayable_path(original)
                    )
                    util.move(item.path, original)

            if self.should_transcode(item):
                linked = False
                try:
                    self.encode(command, original, converted, pretend)
                except subprocess.CalledProcessError:
                    continue
            else:
                linked = link or hardlink
                if pretend:
                    msg = "ln" if hardlink else ("ln -s" if link else "cp")

                    self._log.info(
                        "{} {} {}",
                        msg,
                        util.displayable_path(original),
                        util.displayable_path(converted),
                    )
                else:
                    # No transcoding necessary.
                    msg = (
                        "Hardlinking"
                        if hardlink
                        else ("Linking" if link else "Copying")
                    )

                    self._log.info("{} {.filepath}", msg, item)

                    if hardlink:
                        util.hardlink(original, converted)
                    elif link:
                        util.link(original, converted)
                    else:
                        util.copy(original, converted)

            if pretend:
                continue

            id3v23 = self.config["id3v23"].as_choice([True, False, "inherit"])
            if id3v23 == "inherit":
                id3v23 = None

            # Write tags from the database to the file if requested
            if self.config["write_metadata"].get(bool):
                item.try_write(path=converted, id3v23=id3v23)

            if keep_new:
                # If we're keeping the transcoded file, read it again (after
                # writing) to get new bitrate, duration, etc.
                item.path = converted
                item.read()
                item.store()  # Store new path and audio data.

            if self.config["embed"] and not linked:
                album = item._cached_album
                if album and album.artpath:
                    maxwidth = self._get_art_resize(album.artpath)
                    self._log.debug(
                        "embedding album art from {.art_filepath}", album
                    )
                    art.embed_item(
                        self._log,
                        item,
                        album.artpath,
                        maxwidth,
                        itempath=converted,
                        id3v23=id3v23,
                    )

            if keep_new:
                plugins.send(
                    "after_convert", item=item, dest=dest, keepnew=True
                )
            else:
                plugins.send(
                    "after_convert", item=item, dest=converted, keepnew=False
                )

    def copy_album_art(self, album: Album) -> None:
        """Copies or converts the associated cover art of the album. Album must
        have at least one track.
        """
        if not album or not album.artpath:
            return

        album_item = album.items().get()
        # Album shouldn't be empty.
        if not album_item:
            return

        # Get the destination of the first item (track) of the album, we use
        # this function to format the path accordingly to path_formats.
        dest = album_item.destination(
            basedir=self.dest, path_formats=self.path_formats
        )

        # Remove item from the path.
        dest = os.path.join(*util.components(dest)[:-1])

        dest = album.art_destination(album.artpath, item_dir=dest)
        if album.artpath == dest:
            return

        if not (pretend := self.pretend):
            util.mkdirall(dest)

        if os.path.exists(util.syspath(dest)):
            self._log.info(
                "Skipping {.art_filepath} (target file exists)", album
            )
            return

        # Decide whether we need to resize the cover-art image.
        maxwidth = self._get_art_resize(album.artpath)

        # Either copy or resize (while copying) the image.
        if maxwidth is not None:
            self._log.info(
                "Resizing cover art from {.art_filepath} to {}",
                album,
                util.displayable_path(dest),
            )
            if not pretend:
                ArtResizer.shared.resize(maxwidth, album.artpath, dest)
        else:
            link, hardlink = self.link, self.hardlink
            if pretend:
                msg = "ln" if hardlink else ("ln -s" if link else "cp")

                self._log.info(
                    "{} {.art_filepath} {}",
                    msg,
                    album,
                    util.displayable_path(dest),
                )
            else:
                msg = (
                    "Hardlinking"
                    if hardlink
                    else ("Linking" if link else "Copying")
                )

                self._log.info(
                    "{} cover art from {.art_filepath} to {}",
                    msg,
                    album,
                    util.displayable_path(dest),
                )
                if hardlink:
                    util.hardlink(album.artpath, dest)
                elif link:
                    util.link(album.artpath, dest)
                else:
                    util.copy(album.artpath, dest)

    def convert_func(
        self, lib: Library, opts: optparse.Values, args: list[str]
    ) -> None:
        self.config.set(vars(opts))
        dest, pretend = self.dest, self.pretend

        if opts.album:
            albums = lib.albums(args)
            items = [i for a in albums for i in a.items()]
            if not pretend:
                for a in albums:
                    ui.print_(format(a, ""))
        else:
            items = list(lib.items(args))
            if not pretend:
                for i in items:
                    ui.print_(format(i, ""))

        if not items:
            self._log.error("Empty query result.")
            return
        if not (pretend or opts.yes or ui.input_yn("Convert? (Y/n)")):
            return

        if opts.album and self.config["copy_album_art"]:
            for album in albums:
                self.copy_album_art(album)

        # If the user supplied a playlist name, create a playlist for files
        # copied to the destination.
        pl_normpath = None
        items_paths = None
        if playlist := self.playlist:
            # Playlist paths are understood as relative to the dest directory.
            pl_normpath = util.normpath(playlist)
            pl_dir = os.path.dirname(pl_normpath)
            items_paths = []
            for item in items:
                item_path = item.destination(
                    basedir=dest, path_formats=self.path_formats
                )

                # When keeping new files in the library, destination paths
                # keep original files and extensions.
                if not opts.keep_new and self.should_transcode(item):
                    item_path = replace_ext(item_path, self.command.ext)

                items_paths.append(os.path.relpath(item_path, pl_dir))

        self._parallel_convert(
            items, keep_new=self.config["keep_new"].get(bool)
        )

        if playlist:
            self._log.info("Creating playlist file {}", pl_normpath)
            if not pretend:
                m3ufile = M3UFile(playlist)
                m3ufile.set_contents(items_paths)
                m3ufile.write()

    def convert_on_import(self, _: Library, item: Item) -> None:
        """Transcode a file automatically after it is imported into the
        library.
        """
        if self.should_transcode(item):
            command, ext = self.command

            # Create a temporary file for the conversion.
            tmpdir = self.config["tmpdir"].get()
            if tmpdir:
                tmpdir = util.bytestring_path(tmpdir)
            fd, dest = tempfile.mkstemp(b"." + ext, dir=tmpdir)
            os.close(fd)
            dest = util.bytestring_path(dest)
            _temp_files.append(dest)  # Delete the transcode later.

            # Convert.
            try:
                self.encode(command, item.path, dest)
            except subprocess.CalledProcessError:
                return

            # Change the newly-imported database entry to point to the
            # converted file.
            source_path = item.path
            item.path = dest
            item.write()
            item.read()  # Load new audio information data.
            item.store()

            if self.config["delete_originals"]:
                self._log.log(
                    logging.DEBUG if self.config["quiet"] else logging.INFO,
                    "Removing original file {}",
                    source_path,
                )
                util.remove(source_path, False)

    def _get_art_resize(self, artpath: bytes) -> int | None:
        """For a given piece of album art, determine whether or not it needs
        to be resized according to the user's settings. If so, returns the
        new size. If not, returns None.
        """
        newwidth = None
        if self.config["album_art_maxwidth"]:
            maxwidth = self.config["album_art_maxwidth"].get(int)
            size = ArtResizer.shared.get_size(artpath)
            self._log.debug("image size: {}", size)
            if size:
                if size[0] > maxwidth:
                    newwidth = maxwidth
            else:
                self._log.warning(
                    "Could not get size of image (please see "
                    "documentation for dependencies)."
                )
        return newwidth

    def _cleanup(self, task: ImportTask, session: ImportSession) -> None:
        for path in task.old_paths:
            if path in _temp_files:
                if os.path.isfile(util.syspath(path)):
                    util.remove(path)
                _temp_files.remove(path)

    def _parallel_convert(self, items: list[Item], keep_new: bool):
        """Run the convert_item function for every items on as many thread as
        defined in threads
        """
        convert = [self.convert_item(keep_new) for _ in range(self.threads)]
        pipe = util.pipeline.Pipeline([iter(items), convert])
        pipe.run_parallel()
