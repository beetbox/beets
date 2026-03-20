# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

"""Shows file metadata."""

import os

import mediafile

from beets import ui
from beets.library import Item
from beets.plugins import BeetsPlugin
from beets.util import displayable_path, normpath, syspath

# Mapping from beets field names to URL templates.
FIELD_LINK_TEMPLATES: dict[str, str] = {
    "mb_trackid": "https://musicbrainz.org/recording/{value}",
    "mb_albumid": "https://musicbrainz.org/release/{value}",
    "mb_artistid": "https://musicbrainz.org/artist/{value}",
    "mb_albumartistid": "https://musicbrainz.org/artist/{value}",
    "mb_releasetrackid": "https://musicbrainz.org/track/{value}",
    "mb_releasegroupid": "https://musicbrainz.org/release-group/{value}",
    "mb_workid": "https://musicbrainz.org/work/{value}",
    "discogs_albumid": "https://www.discogs.com/release/{value}",
    "discogs_artistid": "https://www.discogs.com/artist/{value}",
    "discogs_labelid": "https://www.discogs.com/label/{value}",
}


def tag_data(lib, args, album=False):
    query = []
    for arg in args:
        path = normpath(arg)
        if os.path.isfile(syspath(path)):
            yield tag_data_emitter(path)
        else:
            query.append(arg)

    if query:
        for item in lib.items(query):
            yield tag_data_emitter(item.path)


def tag_fields():
    fields = set(mediafile.MediaFile.readable_fields())
    fields.add("art")
    return fields


def tag_data_emitter(path):
    def emitter(included_keys):
        if included_keys == "*":
            fields = tag_fields()
        else:
            fields = included_keys
        if "images" in fields:
            # We can't serialize the image data.
            fields.remove("images")
        mf = mediafile.MediaFile(syspath(path))
        tags = {}
        for field in fields:
            if field == "art":
                tags[field] = mf.art is not None
            else:
                tags[field] = getattr(mf, field, None)

        # create a temporary Item to take advantage of __format__
        item = Item.from_path(syspath(path))

        return tags, item

    return emitter


def library_data(lib, args, album=False):
    for item in lib.albums(args) if album else lib.items(args):
        yield library_data_emitter(item)


def library_data_emitter(item):
    def emitter(included_keys):
        data = dict(item.formatted(included_keys=included_keys))

        return data, item

    return emitter


def update_summary(summary, tags):
    for key, value in tags.items():
        if key not in summary:
            summary[key] = value
        elif summary[key] != value:
            summary[key] = "[various]"
    return summary


def print_data(data, item=None, fmt=None, links=False):
    """Print, with optional formatting, the fields of a single element.

    If no format string `fmt` is passed, the entries on `data` are printed one
    in each line, with the format 'field: value'. If `fmt` is not `None`, the
    `item` is printed according to `fmt`, using the `Item.__format__`
    machinery.

    When `links == True`, external ID fields will be rendered as clickable
    terminal hyperlinks using OSC 8 escape sequences.
    """
    if fmt:
        # use fmt specified by the user
        ui.print_(format(item, fmt))
        return

    path = displayable_path(item.path) if item else None
    formatted = {}
    for key, value in data.items():
        if isinstance(value, list):
            formatted[key] = "; ".join(value)
        elif value is not None:
            if links and key in FIELD_LINK_TEMPLATES:
                value_str = str(value)
                url = FIELD_LINK_TEMPLATES[key].format(value=value_str)
                value = ui.terminal_link(url, value_str)
            formatted[key] = value

    if len(formatted) == 0:
        return

    maxwidth = max(len(key) for key in formatted)

    if path:
        ui.print_(displayable_path(path))

    for field in sorted(formatted):
        value = formatted[field]
        if isinstance(value, list):
            value = "; ".join(value)
        ui.print_(f"{field:>{maxwidth}}: {value}")


def print_data_keys(data, item=None):
    """Print only the keys (field names) for an item."""
    path = displayable_path(item.path) if item else None
    formatted = []
    for key, value in data.items():
        formatted.append(key)

    if len(formatted) == 0:
        return

    if path:
        ui.print_(displayable_path(path))

    for field in sorted(formatted):
        ui.print_(f"    {field}")


class InfoPlugin(BeetsPlugin):
    def commands(self):
        cmd = ui.Subcommand("info", help="show file metadata")
        cmd.func = self.run
        cmd.parser.add_option(
            "-l",
            "--library",
            action="store_true",
            help="show library fields instead of tags",
        )
        cmd.parser.add_option(
            "-a",
            "--album",
            action="store_true",
            help='show album fields instead of tracks (implies "--library")',
        )
        cmd.parser.add_option(
            "-s",
            "--summarize",
            action="store_true",
            help="summarize the tags of all files",
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
            "-k",
            "--keys-only",
            action="store_true",
            help="show only the keys",
        )
        cmd.parser.add_option(
            "--links",
            action="store_true",
            help="make ID fields (MusicBrainz, Discogs) clickable terminal hyperlinks",
        )
        cmd.parser.add_format_option(target="item")
        return [cmd]

    def run(self, lib, opts, args):
        """Print tag info or library data for each file referenced by args.

        Main entry point for the `beet info ARGS...` command.

        If an argument is a path pointing to an existing file, then the tags
        of that file are printed. All other arguments are considered
        queries, and for each item matching all those queries the tags from
        the file are printed.

        If `opts.summarize` is true, the function merges all tags into one
        dictionary and only prints that. If two files have different values
        for the same tag, the value is set to '[various]'
        """
        if opts.library or opts.album:
            data_collector = library_data
        else:
            data_collector = tag_data

        included_keys = []
        for keys in opts.included_keys:
            included_keys.extend(keys.split(","))
        # Drop path even if user provides it multiple times
        included_keys = [k for k in included_keys if k != "path"]

        first = True
        summary = {}
        for data_emitter in data_collector(
            lib,
            args,
            album=opts.album,
        ):
            try:
                data, item = data_emitter(included_keys or "*")
            except (mediafile.UnreadableFileError, OSError) as ex:
                self._log.error("cannot read file: {}", ex)
                continue

            if opts.summarize:
                update_summary(summary, data)
            else:
                if not first:
                    ui.print_()
                if opts.keys_only:
                    print_data_keys(data, item)
                else:
                    fmt = [opts.format][0] if opts.format else None
                    print_data(data, item, fmt, links=opts.links)
                first = False

        if opts.summarize:
            print_data(summary, links=opts.links)
