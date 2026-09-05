"""List duplicate tracks or albums."""

from __future__ import annotations

import os
import shlex
from functools import partial
from typing import TYPE_CHECKING, Any

from beets.library import Album, Item
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, UserError, print_
from beets.util import (
    MoveOperation,
    bytestring_path,
    command_output,
    displayable_path,
    subprocess,
)

if TYPE_CHECKING:
    import optparse
    from collections.abc import Callable, Iterator, Sequence

    from beets.library import AlbumOrItem, LibModel, Library


PLUGIN = "duplicates"


class DuplicatesPlugin(BeetsPlugin):
    """List duplicate tracks or albums"""

    def __init__(self) -> None:
        super().__init__()

        self.config.add(
            {
                "album": False,
                "checksum": "",
                "copy": "",
                "count": False,
                "delete": False,
                "format": "",
                "full": False,
                "keys": [],
                "merge": False,
                "move": "",
                "path": False,
                "tiebreak": {},
                "strict": False,
                "tag": "",
                "remove": False,
            }
        )

        self._command = Subcommand("duplicates", help=__doc__, aliases=["dup"])
        self._command.parser.add_option(
            "-c",
            "--count",
            dest="count",
            action="store_true",
            help="show duplicate counts",
        )
        self._command.parser.add_option(
            "-C",
            "--checksum",
            dest="checksum",
            action="store",
            metavar="PROG",
            help="report duplicates based on arbitrary command",
        )
        self._command.parser.add_option(
            "-d",
            "--delete",
            dest="delete",
            action="store_true",
            help="delete items from library and disk",
        )
        self._command.parser.add_option(
            "-F",
            "--full",
            dest="full",
            action="store_true",
            help="show all versions of duplicate tracks or albums",
        )
        self._command.parser.add_option(
            "-s",
            "--strict",
            dest="strict",
            action="store_true",
            help="report duplicates only if all attributes are set",
        )
        self._command.parser.add_option(
            "-k",
            "--key",
            dest="keys",
            action="append",
            metavar="KEY",
            help="report duplicates based on keys (use multiple times)",
        )
        self._command.parser.add_option(
            "-M",
            "--merge",
            dest="merge",
            action="store_true",
            help="merge duplicate items",
        )
        self._command.parser.add_option(
            "-m",
            "--move",
            dest="move",
            action="store",
            metavar="DEST",
            help="move items to dest",
        )
        self._command.parser.add_option(
            "-o",
            "--copy",
            dest="copy",
            action="store",
            metavar="DEST",
            help="copy items to dest",
        )
        self._command.parser.add_option(
            "-t",
            "--tag",
            dest="tag",
            action="store",
            help="tag matched items with 'k=v' attribute",
        )
        self._command.parser.add_option(
            "-r",
            "--remove",
            dest="remove",
            action="store_true",
            help="remove items from library",
        )
        self._command.parser.add_all_common_options()

    def commands(self) -> list[Subcommand]:
        def _dup(lib: Library, opts: optparse.Values, args: list[str]) -> None:
            self.config.set_args(opts)
            keys = self.config["keys"].as_str_seq()

            if self.config["album"].get(bool):
                self._run_command(
                    lib.albums(args),
                    keys or ["mb_albumid"],
                    "$albumartist - $album",
                    merge_func=self._merge_albums,
                )
            else:
                self._run_command(
                    lib.items(args),
                    keys or ["mb_trackid", "mb_albumid"],
                    "$albumartist - $album - $title",
                    merge_func=self._merge_items,
                )

        self._command.func = _dup
        return [self._command]

    def _run_command(
        self,
        items: Sequence[AlbumOrItem],
        keys: list[str],
        fmt_tmpl_fallback: str,
        *,
        merge_func: Callable[[list[AlbumOrItem]], list[AlbumOrItem]],
    ) -> None:
        """Process one homogeneous set of duplicate candidates."""
        checksum = self.config["checksum"].get(str)
        copy = bytestring_path(self.config["copy"].as_str())
        count = self.config["count"].get(bool)
        delete = self.config["delete"].get(bool)
        remove = self.config["remove"].get(bool)
        fmt_tmpl = self.config["format"].get(str)
        full = self.config["full"].get(bool)
        merge = self.config["merge"].get(bool)
        move = bytestring_path(self.config["move"].as_str())
        path = self.config["path"].get(bool)
        tiebreak = self.config["tiebreak"].get(dict)
        strict = self.config["strict"].get(bool)
        tag = self.config["tag"].get(str)

        # If there's nothing to do, return early. The code below assumes
        # `items` to be non-empty.
        if not items:
            return

        if path:
            fmt_tmpl = "$path"
        elif not fmt_tmpl:
            fmt_tmpl = fmt_tmpl_fallback

        if checksum:
            for i in items:
                k, _ = self._checksum(i, checksum)
            keys = [k]

        for obj_id, obj_count, objs in self._duplicates(
            items,
            keys=keys,
            full=full,
            strict=strict,
            tiebreak=tiebreak,
            merge_func=merge_func if merge else None,
        ):
            if obj_id:  # Skip empty IDs.
                for o in objs:
                    self._process_item(
                        o,
                        copy=copy,
                        move=move,
                        delete=delete,
                        remove=remove,
                        tag=tag,
                        fmt=(
                            fmt_tmpl
                            if not count
                            else f"{fmt_tmpl}: {obj_count}"
                        ),
                    )

    def _process_item(
        self,
        model: LibModel,
        *,
        copy: bytes,
        move: bytes,
        delete: bool,
        tag: str,
        fmt: str,
        remove: bool,
    ) -> None:
        """Process one library model."""
        print_(format(model, fmt))
        if copy:
            model.move(basedir=copy, operation=MoveOperation.COPY)
            model.store()
        if move:
            model.move(basedir=move)
            model.store()
        if delete:
            model.remove(delete=True)
        elif remove:
            model.remove(delete=False)
        if tag:
            try:
                k, v = tag.split("=")
            except Exception:
                raise UserError(f"{PLUGIN}: can't parse k=v tag: {tag}")
            setattr(model, k, v)
            model.store()

    def _checksum(self, model: LibModel, prog: str) -> tuple[str, Any]:
        """Run external `prog` on file path associated with `model`, cache
        output as flexattr on a key that is the name of the program, and
        return the key, checksum tuple.
        """
        args = [
            p.format(file=os.fsdecode(model.path)) for p in shlex.split(prog)
        ]
        key = args[0]
        checksum = getattr(model, key, False)
        if not checksum:
            self._log.debug(
                "key {} on model {.filepath} not cached:computing checksum",
                key,
                model,
            )
            try:
                checksum = command_output(args).stdout
                setattr(model, key, checksum)
                model.store()
                self._log.debug(
                    "computed checksum for {.title} using {}", model, key
                )
            except subprocess.CalledProcessError as e:
                self._log.debug("failed to checksum {.filepath}: {}", model, e)
        else:
            self._log.debug(
                "key {} on item {.filepath} cached:not computing checksum",
                key,
                model,
            )
        return key, checksum

    def _group_by(
        self, objs: Sequence[AlbumOrItem], keys: Sequence[str], strict: bool
    ) -> dict[tuple[Any, ...], list[AlbumOrItem]]:
        """Return a dictionary with keys arbitrary concatenations of attributes
        and values lists of objects (Albums or Items) with those keys.

        If strict, all attributes must be defined for a duplicate match.
        """
        import collections

        counts = collections.defaultdict(list)
        for obj in objs:
            values = [getattr(obj, k, None) for k in keys]
            values = [v for v in values if v not in (None, "")]
            if strict and len(values) < len(keys):
                self._log.debug(
                    "some keys {} on item {.filepath} are null or empty: skipping",
                    keys,
                    obj,
                )
            elif not strict and not len(values):
                self._log.debug(
                    "all keys {} on item {.filepath} are null or empty: skipping",
                    keys,
                    obj,
                )
            else:
                key = tuple(values)
                counts[key].append(obj)

        return counts

    def _order(
        self,
        objs: Sequence[AlbumOrItem],
        tiebreak: dict[str, list[str]] | None = None,
    ) -> list[AlbumOrItem]:
        """Return the objects (Items or Albums) sorted by descending
        order of priority.

        If provided, the `tiebreak` dict indicates the field to use to
        prioritize the objects. Otherwise, Items are placed in order of
        "completeness" (objects with more non-null fields come first)
        and Albums are ordered by their track count.
        """
        kind = "items" if all(isinstance(o, Item) for o in objs) else "albums"

        sort = partial(sorted, reverse=True)
        if tiebreak and kind in tiebreak.keys():
            return sort(
                objs, key=lambda x: tuple(getattr(x, k) for k in tiebreak[kind])
            )
        if kind == "items":

            def truthy(v: object) -> bool:
                # Avoid a Unicode warning by avoiding comparison
                # between a bytes object and the empty Unicode
                # string ''.
                return v is not None and (
                    v != "" if isinstance(v, str) else True
                )

            fields = Item.all_keys()

            return sort(
                objs,
                key=lambda x: sum(1 for f in fields if truthy(getattr(x, f))),
            )
        return sort(objs, key=lambda x: len(x.items()))

    def _merge_items(self, objs: list[Item]) -> list[Item]:
        """Merge Item objs by copying missing fields from items in the tail to
        the head item.

        Return same number of items, with the head item modified.
        """
        fields = Item.all_keys()
        for f in fields:
            for o in objs[1:]:
                if getattr(objs[0], f, None) in (None, ""):
                    value = getattr(o, f, None)
                    if value:
                        self._log.debug(
                            "key {} on item {} is null "
                            "or empty: setting from item {.filepath}",
                            f,
                            displayable_path(objs[0].path),
                            o,
                        )
                        setattr(objs[0], f, value)
                        objs[0].store()
                        break
        return objs

    def _merge_albums(self, objs: list[Album]) -> list[Album]:
        """Merge Album objs by copying missing items from albums in the tail
        to the head album.

        Return same number of albums, with the head album modified."""
        ids = [i.mb_trackid for i in objs[0].items()]
        for o in objs[1:]:
            for i in o.items():
                if i.mb_trackid not in ids:
                    missing = Item.from_path(i.path)
                    missing.album_id = objs[0].id
                    missing.add(i._db)
                    self._log.debug(
                        "item {} missing from album {}:"
                        " merging from {.filepath} into {}",
                        missing,
                        objs[0],
                        o,
                        displayable_path(missing.destination()),
                    )
                    missing.move(operation=MoveOperation.COPY)
        return objs

    def _duplicates(
        self,
        objs: Sequence[AlbumOrItem],
        keys: Sequence[str],
        full: bool,
        strict: bool,
        tiebreak: dict[str, list[str]] | None,
        merge_func: Callable[[list[AlbumOrItem]], list[AlbumOrItem]] | None,
    ) -> Iterator[tuple[tuple[Any, ...], int, Sequence[AlbumOrItem]]]:
        """Generate triples of keys, duplicate counts, and constituent objects."""
        offset = 0 if full else 1
        for k, objs in self._group_by(objs, keys, strict).items():
            if len(objs) > 1:
                objs = self._order(objs, tiebreak)
                if merge_func:
                    objs = merge_func(objs)
                yield (k, len(objs) - offset, objs[offset:])
