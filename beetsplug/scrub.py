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
            if f.tags is None:
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

    # MPEG-4 covr atoms only store JPEG or PNG. mediafile raises
    # ValueError for any other MIME type (#2498).
    _MP4_ART_MIMES = frozenset({"image/jpeg", "image/png"})

    def _images_for_restore(
        self,
        mf: mediafile.MediaFile,
        images: list[mediafile.Image] | None,
        path: bytes,
    ) -> list[mediafile.Image] | None:
        """Drop art the container cannot store, instead of failing on write."""
        if not images or mf.type not in ("aac", "alac"):
            return images
        kept: list[mediafile.Image] = []
        for img in images:
            mime = img.mime_type or ""
            if mime in self._MP4_ART_MIMES:
                kept.append(img)
            else:
                self._log.error(
                    "could not restore art for {}: "
                    "MP4 files only supports PNG and JPEG images ({})",
                    util.displayable_path(path),
                    mime or "unknown",
                )
        return kept

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
            images = self._images_for_restore(mf, images, item.path)
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
