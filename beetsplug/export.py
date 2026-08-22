"""Exports data from beets"""

from __future__ import annotations

import codecs
import csv
import json
import os
import sys
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol, get_args
from xml.etree import ElementTree

import mediafile

from beets import ui
from beets.dbcore.types import BasePathType
from beets.library.fields import TYPE_BY_FIELD
from beets.plugins import BeetsPlugin
from beetsplug.info import library_data, tag_data

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from beets.library import Library

    from ._typing import JSONDict

Format = Literal["json", "jsonlines", "csv", "xml"]
VALID_FORMATS = get_args(Format)


class ExportCLIOpts(Protocol):
    library: bool | None
    album: bool
    append: bool
    included_keys: Sequence[str]
    output: str | None
    format: Format | None


class ExportEncoder(json.JSONEncoder):
    """Deals with dates because JSON doesn't have a standard"""

    def default(self, o: object) -> Any:
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)


class ExportPlugin(BeetsPlugin):
    default_format: Format

    def __init__(self) -> None:
        super().__init__()

        self.config.add(
            {
                "default_format": "json",
                "json": {
                    # JSON module formatting options.
                    "formatting": {
                        "ensure_ascii": False,
                        "indent": 4,
                        "separators": (",", ": "),
                        "sort_keys": True,
                    }
                },
                "jsonlines": {
                    # JSON Lines formatting options.
                    "formatting": {
                        "ensure_ascii": False,
                        "separators": (",", ": "),
                        "sort_keys": True,
                    }
                },
                "csv": {
                    # CSV module formatting options.
                    "formatting": {
                        # The delimiter used to separate columns.
                        "delimiter": ",",
                        # The dialect to use when formatting the file output.
                        "dialect": "excel",
                    }
                },
                "xml": {
                    # XML module formatting options.
                    "formatting": {}
                },
                # TODO: Use something like the edit plugin
                # 'item_fields': []
            }
        )
        self.default_format = self.config["default_format"].as_choice(
            VALID_FORMATS
        )

    def commands(self) -> list[ui.Subcommand]:
        cmd = ui.Subcommand("export", help="export data from beets")
        cmd.func = self.run
        cmd.parser.add_album_option()
        cmd.parser.add_option(
            "-l",
            "--library",
            action="store_true",
            help="show library fields instead of tags",
        )
        cmd.parser.add_option(
            "--append",
            action="store_true",
            default=False,
            help="if should append data to the file",
        )
        cmd.parser.add_option(
            "-i",
            "--include-keys",
            default=[],
            action="append",
            dest="included_keys",
            help="comma separated list of keys to show",
        )
        cmd.parser.add_option(
            "-o",
            "--output",
            help="path for the output file. If not given, will print the data",
        )
        cmd.parser.add_option(
            "-f",
            "--format",
            type="choice",
            choices=VALID_FORMATS,
            default=self.config["default_format"].get(),
            help="the output format: json|jsonlines|csv|xml",
        )
        return [cmd]

    def run(
        self, lib: Library, opts: ExportCLIOpts, args: Sequence[str]
    ) -> None:
        file_path = opts.output
        file_mode = "a" if opts.append else "w"
        file_format = opts.format or self.default_format
        format_options = self.config[file_format]["formatting"].get(dict)

        _format = (
            CSVFormat
            if file_format == "csv"
            else XMLFormat
            if file_format == "xml"
            else JsonFormat
        )
        export_format = _format(
            file_format=file_format, file_path=file_path, file_mode=file_mode
        )

        if opts.library or opts.album:
            data_collector = library_data
        else:
            data_collector = tag_data

        included_keys = []
        for keys in opts.included_keys:
            included_keys.extend(keys.split(","))

        byte_fields = [
            k for k, v in TYPE_BY_FIELD.items() if isinstance(v, BasePathType)
        ]

        def collect_data() -> Iterator[JSONDict]:
            for data_emitter in data_collector(lib, args, album=opts.album):
                try:
                    data, _ = data_emitter(included_keys or "*")
                except (mediafile.UnreadableFileError, OSError) as ex:
                    self._log.error("cannot read file: {}", ex)
                    continue
                else:
                    yield data

        def stringify_bytes(data: JSONDict) -> JSONDict:
            for field in byte_fields:
                if (value := data.get(field)) is not None:
                    data[field] = os.fsdecode(value)

            return data

        export_format.export(
            map(stringify_bytes, collect_data()), **format_options
        )


class ExportFormat:
    """The output format type"""

    def __init__(
        self,
        file_format: str,
        file_path: str | None,
        file_mode: str = "w",
        encoding: str = "utf-8",
    ) -> None:
        self.file_format = file_format
        self.path = file_path
        self.mode = file_mode
        self.encoding = encoding
        # creates a file object to write/append or sets to stdout
        self.out_stream = (
            codecs.open(self.path, self.mode, self.encoding)
            if self.path
            else sys.stdout
        )

    def export(self, data_iter: Iterable[JSONDict], **kwargs) -> None:
        raise NotImplementedError()


class JsonFormat(ExportFormat):
    """Saves in a json file"""

    def _print_json(self, data: Any, **kwargs) -> None:
        json.dump(data, self.out_stream, cls=ExportEncoder, **kwargs)
        self.out_stream.write("\n")

    def export(self, data_iter: Iterable[JSONDict], **kwargs) -> None:
        if self.file_format == "json":
            self._print_json(list(data_iter), **kwargs)
        else:
            for item in data_iter:
                self._print_json(item, **kwargs)


class CSVFormat(ExportFormat):
    """Saves in a csv file"""

    def export(self, data_iter: Iterable[JSONDict], **kwargs) -> None:
        data = list(data_iter)
        header = list(data[0].keys()) if data else []
        writer = csv.DictWriter(self.out_stream, fieldnames=header, **kwargs)
        writer.writeheader()
        writer.writerows(data)


class XMLFormat(ExportFormat):
    """Saves in a xml file"""

    def export(self, data_iter: Iterable[JSONDict], **kwargs) -> None:
        # Creates the XML file structure.
        data = list(data_iter)
        library = ElementTree.Element("library")
        tracks = ElementTree.SubElement(library, "tracks")
        if data and isinstance(data[0], dict):
            for index, item in enumerate(data):
                track = ElementTree.SubElement(tracks, "track")
                for key, value in item.items():
                    track_details = ElementTree.SubElement(track, key)
                    track_details.text = value
        # Depending on the version of python the encoding needs to change
        try:
            string = ElementTree.tostring(library, encoding="unicode", **kwargs)
        except LookupError:
            string = ElementTree.tostring(library, encoding="utf-8", **kwargs)

        self.out_stream.write(string)
