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
import codecs
import json
import csv
import xml.etree.ElementTree as ET

from datetime import datetime, date
from beets.plugins import BeetsPlugin
from beets import ui
import mediafile
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
            'csv': {
                # csv module formatting options
                'formatting': {
                    'ensure_ascii': False,
                    'indent': 0,
                    'separators': (','),
                    'sort_keys': True
                }
            },
            'xml': {
                # xml module formatting options
                'formatting': {
                    'ensure_ascii': False,
                    'indent': 4,
                    'separators': (','),
                    'sort_keys': True
                }
            }
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
        cmd.parser.add_option(
            u'-f', u'--format', default='json',
            help=u'specify the format of the exported data. Your options are json (deafult), csv, and xml'
        )
        return [cmd]

    def run(self, lib, opts, args):

        file_path = opts.output
        file_mode = 'a' if opts.append else 'w'
        file_format = opts.format
        format_options = self.config[file_format]['formatting'].get(dict)

        export_format = ExportFormat.factory(
            file_type=file_format, 
            **{
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
    def __init__(self, file_path, file_mode=u'w', encoding=u'utf-8'):
        self.path = file_path
        self.mode = file_mode
        self.encoding = encoding

    @classmethod
    def factory(cls, file_type, **kwargs):
        if file_type == "json":
            return JsonFormat(**kwargs)
        elif file_type == "csv":
            return CSVFormat(**kwargs)
        elif file_type == "xml":
            return XMLFormat(**kwargs)
        else:
            raise NotImplementedError()

    def export(self, data, **kwargs):
        raise NotImplementedError()


class JsonFormat(ExportFormat):
    """Saves in a json file"""
    def __init__(self, file_path, file_mode=u'w', encoding=u'utf-8'):
        super(JsonFormat, self).__init__(file_path, file_mode, encoding)
        self.export = self.export_to_file if self.path else self.export_to_terminal

    def export_to_terminal(self, data, **kwargs):
        json.dump(data, sys.stdout, cls=ExportEncoder, **kwargs)

    def export_to_file(self, data, **kwargs):
        with codecs.open(self.path, self.mode, self.encoding) as f:
            json.dump(data, f, cls=ExportEncoder, **kwargs)


class CSVFormat(ExportFormat):
    """Saves in a csv file"""
    def __init__(self, file_path, file_mode=u'w', encoding=u'utf-8'):
        super(CSVFormat, self).__init__(file_path, file_mode, encoding)
        self.header = []

    def export(self, data, **kwargs):
        if data and type(data) is list and len(data) > 0:
            self.header = list(data[0].keys())
        if self.path:
            self.export_to_file(data, **kwargs)
        else:
            self.export_to_terminal(data, **kwargs)

    def export_to_terminal(self, data, **kwargs):
        writer = csv.DictWriter(sys.stdout, fieldnames=self.header)
        writer.writeheader()
        writer.writerows(data)

    def export_to_file(self, data, **kwargs):
        with codecs.open(self.path, self.mode, self.encoding) as f:
            writer = csv.DictWriter(f, fieldnames=self.header)
            writer.writeheader()
            writer.writerows(data)


class XMLFormat(ExportFormat):
    """Saves in a xml file"""
    def __init__(self, file_path, file_mode=u'w', encoding=u'utf-8'):
        super(XMLFormat, self).__init__(file_path, file_mode, encoding)

    def export(self, data, **kwargs):
        # create the file structure
        library = ET.Element('library')
        tracks_key = ET.SubElement(library, 'key')
        tracks_key.text = "Tracks"
        tracks_dict = ET.SubElement(library, 'dict')
        if data and type(data) is list \
        and len(data) > 0 and type(data[0]) is dict:
            index = 1
            for item in data:
                track_key = ET.SubElement(tracks_dict, 'key')
                track_key.text = str(index)
                track_dict = ET.SubElement(tracks_dict, 'dict')
                track_details = ET.SubElement(track_dict, 'Track ID')
                track_details.text = str(index)
                index += 1
                for key, value in item.items():
                    track_details = ET.SubElement(track_dict, key)
                    track_details.text = value
        data = str(ET.tostring(library, encoding=self.encoding))
        #data = ET.dump(library)
        if self.path:
            self.export_to_file(data, **kwargs)
        else:
            self.export_to_terminal(data, **kwargs)
    
    def export_to_terminal(self, data, **kwargs):
        print(data)

    def export_to_file(self, data, **kwargs):
        with codecs.open(self.path, self.mode, self.encoding) as f:
            f.write(data)