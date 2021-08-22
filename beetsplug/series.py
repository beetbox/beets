# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2019, Guilherme Danno.
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
"""Update series tags using MusicBrainz."""
from typing import Callable
from beets.plugins import BeetsPlugin
from beets import ui, util
from beets.autotag import mb
from beets.autotag.mb import musicbrainzngs
from collections import defaultdict, namedtuple

from dataclasses import dataclass
from itertools import groupby

from six.moves.urllib.parse import urljoin

ORDER_ATTR_ID = 'a59c5830-5ec7-38fe-9a21-c7ea54f6650a'

@dataclass
class SeriesType:
    name: str
    relation: str
    relation_list: str
    get_field: Callable


TYPES = [
    SeriesType(
        name='Release series',
        relation='release-rels',
        relation_list='release-relation-list',
        get_field=lambda a: a.mb_albumid
    ),
    SeriesType(
        name='Release group series',
        relation='release-group-rels',
        relation_list='release_group-relation-list',
        get_field=lambda a: a.mb_releasegroupid
    ),
]

SERIES_RELS = [t.relation for t in TYPES]


def apply_item_changes(lib, item, move, pretend, write):
    """Store, move and write the item according to the arguments.
    """
    if not pretend:
        item.try_sync(write, move)


def get_series_type(name):
    return next((t for t in TYPES if t.name == name), None)


def get_attribute(item, attr):
    try:
        return [x['value'] for x in item['attributes']
                if x['type-id'] == attr][0]
    except KeyError:
        return None


def group_by_series_type(items, key='type'):
    supported_series = [t.name for t in TYPES]
    keyfunc = lambda x: x[key]

    for k, item in groupby(sorted(items, key=keyfunc), keyfunc):
        if k in supported_series:
            yield (k, item)


def print_ui(query, data):
    available_items = {}
    choice_number = 0
    for series_type, valid_series in group_by_series_type(data):
        series_text = ui.colorize('text_highlight_minor', series_type)
        ui.print_(f"\n{series_text}:\n")

        for series in valid_series:
            choice_number += 1
            available_items[choice_number] = series['id']

            try:
                name = ui.colordiff(query, series['name'])[1]
                disambiguation = ui.colorize(
                    'text_highlight_minor',
                    series['disambiguation']
                )
                text = f"{name} ({disambiguation})"
            except KeyError:
                text = ui.colordiff(query, series['name'])[1]

            url = urljoin(mb.BASE_URL, 'mbid/' + series['id'])
            ui.print_(f"  {choice_number}. {text}")
            ui.print_(f"  {url}")
            ui.print_('')

    return available_items

class SeriesProvider:

    page_size: int

    def __init__(self, page_size = 10):
        self.page_size = page_size

    def _build_series(self, series):
        data = {
            'id': series['series']['id'],
            'name': series['series']['name'],
            'type': get_series_type(series['series']['type']),
            'items': defaultdict(dict),
        }

        for item in series['series'][data['type'].relation_list]:
            data['items'][item['target']] = {
                'order': get_attribute(item, ORDER_ATTR_ID),
                'name': data['name'],
                'id': data['id'],
            }

        return data

    def get_by_id(self, series_id):
        try:
            series = musicbrainzngs.get_series_by_id(series_id, SERIES_RELS)
            return self._build_series(series)
        except Exception:
            return

    def search(self, query):
        offset = 0
        while True:
            result = musicbrainzngs.search_series(
                query,
                limit=self.page_size,
                offset=offset
            )

            ui.print_(f"Found {result['series-count']} results for '{query}'")
            if result['series-count'] == 0:
                return

            available_items = print_ui(query, result['series-list'])
            if len(available_items) == 0:
                types = ' or '.join([f"'{t.name}'" for t in TYPES])
                ui.print_(f"No series with type {types}")
                return


            choices = []
            if offset > 0:
                choices += ['Previous']
            if offset < result['series-count']:
                # We filter some of the results client-side,
                # so we have a bug that a page can return 0 items
                choices += ['Next']

            response = ui.input_options(
                choices,
                numrange=(1, len(available_items)),
            )

            if response == 'n':
                offset = min(offset + self.page_size, result['series-count'])
                continue
            if response == 'p':
                offset = max(0, offset - self.page_size)
                continue

            return available_items[response]



class MbSeriesPlugin(BeetsPlugin):

    # Mapping between internal names and musicbrainz attributes
    mapping = {
        'id': 'id',
        'name': 'name',
        'volume': 'order',
    }

    def __init__(self):
        super(MbSeriesPlugin, self).__init__()

        self.config.add({
            'items_per_page': 10,
            'fields': {
                'id': {
                    'field_name': 'mb_seriesid',
                    'write': True,
                },
                'name': {
                    'field_name': 'series',
                    'write': True,
                },
                'volume': {
                    'field_name': 'volume',
                    'write': True,
                },
            }
        })

    def commands(self):
        def func(lib, opts, args):
            """
            Command handler for the series function.
            """
            move = ui.should_move(opts.move)
            pretend = opts.pretend
            write = ui.should_write(opts.write)
            query = ui.decargs(args)
            mb_query = opts.mb_query
            series_id = mb._parse_id(opts.id or '')
            series = SeriesProvider(page_size=self.config['items_per_page'])

            if series_id:
                self._log.info(u'Updating series {0}'.format(series_id))
                self.update_albums(lib, query, series_id, move, pretend, write)
            elif mb_query:
                series_id = series.search(mb_query)
                self.update_albums(lib, query, series_id, move, pretend, write)
            else:
                self.update_all_albums(lib, move, pretend, write)

        cmd = ui.Subcommand('series', help=u'Fetch series from MusicBrainz')
        cmd.parser.add_option(
            u'-S', u'--id', action='store',
            help=u'query MusicBrainz series with this id')
        cmd.parser.add_option(
            u'-q', u'--mb-query', action='store',
            help=u'query MusicBrainz series with this query')
        cmd.parser.add_option(
            u'-p', u'--pretend', action='store_true',
            help=u'show all changes but do nothing')
        cmd.parser.add_option(
            u'-m', u'--move', action='store_true', dest='move',
            help=u"move files in the library directory")
        cmd.parser.add_option(
            u'-M', u'--nomove', action='store_false', dest='move',
            help=u"don't move files in library")
        cmd.parser.add_option(
            u'-w', u'--write', action='store_true', default=None,
            help=u"write new metadata to files' tags"
        )
        cmd.parser.add_option(
            u'-W', u'--nowrite', action='store_false',
            default=None, dest='write',
            help=u"don't write updated metadata to files")
        cmd.func = func
        return [cmd]

    def is_mb_release(self, a):
        return a.mb_albumid and mb._parse_id(a.mb_albumid)

    def update_all_albums(self, lib, move, pretend, write):
        mb_seriesid = self.config['fields']['id']['field_name'].as_str()
        series_ids = set((getattr(a, mb_seriesid) for a in lib.albums(f'{mb_seriesid}::.')))

        self._log.info(f'updating {len(series_ids)} series')
        for _id in series_ids:
            self.update_albums(lib, f'{mb_seriesid}:{_id}', _id, move, pretend, write)

    def update_albums(self, lib, query: str, series_id: str, move, pretend, write):
        """Retrieve and apply info from the autotagger for albums matched by
        query and their items.
        """
        provider = SeriesProvider()
        series = provider.get_by_id(series_id)

        if not series:
            return

        fields = []
        for field, external_field in self.mapping.items():
            if self.config['fields'][field]['write']:
                self.config['fields'][field]['attr'] = external_field
                fields.append(self.config['fields'][field])

        for a in [a for a in lib.albums(query) if self.is_mb_release(a)]:
            mbid = series['type'].get_field(a)
            if not series['items'][mbid]:
                continue

            item = series['items'][mbid]

            for f in fields:
                if item[f['attr'].get()]:
                    a[f['field_name'].get()] = item[f['attr'].get()]

            ui.show_model_changes(a)
            apply_item_changes(lib, a, move, pretend, write)
