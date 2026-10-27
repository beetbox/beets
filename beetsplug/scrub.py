"""Cleans extraneous metadata from files' tags via a command or
automatically whenever tags are written.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import mediafile
import mutagen
from mutagen.id3 import ID3
from mutagen.mp4 import MP4Tags

from beets import config, ui, util
from beets.plugins import BeetsPlugin

if TYPE_CHECKING:
    from beets.importer import ImportSession, ImportTask
    from beets.library import Item, Library


class ScrubCLIOpts(Protocol):
    limit: int | None
    write: bool


_MUTAGEN_FORMATS = {
    "asf": "ASF",
    "apev2": "APEv2File",
    "flac": "FLAC",
    "id3": "ID3FileType",
    "mp3": "MP3",
    "mp4": "MP4",
    "oggflac": "OggFLAC",
    "oggspeex": "OggSpeex",
    "oggtheora": "OggTheora",
    "oggvorbis": "OggVorbis",
    "oggopus": "OggOpus",
    "trueaudio": "TrueAudio",
    "wavpack": "WavPack",
    "monkeysaudio": "MonkeysAudio",
    "optimfrog": "OptimFROG",
}


class ScrubPlugin(BeetsPlugin):
    """Removes extraneous metadata from files' tags."""

    def __init__(self) -> None:
        super().__init__()
        self.config.add({"auto": True, "keep_tags": []})
        self.keep_tags = {
            tag.casefold() for tag in self.config["keep_tags"].as_str_seq()
        }

        if self.config["auto"]:
            self.register_listener("import_task_files", self.import_task_files)

    def commands(self) -> list[ui.Subcommand]:
        def scrub_func(
            lib: Library, opts: ScrubCLIOpts, args: list[str]
        ) -> None:
            # Walk through matching files and remove tags.
            for item in lib.items(args, limit=opts.limit):
                self._log.info("scrubbing: {.filepath}", item)
                self._scrub_item(item, opts.write)

        scrub_cmd = ui.Subcommand("scrub", help="clean audio tags")
        scrub_cmd.parser.add_option(
            "-W",
            "--nowrite",
            dest="write",
            action="store_false",
            default=True,
            help="leave tags empty",
        )
        scrub_cmd.parser.add_limit_option()
        scrub_cmd.func = scrub_func

        return [scrub_cmd]

    @staticmethod
    def _mutagen_classes() -> list[type[Any]]:
        """Get a list of file type classes from the Mutagen module."""
        classes = []
        for modname, clsname in _MUTAGEN_FORMATS.items():
            mod = __import__(f"mutagen.{modname}", fromlist=[clsname])
            classes.append(getattr(mod, clsname))
        return classes

    def _is_kept(self, tags: Any, key: str) -> bool:
        """Check whether the tag stored under `key` is in `keep_tags`."""
        names = [key]
        if isinstance(tags, (ID3, MP4Tags)):
            # Also match key prefixes and bare TXXX/freeform names.
            parts = key.split(":")
            names += [":".join(parts[:i]) for i in range(1, len(parts))]
            if parts[0] == "TXXX":
                names.append(key.split(":", 1)[1])
            elif parts[0] == "----" and len(parts) > 2:
                names.append(key.split(":", 2)[2])
        return any(name.casefold() in self.keep_tags for name in names)

    @staticmethod
    def _remove_tags(f: Any, keys: list[str]) -> None:
        """Remove the given tags from a file and save it."""
        for key in keys:
            del f[key]
        if isinstance(f.tags, ID3):
            # Drop unparsed frames and ID3v1, like delete() does.
            f.tags.unknown_frames.clear()
            if config["id3v23"].get(bool):
                f.tags.update_to_v23()
                f.save(v1=0, v2_version=3)
            else:
                f.save(v1=0)
        else:
            f.save()

    def _scrub(self, path: bytes) -> None:
        """Remove all tags from a file, except those in `keep_tags`."""
        for cls in self._mutagen_classes():
            # Try opening the file with this type, but just skip in the
            # event of any error.
            try:
                f = cls(util.syspath(path))
            except Exception:
                continue
            if f.tags is None:
                continue

            keys = list(f.keys())
            if isinstance(f.tags, ID3) and f.tags.version < (2, 0, 0):
                # ID3v1 only: a partial save would add an ID3v2 header.
                unkept = keys
            else:
                unkept = [k for k in keys if not self._is_kept(f.tags, k)]

            # Remove the tag for this type.
            try:
                if len(unkept) == len(keys):
                    f.delete()
                elif unkept:
                    kept = [k for k in keys if k not in unkept]
                    self._log.debug("keeping tags: {}", ", ".join(kept))
                    self._remove_tags(f, unkept)
            except NotImplementedError:
                # Some Mutagen metadata subclasses (namely, ASFTag) do not
                # support .delete(), presumably because it is impossible to
                # remove them. In this case, we just remove all the tags.
                for tag in f.keys():
                    del f[tag]
                f.save()
            except (OSError, mutagen.MutagenError) as exc:
                self._log.error(
                    "could not scrub {}: {}", util.displayable_path(path), exc
                )

    def _scrub_item(self, item: Item, restore: bool) -> None:
        """Remove tags from an Item's associated file and, if `restore`
        is enabled, write the database's tags back to the file.
        """
        # Get album art if we need to restore it.
        if restore:
            try:
                mf = mediafile.MediaFile(
                    util.syspath(item.path), config["id3v23"].get(bool)
                )
            except mediafile.UnreadableFileError as exc:
                self._log.error("could not open file to scrub: {}", exc)
                return
            images = mf.images

        # Remove all tags.
        self._scrub(item.path)

        # Restore tags, if enabled.
        if restore:
            self._log.debug("writing new tags after scrub")
            item.try_write()
            if images:
                self._log.debug("restoring art")
                try:
                    mf = mediafile.MediaFile(
                        util.syspath(item.path), config["id3v23"].get(bool)
                    )
                    mf.images = images
                    mf.save()
                except mediafile.UnreadableFileError as exc:
                    self._log.error("could not write tags: {}", exc)

    def import_task_files(
        self, session: ImportSession, task: ImportTask
    ) -> None:
        """Automatically scrub imported files."""
        if not ui.should_write():
            return
        for item in task.imported_items():
            self._log.debug("auto-scrubbing {.filepath}", item)
            self._scrub_item(item, True)
