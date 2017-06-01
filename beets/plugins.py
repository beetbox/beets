# -*- coding: utf-8 -*-
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

"""Support for beets plugins."""

from __future__ import division, absolute_import, print_function

import inspect
import traceback
import re
from collections import defaultdict
from functools import wraps


import beets
from beets import logging
from beets import mediafile
import six

PLUGIN_NAMESPACE = 'beetsplug'

# Plugins using the Last.fm API can share the same API key.
LASTFM_KEY = '2dc3914abf35f0d9c92d97d8f8e42b43'

# Global logger.
log = logging.getLogger('beets')


class PluginConflictException(Exception):
    """Indicates that the services provided by one plugin conflict with
    those of another.

    For example two plugins may define different types for flexible fields.
    """


class PluginLogFilter(logging.Filter):
    """A logging filter that identifies the plugin that emitted a log
    message.
    """
    def __init__(self, plugin):
        self.prefix = u'{0}: '.format(plugin.name)

    def filter(self, record):
        if hasattr(record.msg, 'msg') and isinstance(record.msg.msg,
                                                     six.string_types):
            # A _LogMessage from our hacked-up Logging replacement.
            record.msg.msg = self.prefix + record.msg.msg
        elif isinstance(record.msg, six.string_types):
            record.msg = self.prefix + record.msg
        return True


# Managing the plugins themselves.

class BeetsPlugin(object):
    """The base class for all beets plugins. Plugins provide
    functionality by defining a subclass of BeetsPlugin and overriding
    the abstract methods defined here.
    """
    def __init__(self, name=None):
        """Perform one-time plugin setup.
        """
        self.name = name or self.__module__.split('.')[-1]
        self.config = beets.config[self.name]
        if not self.template_funcs:
            self.template_funcs = {}
        if not self.template_fields:
            self.template_fields = {}
        if not self.album_template_fields:
            self.album_template_fields = {}
        self.import_stages = []

        self._log = log.getChild(self.name)
        self._log.setLevel(logging.NOTSET)  # Use `beets` logger level.
        if not any(isinstance(f, PluginLogFilter) for f in self._log.filters):
            self._log.addFilter(PluginLogFilter(self))

    def commands(self):
        """Should return a list of beets.ui.Subcommand objects for
        commands that should be added to beets' CLI.
        """
        return ()

    def get_import_stages(self):
        """Return a list of functions that should be called as importer
        pipelines stages.

        The callables are wrapped versions of the functions in
        `self.import_stages`. Wrapping provides some bookkeeping for the
        plugin: specifically, the logging level is adjusted to WARNING.
        """
        return [self._set_log_level_and_params(logging.WARNING, import_stage)
                for import_stage in self.import_stages]

    def _set_log_level_and_params(self, base_log_level, func):
        """Wrap `func` to temporarily set this plugin's logger level to
        `base_log_level` + config options (and restore it to its previous
        value after the function returns). Also determines which params may not
        be sent for backwards-compatibility.
        """
        argspec = inspect.getargspec(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            assert self._log.level == logging.NOTSET
            verbosity = beets.config['verbose'].get(int)
            log_level = max(logging.DEBUG, base_log_level - 10 * verbosity)
            self._log.setLevel(log_level)
            try:
                try:
                    return func(*args, **kwargs)
                except TypeError as exc:
                    if exc.args[0].startswith(func.__name__):
                        # caused by 'func' and not stuff internal to 'func'
                        kwargs = dict((arg, val) for arg, val in kwargs.items()
                                      if arg in argspec.args)
                        return func(*args, **kwargs)
                    else:
                        raise
            finally:
                self._log.setLevel(logging.NOTSET)
        return wrapper

    def queries(self):
        """Should return a dict mapping prefixes to Query subclasses.
        """
        return {}

    def track_distance(self, item, info):
        """Should return a Distance object to be added to the
        distance for every track comparison.
        """
        return beets.autotag.hooks.Distance()

    def album_distance(self, items, album_info, mapping):
        """Should return a Distance object to be added to the
        distance for every album-level comparison.
        """
        return beets.autotag.hooks.Distance()

    def candidates(self, items, artist, album, va_likely):
        """Should return a sequence of AlbumInfo objects that match the
        album whose items are provided.
        """
        return ()

    def item_candidates(self, item, artist, title):
        """Should return a sequence of TrackInfo objects that match the
        item provided.
        """
        return ()

    def album_for_id(self, album_id):
        """Return an AlbumInfo object or None if no matching release was
        found.
        """
        return None

    def track_for_id(self, track_id):
        """Return a TrackInfo object or None if no matching release was
        found.
        """
        return None

    def add_media_field(self, name, descriptor):
        """Add a field that is synchronized between media files and items.

        When a media field is added ``item.write()`` will set the name
        property of the item's MediaFile to ``item[name]`` and save the
        changes. Similarly ``item.read()`` will set ``item[name]`` to
        the value of the name property of the media file.

        ``descriptor`` must be an instance of ``mediafile.MediaField``.
        """
        # Defer impor to prevent circular dependency
        from beets import library
        mediafile.MediaFile.add_field(name, descriptor)
        library.Item._media_fields.add(name)

    _raw_listeners = None
    listeners = None

    def register_listener(self, event, func):
        """Add a function as a listener for the specified event.
        """
        wrapped_func = self._set_log_level_and_params(logging.WARNING, func)

        cls = self.__class__
        if cls.listeners is None or cls._raw_listeners is None:
            cls._raw_listeners = defaultdict(list)
            cls.listeners = defaultdict(list)
        if func not in cls._raw_listeners[event]:
            cls._raw_listeners[event].append(func)
            cls.listeners[event].append(wrapped_func)

    template_funcs = None
    template_fields = None
    album_template_fields = None

    @classmethod
    def template_func(cls, name):
        """Decorator that registers a path template function. The
        function will be invoked as ``%name{}`` from path format
        strings.
        """
        def helper(func):
            if cls.template_funcs is None:
                cls.template_funcs = {}
            cls.template_funcs[name] = func
            return func
        return helper

    @classmethod
    def template_field(cls, name):
        """Decorator that registers a path template field computation.
        The value will be referenced as ``$name`` from path format
        strings. The function must accept a single parameter, the Item
        being formatted.
        """
        def helper(func):
            if cls.template_fields is None:
                cls.template_fields = {}
            cls.template_fields[name] = func
            return func
        return helper


_classes = set()


def load_plugins(names=()):
    """Imports the modules for a sequence of plugin names. Each name
    must be the name of a Python module under the "beetsplug" namespace
    package in sys.path; the module indicated should contain the
    BeetsPlugin subclasses desired.
    """
    for name in names:
        modname = '{0}.{1}'.format(PLUGIN_NAMESPACE, name)
        try:
            try:
                namespace = __import__(modname, None, None)
            except ImportError as exc:
                # Again, this is hacky:
                if exc.args[0].endswith(' ' + name):
                    log.warning(u'** plugin {0} not found', name)
                else:
                    raise
            else:
                for obj in getattr(namespace, name).__dict__.values():
                    if isinstance(obj, type) and issubclass(obj, BeetsPlugin) \
                            and obj != BeetsPlugin and obj not in _classes:
                        _classes.add(obj)

        except Exception:
            log.warning(
                u'** error loading plugin {}:\n{}',
                name,
                traceback.format_exc(),
            )


_instances = {}


def find_plugins():
    """Returns a list of BeetsPlugin subclass instances from all
    currently loaded beets plugins. Loads the default plugin set
    first.
    """
    load_plugins()
    plugins = []
    for cls in _classes:
        # Only instantiate each plugin class once.
        if cls not in _instances:
            _instances[cls] = cls()
        plugins.append(_instances[cls])
    return plugins


# Communication with plugins.

def commands():
    """Returns a list of Subcommand objects from all loaded plugins.
    """
    out = []
    for plugin in find_plugins():
        out += plugin.commands()
    return out


def queries():
    """Returns a dict mapping prefix strings to Query subclasses all loaded
    plugins.
    """
    out = {}
    for plugin in find_plugins():
        out.update(plugin.queries())
    return out


def types(model_cls):
    # Gives us `item_types` and `album_types`
    attr_name = '{0}_types'.format(model_cls.__name__.lower())
    types = {}
    for plugin in find_plugins():
        plugin_types = getattr(plugin, attr_name, {})
        for field in plugin_types:
            if field in types and plugin_types[field] != types[field]:
                raise PluginConflictException(
                    u'Plugin {0} defines flexible field {1} '
                    u'which has already been defined with '
                    u'another type.'.format(plugin.name, field)
                )
        types.update(plugin_types)
    return types


def track_distance(item, info):
    """Gets the track distance calculated by all loaded plugins.
    Returns a Distance object.
    """
    from beets.autotag.hooks import Distance
    dist = Distance()
    for plugin in find_plugins():
        dist.update(plugin.track_distance(item, info))
    return dist


def album_distance(items, album_info, mapping):
    """Returns the album distance calculated by plugins."""
    from beets.autotag.hooks import Distance
    dist = Distance()
    for plugin in find_plugins():
        dist.update(plugin.album_distance(items, album_info, mapping))
    return dist


def candidates(items, artist, album, va_likely):
    """Gets MusicBrainz candidates for an album from each plugin.
    """
    for plugin in find_plugins():
        for candidate in plugin.candidates(items, artist, album, va_likely):
            yield candidate


def item_candidates(item, artist, title):
    """Gets MusicBrainz candidates for an item from the plugins.
    """
    for plugin in find_plugins():
        for item_candidate in plugin.item_candidates(item, artist, title):
            yield item_candidate


def album_for_id(album_id):
    """Get AlbumInfo objects for a given ID string.
    """
    for plugin in find_plugins():
        album = plugin.album_for_id(album_id)
        if album:
            yield album


def track_for_id(track_id):
    """Get TrackInfo objects for a given ID string.
    """
    for plugin in find_plugins():
        track = plugin.track_for_id(track_id)
        if track:
            yield track


def template_funcs():
    """Get all the template functions declared by plugins as a
    dictionary.
    """
    funcs = {}
    for plugin in find_plugins():
        if plugin.template_funcs:
            funcs.update(plugin.template_funcs)
    return funcs


def import_stages():
    """Get a list of import stage functions defined by plugins."""
    stages = []
    for plugin in find_plugins():
        stages += plugin.get_import_stages()
    return stages


# New-style (lazy) plugin-provided fields.

def item_field_getters():
    """Get a dictionary mapping field names to unary functions that
    compute the field's value.
    """
    funcs = {}
    for plugin in find_plugins():
        if plugin.template_fields:
            funcs.update(plugin.template_fields)
    return funcs


def album_field_getters():
    """As above, for album fields.
    """
    funcs = {}
    for plugin in find_plugins():
        if plugin.album_template_fields:
            funcs.update(plugin.album_template_fields)
    return funcs


# Event dispatch.

def event_handlers():
    """Find all event handlers from plugins as a dictionary mapping
    event names to sequences of callables.
    """
    all_handlers = defaultdict(list)
    for plugin in find_plugins():
        if plugin.listeners:
            for event, handlers in plugin.listeners.items():
                all_handlers[event] += handlers
    return all_handlers


def send(event, **arguments):
    """Send an event to all assigned event listeners.

    `event` is the name of  the event to send, all other named arguments
    are passed along to the handlers.

    Return a list of non-None values returned from the handlers.
    """
    log.debug(u'Sending event: {0}', event)
    results = []
    for handler in event_handlers()[event]:
        result = handler(**arguments)
        if result is not None:
            results.append(result)
    return results


def feat_tokens(for_artist=True):
    """Return a regular expression that matches phrases like "featuring"
    that separate a main artist or a song title from secondary artists.
    The `for_artist` option determines whether the regex should be
    suitable for matching artist fields (the default) or title fields.
    """
    feat_words = ['ft', 'featuring', 'feat', 'feat.', 'ft.']
    if for_artist:
        feat_words += ['with', 'vs', 'and', 'con', '&']
    return '(?<=\s)(?:{0})(?=\s)'.format(
        '|'.join(re.escape(x) for x in feat_words)
    )


def sanitize_choices(choices, choices_all):
    """Clean up a stringlist configuration attribute: keep only choices
    elements present in choices_all, remove duplicate elements, expand '*'
    wildcard while keeping original stringlist order.
    """
    seen = set()
    others = [x for x in choices_all if x not in choices]
    res = []
    for s in choices:
        if s in list(choices_all) + ['*']:
            if not (s in seen or seen.add(s)):
                res.extend(list(others) if s == '*' else [s])
    return res


def notify_info_yielded(event):
    """Makes a generator send the event 'event' every time it yields.
    This decorator is supposed to decorate a generator, but any function
    returning an iterable should work.
    Each yielded value is passed to plugins using the 'info' parameter of
    'send'.
    """
    def decorator(generator):
        def decorated(*args, **kwargs):
            for v in generator(*args, **kwargs):
                send(event, info=v)
                yield v
        return decorated
    return decorator
