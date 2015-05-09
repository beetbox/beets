# This file is part of beets.
# Copyright 2015, Heinz Wiesinger.
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

"""Synchronize information from music player libraries
"""
from abc import abstractmethod, ABCMeta
from beets import ui
from beets.plugins import BeetsPlugin
import inspect
import pkgutil
from importlib import import_module


METASYNC_MODULE = 'beetsplug.metasync'


class MetaSource(object):
    __metaclass__ = ABCMeta

    def __init__(self, config, log):
        self.item_types = {}
        self.config = config
        self._log = log

    @abstractmethod
    def sync_data(self, item):
        pass


def load_meta_sources():
    """ Returns a dictionary of all the MetaSources
    E.g., {'itunes': Itunes} with isinstance(Itunes, MetaSource) true
    """

    def is_meta_source_implementation(c):
        return inspect.isclass(c) and \
            not inspect.isabstract(c) and \
            issubclass(c, MetaSource)

    meta_sources = {}

    module_names = [name for _, name, _ in pkgutil.walk_packages(
        import_module(METASYNC_MODULE).__path__)]

    for module_name in module_names:
        module = import_module(METASYNC_MODULE + '.' + module_name)
        classes = inspect.getmembers(module, is_meta_source_implementation)

        for cls_name, _cls in classes:
            meta_sources[cls_name.lower()] = _cls

    return meta_sources


META_SOURCES = load_meta_sources()


def load_item_types():
    """ Returns a dictionary containing the item_types of all the MetaSources
    """
    item_types = {}
    for meta_source in META_SOURCES.values():
        item_types.update(meta_source.item_types)
    return item_types


class MetaSyncPlugin(BeetsPlugin):

    item_types = load_item_types()

    def __init__(self):
        super(MetaSyncPlugin, self).__init__()

    def commands(self):
        cmd = ui.Subcommand('metasync',
                            help='update metadata from music player libraries')
        cmd.parser.add_option('-p', '--pretend', action='store_true',
                              help='show all changes but do nothing')
        cmd.parser.add_option('-s', '--source', default=[],
                              action='append', dest='sources',
                              help='comma-separated list of sources to sync')
        cmd.parser.add_format_option()
        cmd.func = self.func
        return [cmd]

    def func(self, lib, opts, args):
        """Command handler for the metasync function.
        """
        pretend = opts.pretend
        query = ui.decargs(args)

        sources = []
        for source in opts.sources:
            sources.extend(source.split(','))

        sources = sources or self.config['source'].as_str_seq()

        meta_sources = {}

        # Instantiate the meta sources
        for player in sources:
            try:
                meta_sources[player] = \
                    META_SOURCES[player](self.config, self._log)
            except KeyError:
                self._log.error(u'Unknown metadata source \'{0}\''.format(
                    player))
            except ImportError as e:
                self._log.error(u'Failed to instantiate metadata source '
                                u'\'{0}\': {1}'.format(player, e))

        # Sync the items with all of the meta sources
        for item in lib.items(query):
            for meta_source in meta_sources.values():
                meta_source.sync_data(item)

            changed = ui.show_model_changes(item)

            if changed and not pretend:
                item.store()
