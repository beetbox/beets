# This file is part of beets.
# Copyright 2010, Adrian Sampson.
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
import itertools
import traceback
from collections import defaultdict

PLUGIN_NAMESPACE = 'beetsplug'
DEFAULT_PLUGINS = ['bpd']

# Global logger.
log = logging.getLogger('beets')


# Managing the plugins themselves.

class BeetsPlugin(object):
    """The base class for all beets plugins. Plugins provide
    functionality by defining a subclass of BeetsPlugin and overriding
    the abstract methods defined here.
    """
    def commands(self):
        """Should return a list of beets.ui.Subcommand objects for
        commands that should be added to beets' CLI.
        """
        return ()

    def track_distance(self, item, info):
        """Should return a (distance, distance_max) pair to be added
        to the distance value for every track comparison.
        """
        return 0.0, 0.0

    listeners = None
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

def load_plugins(names=()):
    """Imports the modules for a sequence of plugin names. Each name
    must be the name of a Python module under the "beetsplug" namespace
    package in sys.path; the module indicated should contain the
    BeetsPlugin subclasses desired. A default set of plugins is also
    loaded.
    """
    for name in itertools.chain(names, DEFAULT_PLUGINS):
        modname = '%s.%s' % (PLUGIN_NAMESPACE, name)
        try:
            try:
                __import__(modname, None, None)
            except ImportError, exc:
                # Again, this is hacky:
                if exc.args[0].endswith(' ' + name):
                    log.warn('** plugin %s not found' % name)
                else:
                    raise
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
    for cls in BeetsPlugin.__subclasses__():
        # Only instantiate each plugin class once.
        if cls not in _instances:
            _instances[cls] = cls()
        plugins.append(_instances[cls])
    return plugins


# Plugin commands.

def commands():
    """Returns a list of Subcommand objects from all loaded plugins.
    """
    out = []
    for plugin in find_plugins():
        out += plugin.commands()
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

# Event dispatch.

# All the handlers for the event system.
# Each key of the dictionary should contain a list of functions to be
# called for any event. Functions will be called in the order they were
# added.
_event_handlers = defaultdict(list)

def load_listeners():
    """Loads and registers event handlers from all loaded plugins.
    """
    for plugin in find_plugins():
        if plugin.listeners:
            for event, handlers in plugin.listeners.items():
                _event_handlers[event] += handlers

def send(event, **arguments):
    """Sends an event to all assigned event listeners. Event is the
    name of  the event to send, all other named arguments go to the
    event handler(s).

    Returns the number of handlers called.
    """
    handlers = _event_handlers[event]
    for handler in handlers:
        handler(**arguments)
    return len(handlers)
