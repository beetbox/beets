"""Cleans extraneous metadata from files' tags via a command or
automatically whenever tags are written.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import mediafile
import mutagen

from beets import config, ui, util
from beets.plugins import BeetsPlugin

if TYPE_CHECKING:
    from beets.importer import ImportSession, ImportTask
    from beets.library import Item, Library


class ScrubCLIOpts(Protocol):
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
        self.config.add({"auto": True})

        if self.config["auto"]:
            self.register_listener("import_task_files", self.import_task_files)

    def commands(self) -> list[ui.Subcommand]:
        def scrub_func(
            lib: Library, opts: ScrubCLIOpts, args: list[str]
        ) -> None:
            # Walk through matching files and remove tags.
            for item in lib.items(args):
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

    def _scrub(self, path: bytes) -> None:
        """Remove all tags from a file."""
        for cls in self._mutagen_classes():
            # Try opening the file with this type, but just skip in the
            # event of any error.
            try:
                f = cls(util.syspath(path))
            except Exception:
                continue
            # Deleting an empty tag block costs a full write for nothing.
            # `_scrub_item` has normally emptied the native one already.
            if not f.tags:
                continue

            # Remove the tag for this type.
            try:
                f.delete()
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

    def _clear_native_tags(self, item: Item) -> tuple[bool, list[Any]]:
        """Empty the file's own tag block in one write.

        Return whether the file could be read, and the art found in it, which
        the caller must write back.

        `mutagen.flac.FLAC.delete()` saves with ``padding=lambda x: 0``, so the
        file shrinks and writing the tags back has to grow it again: two
        rewrites of the audio stream per track. Clearing in memory and saving
        once reuses the padding the file already reserves. Passing a `padding`
        hint here would defeat that.

        The art is left out of this save on purpose: MP3 and Ogg keep it inside
        the tag block, so restoring it here would make the block non-empty and
        `_scrub` would delete it again.
        """
        try:
            mf = mediafile.MediaFile(
                util.syspath(item.path), config["id3v23"].get(bool)
            )
        except mediafile.UnreadableFileError as exc:
            self._log.error("could not open file to scrub: {}", exc)
            return False, []

        images = mf.images or []
        mgfile = mf.mgfile

        if mgfile.tags is not None:
            try:
                mgfile.tags.clear()
            except (AttributeError, NotImplementedError):
                # Not a mutable mapping; leave it to `_scrub`.
                return True, images

            try:
                mf.save()
            except (mediafile.UnreadableFileError, mutagen.MutagenError) as exc:
                self._log.error(
                    "could not scrub {}: {}",
                    util.displayable_path(item.path),
                    exc,
                )

        return True, images

    def _scrub_item(self, item: Item, restore: bool) -> None:
        """Remove tags from an Item's associated file and, if `restore`
        is enabled, write the database's tags back to the file.
        """
        images: list[Any] = []
        if restore:
            readable, images = self._clear_native_tags(item)
            if not readable:
                return

        # Remove all tags.
        self._scrub(item.path)

        # Restore tags, if enabled.
        if restore:
            self._log.debug("writing new tags after scrub")
            # `tags` is merged into what beets passes to MediaFile.update(), so
            # the art costs no extra write.
            item.try_write(tags={"images": images} if images else None)

    def import_task_files(
        self, session: ImportSession, task: ImportTask
    ) -> None:
        """Automatically scrub imported files."""
        if not ui.should_write():
            return
        for item in task.imported_items():
            self._log.debug("auto-scrubbing {.filepath}", item)
            self._scrub_item(item, True)
