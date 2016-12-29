# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2015-2016, Ohm Patel.
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

"""Fetch various AcousticBrainz metadata using MBID.
"""
from __future__ import division, absolute_import, print_function

import requests

from collections import defaultdict
from beets import plugins, ui

ACOUSTIC_BASE = "https://acousticbrainz.org/"
LEVELS = ["/low-level", "/high-level"]
ABSCHEME = {
    'highlevel': {
        'danceability': {
            'all': {
                'danceable': 'danceable'
            }
        },
        'gender': {
            'value': 'gender'
        },
        'genre_rosamerica': {
            'value': 'genre_rosamerica'
        },
        'mood_acoustic': {
            'all': {
                'acoustic': 'mood_acoustic'
            }
        },
        'mood_aggressive': {
            'all': {
                'aggressive': 'mood_aggressive'
            }
        },
        'mood_electronic': {
            'all': {
                'electronic': 'mood_electronic'
            }
        },
        'mood_happy': {
            'all': {
                'happy': 'mood_happy'
            }
        },
        'mood_party': {
            'all': {
                'party': 'mood_party'
            }
        },
        'mood_relaxed': {
            'all': {
                'relaxed': 'mood_relaxed'
            }
        },
        'mood_sad': {
            'all': {
                'sad': 'mood_sad'
            }
        },
        'ismir04_rhythm': {
            'value': 'rhythm'
        },
        'tonal_atonal': {
            'all': {
                'tonal': 'tonal'
            }
        },
        'voice_instrumental': {
            'value': 'voice_instrumental'
        },
    },
    'lowlevel': {
        'average_loudness': 'average_loudness'
    },
    'rhythm': {
        'bpm': 'bpm'
    },
    'tonal': {
        'chords_changes_rate': 'chords_changes_rate',
        'chords_key': 'chords_key',
        'chords_number_rate': 'chords_number_rate',
        'chords_scale': 'chords_scale',
        'key_key': ('initial_key', 0),
        'key_scale': ('initial_key', 1),
        'key_strength': 'key_strength'

    }
}


class AcousticPlugin(plugins.BeetsPlugin):
    def __init__(self):
        super(AcousticPlugin, self).__init__()

        self.config.add({
            'auto': True,
            'force': False,
        })

        if self.config['auto']:
            self.register_listener('import_task_files',
                                   self.import_task_files)

    def commands(self):
        cmd = ui.Subcommand('acousticbrainz',
                            help=u"fetch metadata from AcousticBrainz")
        cmd.parser.add_option(
            u'-f', u'--force', dest='force_refetch',
            action='store_true', default=False,
            help=u're-download data when already present'
        )

        def func(lib, opts, args):
            items = lib.items(ui.decargs(args))
            self._fetch_info(items, ui.should_write(),
                             opts.force_refetch or self.config['force'])

        cmd.func = func
        return [cmd]

    def import_task_files(self, session, task):
        """Function is called upon beet import.
        """
        self._fetch_info(task.imported_items(), False, True)

    def _get_data(self, mbid):
        data = {}
        for url in _generate_urls(mbid):
            self._log.debug(u'fetching URL: {}', url)

            try:
                res = requests.get(url)
            except requests.RequestException as exc:
                self._log.info(u'request error: {}', exc)
                return {}

            if res.status_code == 404:
                self._log.info(u'recording ID {} not found', mbid)
                return {}

            try:
                data.update(res.json())
            except ValueError:
                self._log.debug(u'Invalid Response: {}', res.text)
                return {}

        return data

    def _fetch_info(self, items, write, force):
        """Fetch additional information from AcousticBrainz for the `item`s.
        """
        for item in items:
            # If we're not forcing re-downloading for all tracks, check
            # whether the data is already present. We use one
            # representative field name to check for previously fetched
            # data.
            if not force:
                mood_str = item.get('mood_acoustic', u'')
                if mood_str:
                    self._log.info(u'data already present for: {}', item)
                    continue

            # We can only fetch data for tracks with MBIDs.
            if not item.mb_trackid:
                continue

            self._log.info(u'getting data for: {}', item)
            data = self._get_data(item.mb_trackid)
            if data:
                for attr, val in self._map_data_to_scheme(data, ABSCHEME):
                    self._log.debug(u'attribute {} of {} set to {}',
                                    attr,
                                    item,
                                    val)
                    setattr(item, attr, val)
                item.store()
                if write:
                    item.try_write()

    def _map_data_to_scheme(self, data, scheme):
        """Given `data` as a structure of nested dictionaries, and `scheme` as a
        structure of nested dictionaries , `yield` tuples `(attr, val)` where
        `attr` and `val` are corresponding leaf nodes in `scheme` and `data`.

        As its name indicates, `scheme` defines how the data is structured,
        so this function tries to find leaf nodes in `data` that correspond
        to the leafs nodes of `scheme`, and not the other way around.
        Leaf nodes of `data` that do not exist in the `scheme` do not matter.
        If a leaf node of `scheme` is not present in `data`,
        no value is yielded for that attribute and a simple warning is issued.

        Finally, to account for attributes of which the value is split between
        several leaf nodes in `data`, leaf nodes of `scheme` can be tuples
        `(attr, order)` where `attr` is the attribute to which the leaf node
        belongs, and `order` is the place at which it should appear in the
        value. The different `value`s belonging to the same `attr` are simply
        joined with `' '`. This is hardcoded and not very flexible, but it gets
        the job done.

        For example:

        >>> scheme = {
            'key1': 'attribute',
            'key group': {
                'subkey1': 'subattribute',
                'subkey2': ('composite attribute', 0)
            },
            'key2': ('composite attribute', 1)
        }
        >>> data = {
            'key1': 'value',
            'key group': {
                'subkey1': 'subvalue',
                'subkey2': 'part 1 of composite attr'
            },
            'key2': 'part 2'
        }
        >>> print(list(_map_data_to_scheme(data, scheme)))
        [('subattribute', 'subvalue'),
         ('attribute', 'value'),
         ('composite attribute', 'part 1 of composite attr part 2')]
        """
        # First, we traverse `scheme` and `data`, `yield`ing all the non
        # composites attributes straight away and populating the dictionary
        # `composites` with the composite attributes.

        # When we are finished traversing `scheme`, `composites` should
        # map each composite attribute to an ordered list of the values
        # belonging to the attribute, for example:
        # `composites = {'initial_key': ['B', 'minor']}`.

        # The recursive traversal.
        composites = defaultdict(list)
        for attr, val in self._data_to_scheme_child(data,
                                                    scheme,
                                                    composites):
            yield attr, val

        # When composites has been populated, yield the composite attributes
        # by joining their parts.
        for composite_attr, value_parts in composites.items():
            yield composite_attr, ' '.join(value_parts)

    def _data_to_scheme_child(self, subdata, subscheme, composites):
        """The recursive business logic of :meth:`_map_data_to_scheme`:
        Traverse two structures of nested dictionaries in parallel and `yield`
        tuples of corresponding leaf nodes.

        If a leaf node belongs to a composite attribute (is a `tuple`),
        populate `composites` rather than yielding straight away.
        All the child functions for a single traversal share the same
        `composites` instance, which is passed along.
        """
        for k, v in subscheme.items():
            if k in subdata:
                if type(v) == dict:
                    for attr, val in self._data_to_scheme_child(subdata[k],
                                                                v,
                                                                composites):
                        yield attr, val
                elif type(v) == tuple:
                    composite_attribute, part_number = v
                    attribute_parts = composites[composite_attribute]
                    # Parts are not guaranteed to be inserted in order
                    while len(attribute_parts) <= part_number:
                        attribute_parts.append('')
                    attribute_parts[part_number] = subdata[k]
                else:
                    yield v, subdata[k]
            else:
                self._log.warning(u'Acousticbrainz did not provide info'
                                  u'about {}', k)
                self._log.debug(u'Data {} could not be mapped to scheme {} '
                                u'because key {} was not found', subdata, v, k)


def _generate_urls(mbid):
    """Generates AcousticBrainz end point urls for given `mbid`.
    """
    for level in LEVELS:
        yield ACOUSTIC_BASE + mbid + level
