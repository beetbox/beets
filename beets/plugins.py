# This file is part of beets.
# Copyright 2013, Adrian Sampson.
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

import logging
import traceback
from collections import defaultdict

import beets
from beets import mediafile

PLUGIN_NAMESPACE = 'beetsplug'

# Plugins using the Last.fm API can share the same API key.
LASTFM_KEY = '2dc3914abf35f0d9c92d97d8f8e42b43'

# Global logger.
log = logging.getLogger('beets')


# Managing the plugins themselves.

class BeetsPlugin(object):
    """The base class for all beets plugins. Plugins provide
    functionality by defining a subclass of BeetsPlugin and overriding
    the abstract methods defined here.
    """
    def __init__(self, name=None):
        """Perform one-time plugin setup.
        """
        _add_media_fields(self.item_fields())
        self.import_stages = []
        self.name = name or self.__module__.split('.')[-1]
        self.config = beets.config[self.name]
        if not self.template_funcs:
            self.template_funcs = {}
        if not self.template_fields:
            self.template_fields = {}

    def commands(self):
        """Should return a list of beets.ui.Subcommand objects for
        commands that should be added to beets' CLI.
        """
        return ()
    
    def queries(self):
        """Should return a dict of {prefix : beets.library.PluginQuery}"""
        return {}

    def track_distance(self, item, info):
        """Should return a (distance, distance_max) pair to be added
        to the distance value for every track comparison.
        """
        return 0.0, 0.0

    def album_distance(self, items, album_info, mapping):
        """Should return a (distance, distance_max) pair to be added
        to the distance value for every album-level comparison.
        """
        return 0.0, 0.0

    def candidates(self, items):
        """Should return a sequence of AlbumInfo objects that match the
        album whose items are provided.
        """
        return ()

    def item_candidates(self, item):
        """Should return a sequence of TrackInfo objects that match the
        item provided.
        """
        return ()

    def configure(self, config):
        """This method is called with the ConfigParser object after
        the CLI starts up.
        """
        pass

    def item_fields(self):
        """Returns field descriptors to be added to the MediaFile class,
        in the form of a dictionary whose keys are field names and whose
        values are descriptor (e.g., MediaField) instances. The Library
        database schema is not (currently) extended.
        """
        return {}


    listeners = None

    @classmethod
    def register_listener(cls, event, func):
        """Add a function as a listener for the specified event. (An
        imperative alternative to the @listen decorator.)
        """
        if cls.listeners is None:
            cls.listeners = defaultdict(list)
        cls.listeners[event].append(func)

    @classmethod
    def listen(cls, event):
        """Decorator that adds a function as an event handler for the
        specified event (as a string). The parameters passed to function
        will vary depending on what event occurred.

        The function should respond to named parameters.
        function(**kwargs) will trap all arguments in a dictionary.
        Example:

            >>> @MyPlugin.listen("imported")
            >>> def importListener(**kwargs):
            >>>     pass
        """
        def helper(func):
            if cls.listeners is None:
                cls.listeners = defaultdict(list)
            cls.listeners[event].append(func)
            return func
        return helper

    template_funcs = None
    template_fields = None

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

_classes = []
def load_plugins(names=()):
    """Imports the modules for a sequence of plugin names. Each name
    must be the name of a Python module under the "beetsplug" namespace
    package in sys.path; the module indicated should contain the
    BeetsPlugin subclasses desired.
    """
    for name in names:
        modname = '%s.%s' % (PLUGIN_NAMESPACE, name)
        try:
            try:
                namespace = __import__(modname, None, None)
            except ImportError as exc:
                # Again, this is hacky:
                if exc.args[0].endswith(' ' + name):
                    log.warn('** plugin %s not found' % name)
                else:
                    raise
            else:
                for obj in getattr(namespace, name).__dict__.values():
                    if isinstance(obj, type) and issubclass(obj, BeetsPlugin) \
                            and obj != BeetsPlugin:
                        _classes.append(obj)

        except:
            log.warn('** error loading plugin %s' % name)
            log.warn(traceback.format_exc())

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
    """Returns a dict of {prefix: beet.library.PluginQuery} objects from all
    loaded plugins.  """
    out = {}
    for plugin in find_plugins():
        out.update(plugin.queries())
    return out

def track_distance(item, info):
    """Gets the track distance calculated by all loaded plugins.
    Returns a (distance, distance_max) pair.
    """
    dist = 0.0
    dist_max = 0.0
    for plugin in find_plugins():
        d, dm = plugin.track_distance(item, info)
        dist += d
        dist_max += dm
    return dist, dist_max

def album_distance(items, album_info, mapping):
    """Returns the album distance calculated by plugins."""
    dist = 0.0
    dist_max = 0.0
    for plugin in find_plugins():
        d, dm = plugin.album_distance(items, album_info, mapping)
        dist += d
        dist_max += dm
    return dist, dist_max

def candidates(items):
    """Gets MusicBrainz candidates for an album from each plugin.
    """
    out = []
    for plugin in find_plugins():
        out.extend(plugin.candidates(items))
    return out

def item_candidates(item):
    """Gets MusicBrainz candidates for an item from the plugins.
    """
    out = []
    for plugin in find_plugins():
        out.extend(plugin.item_candidates(item))
    return out

def configure(config):
    """Sends the configuration object to each plugin."""
    for plugin in find_plugins():
        plugin.configure(config)

def template_funcs():
    """Get all the template functions declared by plugins as a
    dictionary.
    """
    funcs = {}
    for plugin in find_plugins():
        if plugin.template_funcs:
            funcs.update(plugin.template_funcs)
    return funcs

def template_values(item):
    """Get all the template values computed for a given Item by
    registered field computations.
    """
    values = {}
    for plugin in find_plugins():
        if plugin.template_fields:
            for name, func in plugin.template_fields.iteritems():
                values[name] = unicode(func(item))
    return values

def _add_media_fields(fields):
    """Adds a {name: descriptor} dictionary of fields to the MediaFile
    class. Called during the plugin initialization.
    """
    for key, value in fields.iteritems():
        setattr(mediafile.MediaFile, key, value)

def import_stages():
    """Get a list of import stage functions defined by plugins."""
    stages = []
    for plugin in find_plugins():
        if hasattr(plugin, 'import_stages'):
            stages += plugin.import_stages
    return stages


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
    """Sends an event to all assigned event listeners. Event is the
    name of  the event to send, all other named arguments go to the
    event handler(s).

    Returns the number of handlers called.
    """
    log.debug('Sending event: %s' % event)
    handlers = event_handlers()[event]
    for handler in handlers:
        handler(**arguments)
    return len(handlers)
