"""High-level utilities for manipulating image files associated with
music and items' embedded album art.
"""

from __future__ import annotations

import os
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING

import mediafile

from beets.util import bytestring_path, displayable_path, syspath
from beets.util.artresizer import ArtResizer

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from beets.dbcore import Query
    from beets.library import Album, Item, Library
    from beets.logging import BeetsLogger as Logger
    from beets.util import PathLike


def mediafile_image(
    image_path: bytes, maxwidth: int | None = None
) -> mediafile.Image:
    """Return a `mediafile.Image` object for the path."""

    with open(syspath(image_path), "rb") as f:
        data = f.read()
    return mediafile.Image(data, type=mediafile.ImageType.front)


def get_art(log: Logger, item: Item) -> bytes | None:
    # Extract the art.
    try:
        mf = mediafile.MediaFile(syspath(item.path))
    except mediafile.UnreadableFileError as exc:
        log.warning("Could not extract art from {.filepath}: {}", item, exc)
        return None

    return mf.art


def embed_item(
    log: Logger,
    item: Item,
    imagepath: bytes,
    maxwidth: int | None = None,
    itempath: bytes | None = None,
    compare_threshold: int = 0,
    ifempty: bool = False,
    as_album: bool = False,
    id3v23: bool | None = None,
    quality: int = 0,
) -> None:
    """Embed an image into the item's media file."""
    # Conditions.
    if compare_threshold:
        is_similar = check_art_similarity(
            log, item, imagepath, compare_threshold
        )
        if is_similar is None:
            log.warning("Error while checking art similarity; skipping.")
            return
        if not is_similar:
            log.info("Image not similar; skipping.")
            return

    if ifempty and get_art(log, item):
        log.info("media file already contained art")
        return

    # Filters.
    if maxwidth and not as_album:
        imagepath = resize_image(log, imagepath, maxwidth, quality)

    # Get the `Image` object from the file.
    try:
        log.debug("embedding {}", displayable_path(imagepath))
        image = mediafile_image(imagepath, maxwidth)
    except OSError as exc:
        log.warning("could not read image file: {}", exc)
        return

    # Make sure the image kind is safe (some formats only support PNG
    # and JPEG).
    if image.mime_type not in ("image/jpeg", "image/png"):
        log.info("not embedding image of unsupported type: {.mime_type}", image)
        return

    item.try_write(path=itempath, tags={"images": [image]}, id3v23=id3v23)


def embed_album(
    log: Logger,
    album: Album,
    maxwidth: int | None = None,
    quiet: bool = False,
    compare_threshold: int = 0,
    ifempty: bool = False,
    quality: int = 0,
) -> None:
    """Embed album art into all of the album's items."""
    imagepath = album.artpath
    if not imagepath:
        log.info("No album art present for {}", album)
        return
    if not os.path.isfile(syspath(imagepath)):
        log.info(
            "Album art not found at {} for {}",
            displayable_path(imagepath),
            album,
        )
        return
    if maxwidth:
        imagepath = resize_image(log, imagepath, maxwidth, quality)

    log.info("Embedding album art into {}", album)

    for item in album.items():
        embed_item(
            log,
            item,
            imagepath,
            maxwidth,
            None,
            compare_threshold,
            ifempty,
            as_album=True,
            quality=quality,
        )


def resize_image(
    log: Logger, imagepath: bytes, maxwidth: int, quality: int
) -> bytes:
    """Returns path to an image resized to maxwidth and encoded with the
    specified quality level.
    """
    log.debug(
        "Resizing album art to {} pixels wide and encoding at quality level {}",
        maxwidth,
        quality,
    )
    return ArtResizer.shared.resize(maxwidth, imagepath, quality=quality)


def check_art_similarity(
    log: Logger,
    item: Item,
    imagepath: bytes,
    compare_threshold: int,
    artresizer: ArtResizer | None = None,
) -> bool | None:
    """A boolean indicating if an image is similar to embedded item art.

    If no embedded art exists, always return `True`. If the comparison fails
    for some reason, the return value is `None`.

    This must only be called if `ArtResizer.shared.can_compare` is `True`.
    """
    with NamedTemporaryFile(delete=True) as f:
        art = extract(log, f.name, item)

        if not art:
            return True

        if artresizer is None:
            artresizer = ArtResizer.shared

        return artresizer.compare(art, imagepath, compare_threshold)


def extract(log: Logger, outpath: PathLike, item: Item) -> bytes | None:
    art = get_art(log, item)
    outpath = bytestring_path(outpath)
    if not art:
        log.info("No album art present in {}, skipping.", item)
        return None

    # Add an extension to the filename.
    ext = mediafile.image_extension(art)
    if not ext:
        log.warning("Unknown image type in {.filepath}.", item)
        return None
    outpath += bytestring_path(f".{ext}")

    log.info(
        "Extracting album art from: {} to: {}", item, displayable_path(outpath)
    )
    with open(syspath(outpath), "wb") as f:
        f.write(art)
    return outpath


def extract_first(
    log: Logger, outpath: bytes, items: Iterable[Item]
) -> bytes | None:
    for item in items:
        real_path = extract(log, outpath, item)
        if real_path:
            return real_path
    return None


def clear_item(item: Item, log: Logger) -> None:
    if mediafile.MediaFile(syspath(item.path)).images:
        log.debug("Clearing art for {}", item)
        item.try_write(tags={"images": None})


def clear(
    log: Logger, lib: Library, query: str | Sequence[str] | Query | None = None
) -> None:
    items = lib.items(query)
    log.info("Clearing album art from {} items", len(items))
    for item in items:
        clear_item(item, log)
