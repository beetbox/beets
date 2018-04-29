# -*- coding: utf-8 -*-
# This file is part of beets.
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

"""Exports data from beets
"""

from __future__ import division, absolute_import, print_function

import sys
import json
import codecs

from datetime import datetime, date
from beets.plugins import BeetsPlugin
from beets import ui
from beets import mediafile
from beetsplug.info import make_key_filter, library_data, tag_data


class ExportEncoder(json.JSONEncoder):
    """Deals with dates because JSON doesn't have a standard"""
    def default(self, o):
        if isinstance(o, datetime) or isinstance(o, date):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)


class ExportPlugin(BeetsPlugin):

    def __init__(self):
        super(ExportPlugin, self).__init__()

        self.config.add({
            'default_format': 'json',
            'json': {
                # json module formatting options
                'formatting': {
                    'ensure_ascii': False,
                    'indent': 4,
                    'separators': (',', ': '),
                    'sort_keys': True
                }
            },
            # TODO: Use something like the edit plugin
            # 'item_fields': []
        })

    def commands(self):
        # TODO: Add option to use albums

        cmd = ui.Subcommand('export', help=u'export data from beets')
        cmd.func = self.run
        cmd.parser.add_option(
            u'-l', u'--library', action='store_true',
            help=u'show library fields instead of tags',
        )
        cmd.parser.add_option(
            u'--append', action='store_true', default=False,
            help=u'if should append data to the file',
        )
        cmd.parser.add_option(
            u'-i', u'--include-keys', default=[],
            action='append', dest='included_keys',
            help=u'comma separated list of keys to show',
        )
        cmd.parser.add_option(
            u'-o', u'--output',
            help=u'path for the output file. If not given, will print the data'
        )
        return [cmd]

    def run(self, lib, opts, args):

        file_path = opts.output
        file_format = self.config['default_format'].get(str)
        file_mode = 'a' if opts.append else 'w'
        format_options = self.config[file_format]['formatting'].get(dict)

        export_format = ExportFormat.factory(
            file_format, **{
                'file_path': file_path,
                'file_mode': file_mode
            }
        )

        items = []
        data_collector = library_data if opts.library else tag_data

        included_keys = []
        for keys in opts.included_keys:
            included_keys.extend(keys.split(','))
        key_filter = make_key_filter(included_keys)

        for data_emitter in data_collector(lib, ui.decargs(args)):
            try:
                data, item = data_emitter()
            except (mediafile.UnreadableFileError, IOError) as ex:
                self._log.error(u'cannot read file: {0}', ex)
                continue

            data = key_filter(data)
            items += [data]

        export_format.export(items, **format_options)


class ExportFormat(object):
    """The output format type"""

    @classmethod
    def factory(cls, type, **kwargs):
        if type == "json":
            if kwargs['file_path']:
                return JsonFileFormat(**kwargs)
            else:
                return JsonPrintFormat()
        raise NotImplementedError()

    def export(self, data, **kwargs):
        raise NotImplementedError()


class JsonPrintFormat(ExportFormat):
    """Outputs to the console"""

    def export(self, data, **kwargs):
        json.dump(data, sys.stdout, cls=ExportEncoder, **kwargs)


class JsonFileFormat(ExportFormat):
    """Saves in a json file"""

    def __init__(self, file_path, file_mode=u'w', encoding=u'utf-8'):
        self.path = file_path
        self.mode = file_mode
        self.encoding = encoding

    def export(self, data, **kwargs):
        with codecs.open(self.path, self.mode, self.encoding) as f:
            json.dump(data, f, cls=ExportEncoder, **kwargs)
