# This file is part of Confit.
# Copyright 2012, Adrian Sampson.
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

"""Worry-free YAML configuration files.
"""
from __future__ import unicode_literals
import platform
import os
import pkgutil
import sys
import yaml
import types
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

UNIX_DIR_VAR = 'XDG_CONFIG_HOME'
UNIX_DIR_FALLBACK = '~/.config'
WINDOWS_DIR_VAR = 'APPDATA'
WINDOWS_DIR_FALLBACK = '~\\AppData\\Roaming'
MAC_DIR = '~/Library/Application Support'

CONFIG_FILENAME = 'config.yaml'
DEFAULT_FILENAME = 'config_default.yaml'
ROOT_NAME = 'root'


# Utilities.

PY3 = sys.version_info[0] == 3
STRING = str if PY3 else unicode
BASESTRING = str if PY3 else basestring
NUMERIC_TYPES = (int, float) if PY3 else (int, float, long)
TYPE_TYPES = (type,) if PY3 else (type, types.ClassType)

def iter_first(sequence):
    """Get the first element from an iterable or raise a ValueError if
    the iterator generates no values.
    """
    it = iter(sequence)
    try:
        if PY3:
            return next(it)
        else:
            return it.next()
    except StopIteration:
        raise ValueError()


# Exceptions.

class ConfigError(Exception):
    """Base class for exceptions raised when querying a configuration.
    """

class NotFoundError(ConfigError):
    """A requested value could not be found in the configuration trees.
    """

class ConfigTypeError(ConfigError, TypeError):
    """The value in the configuration did not match the expected type.
    """

class ConfigValueError(ConfigError, ValueError):
    """The value in the configuration is illegal."""

class ConfigReadError(ConfigError):
    """A configuration file could not be read."""
    def __init__(self, filename, reason=None):
        self.filename = filename
        self.reason = reason
        message = 'file {0} could not be read'.format(filename)
        if reason:
            message += ': {0}'.format(reason)
        super(ConfigReadError, self).__init__(message)


# Views and data access logic.

class ConfigView(object):
    """A configuration "view" is a query into a program's configuration
    data. A view represents a hypothetical location in the configuration
    tree; to extract the data from the location, a client typically
    calls the ``view.get()`` method. The client can access children in
    the tree (subviews) by subscripting the parent view (i.e.,
    ``view[key]``).
    """

    name = None
    """The name of the view, depicting the path taken through the
    configuration in Python-like syntax (e.g., ``foo['bar'][42]``).
    """

    def get_all(self):
        """Generates all available values for the view in the order of
        the configuration's sources. (Each source may have at most one
        value for each view.) If no values are available, no values are
        generated. If a type error is encountered when traversing a
        source to resolve the view, a ConfigTypeError may be raised.
        """
        raise NotImplementedError

    def get(self, typ=None):
        """Returns the canonical value for the view. This amounts to the
        first item in ``view.get_all()``. If the view cannot be
        resolved, this method raises a NotFoundError.
        """
        values = self.get_all()

        # Get the first value.
        try:
            value = iter_first(values)
        except ValueError:
            raise NotFoundError("{0} not found".format(self.name))

        # Validate type.
        if typ is not None:
            if not isinstance(typ, TYPE_TYPES):
                raise TypeError('argument to get() must be a type')

            if not isinstance(value, typ):
                raise ConfigTypeError(
                    "{0} must be of type {1}, not {2}".format(
                        self.name, typ.__name__, type(value).__name__
                    )
                )

        return value

    def add(self, value):
        """Add a value as a source for configuration data. The object as
        added as the lowest-priority source. This can be used to
        dynamically extend the defaults.
        """
        raise NotImplementedError

    def set(self, value):
        """Create an overlay source to set the value at this view.
        """
        raise NotImplementedError

    def __repr__(self):
        return '<ConfigView: %s>' % self.name

    def __getitem__(self, key):
        """Get a subview of this view."""
        return Subview(self, key)

    def __setitem__(self, key, value):
        """Create an overlay source to assign a given key under this
        view.
        """
        self.set({key: value})

    def add_args(self, namespace):
        """Overlay parsed command-line arguments, generated by a library
        like argparse or optparse, onto this view's value.
        """
        args = {}
        for key, value in namespace.__dict__.items():
            if value is not None:  # Avoid unset options.
                args[key] = value
        self.set(args)

    # Magical conversions. These special methods make it possible to use
    # View objects somewhat transparently in certain circumstances. For
    # example, rather than using ``view.get(bool)``, it's possible to
    # just say ``bool(view)`` or use ``view`` in a conditional.

    def __str__(self):
        """Gets the value for this view as a byte string."""
        return str(self.get())

    def __unicode__(self):
        """Gets the value for this view as a unicode string. (Python 2
        only.)
        """
        return unicode(self.get())

    def __nonzero__(self):
        """Gets the value for this view as a boolean. (Python 2 only.)
        """
        return self.__bool__()

    def __bool__(self):
        """Gets the value for this view as a boolean. (Python 3 only.)
        """
        return bool(self.get())

    # Dictionary emulation methods.

    def keys(self):
        """Returns a list containing all the keys available as subviews
        of the current views. This enumerates all the keys in *all*
        dictionaries matching the current view, in contrast to
        ``view.get(dict).keys()``, which gets all the keys for the
        *first* dict matching the view. If the object for this view in
        any source is not a dict, then a ConfigTypeError is raised. The
        keys are ordered according to how they appear in each source.
        """
        keys = []

        for dic in self.get_all():
            try:
                cur_keys = dic.keys()
            except AttributeError:
                raise ConfigTypeError(
                    '{0} must be a dict, not {1}'.format(
                        self.name, type(dic).__name__
                    )
                )

            for key in cur_keys:
                if key not in keys:
                    keys.append(key)

        return keys

    def items(self):
        """Iterates over (key, subview) pairs contained in dictionaries
        from *all* sources at this view. If the object for this view in
        any source is not a dict, then a ConfigTypeError is raised.
        """
        for key in self.keys():
            yield key, self[key]

    def values(self):
        """Iterates over all the subviews contained in dictionaries from
        *all* sources at this view. If the object for this view in any
        source is not a dict, then a ConfigTypeError is raised.
        """
        for key in self.keys():
            yield self[key]

    # List/sequence emulation.

    def all_contents(self):
        """Iterates over all subviews from collections at this view from
        *all* sources. If the object for this view in any source is not
        iterable, then a ConfigTypeError is raised. This method is
        intended to be used when the view indicates a list; this method
        will concatenate the contents of the list from all sources.
        """
        for collection in self.get_all():
            try:
                it = iter(collection)
            except TypeError:
                raise ConfigTypeError(
                    '{0} must be an iterable, not {1}'.format(
                        self.name, type(collection).__name__
                    )
                )
            for value in it:
                yield value

    # Explicit validators/converters.

    def as_filename(self):
        """Get a string as a normalized filename, made absolute and with
        tilde expanded.
        """
        value = STRING(self.get())
        return os.path.abspath(os.path.expanduser(value))

    def as_choice(self, choices):
        """Ensure that the value is among a collection of choices and
        return it.
        """
        value = self.get()
        if value not in choices:
            raise ConfigValueError(
                '{0} must be one of {1}, not {2}'.format(
                    self.name, repr(value), repr(list(choices))
                )
            )
        return value

    def as_number(self):
        """Ensure that a value is of numeric type."""
        value = self.get()
        if isinstance(value, NUMERIC_TYPES):
            return value
        raise ConfigTypeError(
            '{0} must be numeric, not {1}'.format(
                self.name, type(value).__name__
            )
        )

    def as_str_seq(self):
        """Get the value as a list of strings. The underlying configured
        value can be a sequence or a single string. In the latter case,
        the string is treated as a white-space separated list of words.
        """
        value = self.get()
        if isinstance(value, bytes):
            value = value.decode('utf8', 'ignore')

        if isinstance(value, STRING):
            return value.split()
        else:
            try:
                return list(value)
            except TypeError:
                raise ConfigTypeError(
                    '{0} must be a whitespace-separated string or '
                    'a list'.format(self.name)
                )

class RootView(ConfigView):
    """The base of a view hierarchy. This view keeps track of the
    sources that may be accessed by subviews.
    """
    def __init__(self, sources):
        """Create a configuration hierarchy for a list of sources. At
        least one source must be provided. The first source in the list
        has the highest priority.
        """
        self.sources = list(sources)
        self.name = ROOT_NAME

    def add(self, obj):
        self.sources.append(obj)

    def set(self, value):
        self.sources.insert(0, value)

    def get_all(self):
        return self.sources

class Subview(ConfigView):
    """A subview accessed via a subscript of a parent view."""
    def __init__(self, parent, key):
        """Make a subview of a parent view for a given subscript key.
        """
        self.parent = parent
        self.key = key

        # Choose a human-readable name for this view.
        if isinstance(self.parent, RootView):
            self.name = ''
        else:
            self.name = self.parent.name
            if not isinstance(self.key, int):
                self.name += '.'
        if isinstance(self.key, int):
            self.name += '#{0}'.format(self.key)
        elif isinstance(self.key, BASESTRING):
            self.name += '{0}'.format(self.key)
        else:
            self.name += '{0}'.format(repr(self.key))

    def get_all(self):
        for collection in self.parent.get_all():
            try:
                value = collection[self.key]
            except IndexError:
                # List index out of bounds.
                continue
            except KeyError:
                # Dict key does not exist.
                continue
            except TypeError:
                # Not subscriptable.
                raise ConfigTypeError(
                    "{0} must be a collection, not {1}".format(
                        self.parent.name, type(collection).__name__
                    )
                )
            yield value

    def set(self, value):
        self.parent.set({self.key: value})

    def add(self, value):
        self.parent.add({self.key: value})


# Config file paths, including platform-specific paths and in-package
# defaults.

# Based on get_root_path from Flask by Armin Ronacher.
def _package_path(name):
    """Returns the path to the package containing the named module or
    None if the path could not be identified (e.g., if
    ``name == "__main__"``).
    """
    loader = pkgutil.get_loader(name)
    if loader is None or name == '__main__':
        return None

    if hasattr(loader, 'get_filename'):
        filepath = loader.get_filename(name)
    else:
        # Fall back to importing the specified module.
        __import__(name)
        filepath = sys.modules[name].__file__

    return os.path.dirname(os.path.abspath(filepath))

def config_dirs():
    """Returns a list of user configuration directories to be searched.
    """
    if platform.system() == 'Darwin':
        paths = [MAC_DIR, UNIX_DIR_FALLBACK]
    elif platform.system() == 'Windows':
        if WINDOWS_DIR_VAR in os.environ:
            paths = [os.environ[WINDOWS_DIR_VAR]]
        else:
            paths = [WINDOWS_DIR_FALLBACK]
    else:
        # Assume Unix.
        paths = [UNIX_DIR_FALLBACK]
        if UNIX_DIR_VAR in os.environ:
            paths.insert(0, os.environ[UNIX_DIR_VAR])

    # Expand and deduplicate paths.
    out = []
    for path in paths:
        path = os.path.abspath(os.path.expanduser(path))
        if path not in out:
            out.append(path)
    return out


# YAML.

class Loader(yaml.SafeLoader):
    """A customized YAML loader. This loader deviates from the official
    YAML spec in a few convenient ways:

    - All strings as are Unicode objects.
    - All maps are OrderedDicts.
    - Strings can begin with % without quotation.
    """
    # All strings should be Unicode objects, regardless of contents.
    def _construct_unicode(self, node):
        return self.construct_scalar(node)

    # Use ordered dictionaries for every YAML map.
    # From https://gist.github.com/844388
    def construct_yaml_map(self, node):
        data = OrderedDict()
        yield data
        value = self.construct_mapping(node)
        data.update(value)

    def construct_mapping(self, node, deep=False):
        if isinstance(node, yaml.MappingNode):
            self.flatten_mapping(node)
        else:
            raise yaml.constructor.ConstructorError(
                None, None,
                'expected a mapping node, but found %s' % node.id,
                node.start_mark
            )

        mapping = OrderedDict()
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                hash(key)
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(
                    'while constructing a mapping',
                    node.start_mark, 'found unacceptable key (%s)' % exc,
                    key_node.start_mark
                )
            value = self.construct_object(value_node, deep=deep)
            mapping[key] = value
        return mapping

    # Allow bare strings to begin with %. Directives are still detected.
    def check_plain(self):
        plain = super(Loader, self).check_plain()
        return plain or self.peek() == '%'

Loader.add_constructor('tag:yaml.org,2002:str', Loader._construct_unicode)
Loader.add_constructor('tag:yaml.org,2002:map', Loader.construct_yaml_map)
Loader.add_constructor('tag:yaml.org,2002:omap', Loader.construct_yaml_map)

def load_yaml(filename):
    """Read a YAML document from a file. If the file cannot be read or
    parsed, a ConfigReadError is raised.
    """
    try:
        with open(filename, 'r') as f:
            return yaml.load(f, Loader=Loader)
    except (IOError, yaml.error.YAMLError) as exc:
        raise ConfigReadError(filename, exc)


# Main interface.

class Configuration(RootView):
    def __init__(self, appname, modname=None, read=True):
        """Create a configuration object by reading the
        automatically-discovered config files for the application for a
        given name. If `modname` is specified, it should be the import
        name of a module whose package will be searched for a default
        config file. (Otherwise, no defaults are used.) Pass `False` for
        `read` to disable automatic reading of all discovered
        configuration files. Use this when creating a configuration
        object at module load time and then call the `read` method
        later.
        """
        super(Configuration, self).__init__([])
        self.appname = appname
        self.modname = modname

        self._env_var = '{0}DIR'.format(self.appname.upper())

        if read:
            self.read()

    def _search_dirs(self):
        """Yield directories that will be searched for configuration
        files for this application.
        """
        # Application's environment variable.
        if self._env_var in os.environ:
            path = os.environ[self._env_var]
            yield os.path.abspath(os.path.expanduser(path))

        # Standard configuration directories.
        for confdir in config_dirs():
            yield os.path.join(confdir, self.appname)

    def _filenames(self, user=True, defaults=True):
        """Get a list of filenames for configuration files. The files
        must actually exist and are placed in the order that they should
        be prioritized. The `user` and `defaults` flags control whether
        files should be used from discovered configuration directories
        and from the in-package defaults directory; set either of these
        to `False` to disable searching for them.
        """
        out = []

        # Search standard directories.
        if user:
            for appdir in self._search_dirs():
                out.append(os.path.join(appdir, CONFIG_FILENAME))

        # Search the package for a defaults file.
        if defaults and self.modname:
            pkg_path = _package_path(self.modname)
            if pkg_path:
                out.append(os.path.join(pkg_path, DEFAULT_FILENAME))

        return [p for p in out if os.path.isfile(p)]

    def read(self, user=True, defaults=True):
        """Find and read the files for this configuration and set them
        as the sources for this configuration. To disable either
        discovered user configuration files or the in-package defaults,
        set `user` or `defaults` to `False`.
        """
        self.sources = []
        for filename in self._filenames(user, defaults):
            self.sources.append(load_yaml(filename))

    def config_dir(self):
        """Get the path to the directory containing the highest-priority
        user configuration. If no user configuration is present, create a
        suitable directory before returning it.
        """
        dirs = list(self._search_dirs())

        # First, look for an existant configuration file.
        for appdir in dirs:
            if os.path.isfile(os.path.join(appdir, CONFIG_FILENAME)):
                return appdir

        # As a fallback, create the first-listed directory name.
        appdir = dirs[0]
        if not os.path.isdir(appdir):
            os.makedirs(appdir)
        return appdir
