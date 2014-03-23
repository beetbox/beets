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

import sys
import logging
import traceback
from collections import defaultdict

import beets
from beets import mediafile
from beets import util

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
        self.import_stages = []
        self.name = name or self.__module__.split('.')[-1]
        self.config = beets.config[self.name]
        if not self.template_funcs:
            self.template_funcs = {}
        if not self.template_fields:
            self.template_fields = {}
        if not self.album_template_fields:
            self.album_template_fields = {}

    def commands(self):
        """Should return a list of beets.ui.Subcommand objects for
        commands that should be added to beets' CLI.
        """
        return ()

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

    # Events with backwards compatibility

    def on_pluginload(self):
        """Called after all the plugins have been loaded after the
        ``beet`` command starts
        """
        self._call_listener('pluginload')

    def on_import(self):
        """"Called after a ``beet import`` command finishes (the ``lib``
        keyword argument is a Library object; ``paths`` is a list of
        paths (strings) that were imported).
        """
        self._call_listener('import')

    def on_album_imported(self, lib=None, album=None):
        """Called with an ``Album`` object every time the ``import``
        command finishes adding an album to the library.
        """
        self._call_listener('album_imported', lib=lib, album=album)

    def on_item_imported(self, lib=None, item=None):
        """Called with an ``Item`` object every time the importer adds a
        singleton to the library (not called for full-album imports).
        """
        self._call_listener('item_imported', lib=lib, item=item)

    def on_item_copied(self, item=None, source=None, destination=None):
        """Called with an ``Item`` object whenever its file is copied.
        Parameters: ``item``, ``source`` path, ``destination`` path
        """
        self._call_listener('item_copied', item=item, source=source,
                                           destination=destination)

    def on_item_moved(self, item=None, source=None, destination=None):
        """Called with an ``Item`` object whenever its file is moved.
        """
        self._call_listener('item_moved', item=item, source=source,
                                          destination=destination)

    def on_item_removed(self, item=None):
        """Called when an item (singleton or album's part) is removed
        from the library (even when its file is not deleted from disk).
        """
        self._call_listener('item_removed', item=item)

    def on_before_write(self, item=None):
        """Called just before a file's metadata is written to disk
        (i.e., just before the file on disk is opened).
        """
        self._call_listener('write', item=item)

    def on_after_write(self, item=None):
        """Called a file's metadata is written to disk (i.e., just after
        the file on disk is closed).
        """
        self._call_listener('after_write', item=item)

    def on_import_task_start(self, task=None, session=None):
        """Called before an import task begins processing.
        """
        self._call_listener('import_task_start', task=task, session=task)

    def on_import_task_apply(self, task=None, session=None):
        """Called after metadata changes have been applied in an import
        task.
        """
        self._call_listener('import_task_apply', task=task, session=session)

    def on_import_task_choice(self, task=None, session=None):
        """Called after a decision has been made about an import task.
        This event can be used to initiate further interaction with the
        user.  Use ``task.choice_flag`` to determine or change the
        action to be taken.
        """
        self._call_listener('import_task_choice', task=task, session=session)

    def on_import_task_files(self, task=None, session=None):
        """Called after an import task finishes manipulating the
        filesystem (copying and moving files, writing metadata tags).
        """
        self._call_listener('import_task_files', task=task, session=session)

    def on_library_opened(self, lib=None):
        """Called after beets starts up and initializes the main Library object.
        """
        self._call_listener('library_opened', lib=lib)

    def on_database_change(self, lib=None):
        """Called after a modification has been made to the library
        database. The change might not be committed yet.
        """
        self._call_listener('database_change', lib=lib)

    def on_cli_exit(self, lib=None):
        """Called just before the ``beet`` command-line program exits.
        """
        self._call_listener('cli_exit', lib=lib)

    def _call_listener(self, event, **args):
        """Calls listeners registered with the legacy API.
        """
        if self.listeners is None:
            self.listeners = defaultdict(list)
        for listener in self.listeners[event]:
            listener(**args)


    listeners = None

    # DEPRECATED
    @classmethod
    def register_listener(cls, event, func):
        """Add a function as a listener for the specified event. (An
        imperative alternative to the @listen decorator.)
        """
        if cls.listeners is None:
            cls.listeners = defaultdict(list)
        cls.listeners[event].append(func)

    # DEPRECATED
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


class Registry(list):
    """Loads plugins and exposes their hooks.

    The items of the list are instances of ``BeetsPlugin``.
    """

    def __init__(self):
        super(Registry, self).__init__()
        self._loaded_classes = set()
        self._beetsplug_loaded = False

    def load(self, names, paths=()):
        """Add plugins from module names.

        ``names`` is a list of module names in the beetsplug namespace
        package. The method tries to load each module. It then collects
        all proper subclasses of BeetsPlugin from that module,
        instantiates them and adds them to the registry. It will keep
        track of all loaded classes so they won't be added twice.

        ``paths`` is a list of additional paths to load modules from.
        They are added to the registry with ``add_paths``.
        """
        self.add_paths(paths)
        for name in names:
            modname = '%s.%s' % (PLUGIN_NAMESPACE, name)
            try:
                try:
                    namespace = __import__(modname, None, None)
                    self._beetsplug_loaded = True
                except ImportError as exc:
                    # Again, this is hacky:
                    if exc.args[0].endswith(' ' + name):
                        log.warn('** plugin %s not found' % name)
                    else:
                        raise
                else:
                    for cls in getattr(namespace, name).__dict__.values():
                        if isinstance(cls, type) and issubclass(cls, BeetsPlugin) \
                                and cls != BeetsPlugin:
                            self._load_class(cls)

            except:
                log.warn('** error loading plugin %s' % name)
                log.warn(traceback.format_exc())
        send('pluginload')

    def add_paths(self, paths):
        """Adds a list of paths to beetsplug namespace package and
        ``sys.path``.

        If you have a beetsplug module in say
        ``/lib/beetsplug/mymodule.py``, you can either add the path as
        '/lib' or '/lib/beetsplug'. If you use the former you need to
        add an ``__init__.py`` file which uses ``pkgutil.extend_path``
        to the beetsplug directory. Additionally you may only use this
        approach once with ``add_paths`` since python will refuse to
        load beetsplug from additional ``sys.path``s once it has already
        been loaded.

        For the beetsplug package, paths are prepended. This means
        that modules are loaded from the most recently added path.
        """
        # TODO clarify this, see also
        # https://gist.github.com/geigerzaehler/9508410
        paths =  map(util.normpath, paths)
        sys.path += paths
        import beetsplug
        beetsplug.__path__ = paths + beetsplug.__path__

    def _load_class(self, cls):
        if cls not in self._loaded_classes:
            self._loaded_classes.add(cls)
            self.append(cls())


    def commands(self):
        """Returns a list of Subcommand objects from all loaded plugins.
        """
        out = []
        for plugin in self:
            out += plugin.commands()
        return out

    def queries(self):
        """Returns a dict mapping prefix strings to Query subclasses all loaded
        plugins.
        """
        out = {}
        for plugin in self:
            out.update(plugin.queries())
        return out

    def track_distance(self, item, info):
        """Gets the track distance calculated by all loaded plugins.
        Returns a Distance object.
        """
        from beets.autotag.hooks import Distance
        dist = Distance()
        for plugin in self:
            dist.update(plugin.track_distance(item, info))
        return dist

    def album_distance(self, items, album_info, mapping):
        """Returns the album distance calculated by plugins."""
        from beets.autotag.hooks import Distance
        dist = Distance()
        for plugin in self:
            dist.update(plugin.album_distance(items, album_info, mapping))
        return dist

    def candidates(self, items, artist, album, va_likely):
        """Gets MusicBrainz candidates for an album from each plugin.
        """
        out = []
        for plugin in self:
            out.extend(plugin.candidates(items, artist, album, va_likely))
        return out

    def item_candidates(self, item, artist, title):
        """Gets MusicBrainz candidates for an item from the plugins.
        """
        out = []
        for plugin in self:
            out.extend(plugin.item_candidates(item, artist, title))
        return out

    def album_for_id(self, album_id):
        """Get AlbumInfo objects for a given ID string.
        """
        out = []
        for plugin in self:
            res = plugin.album_for_id(album_id)
            if res:
                out.append(res)
        return out

    def track_for_id(self, track_id):
        """Get TrackInfo objects for a given ID string.
        """
        out = []
        for plugin in self:
            res = plugin.track_for_id(track_id)
            if res:
                out.append(res)
        return out

    def template_funcs(self):
        """Get all the template functions declared by plugins as a
        dictionary.
        """
        funcs = {}
        for plugin in self:
            if plugin.template_funcs:
                funcs.update(plugin.template_funcs)
        return funcs

    def import_stages(self):
        """Get a list of import stage functions defined by plugins."""
        stages = []
        for plugin in self:
            if hasattr(plugin, 'import_stages'):
                stages += plugin.import_stages
        return stages


    # New-style (lazy) plugin-provided fields.

    def item_field_getters(self):
        """Get a dictionary mapping field names to unary functions that
        compute the field's value.
        """
        funcs = {}
        for plugin in self:
            if plugin.template_fields:
                funcs.update(plugin.template_fields)
        return funcs

    def album_field_getters(self):
        """As above, for album fields.
        """
        funcs = {}
        for plugin in self:
            if plugin.album_template_fields:
                funcs.update(plugin.album_template_fields)
        return funcs


    def send(self, event, **arguments):
        """Sends an event to all assigned event listeners. Event is the
        name of  the event to send, all other named arguments go to the
        event handler(s).

        Returns the number of handlers called.
        """
        log.debug('Sending event: %s' % event)
        for plugin in self:
            handlername = 'on_{0}'.format(event)
            if hasattr(plugin, handlername):
                getattr(plugin, handlername)(**arguments)


registry = Registry()

# For backwards compatibility
load_plugins = registry.load
def find_plugins():
    return registry
commands = registry.commands
queries = registry.queries
track_distance = registry.track_distance
album_distance = registry.album_distance
candidates = registry.candidates
item_candidates = registry.item_candidates
album_for_id = registry.album_for_id
track_for_id = registry.track_for_id
template_funcs = registry.template_funcs
_add_media_fields = registry._add_media_fields
import_stages = registry.import_stages
item_field_getters = registry.item_field_getters
album_field_getters = registry.album_field_getters
send = registry.send
