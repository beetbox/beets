# This file is part of Confit.
# Copyright 2014, Adrian Sampson.
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

YAML_TAB_PROBLEM = "found character '\\t' that cannot start any token"


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
        if isinstance(reason, yaml.scanner.ScannerError) and \
                reason.problem == YAML_TAB_PROBLEM:
            # Special-case error message for tab indentation in YAML markup.
            message += ': found tab character at line {0}, column {1}'.format(
                reason.problem_mark.line + 1,
                reason.problem_mark.column + 1,
            )
        elif reason:
            # Generic error message uses exception's message.
            message += ': {0}'.format(reason)

        super(ConfigReadError, self).__init__(message)


# Views and sources.

class ConfigSource(dict):
    """A dictionary augmented with metadata about the source of the
    configuration.
    """
    def __init__(self, value, filename=None, default=False):
        super(ConfigSource, self).__init__(value)
        if filename is not None and not isinstance(filename, BASESTRING):
            raise TypeError('filename must be a string or None')
        self.filename = filename
        self.default = default

    def __repr__(self):
        return 'ConfigSource({0}, {1}, {2})'.format(
            super(ConfigSource, self).__repr__(),
            repr(self.filename),
            repr(self.default)
        )

    @classmethod
    def of(self, value):
        """Given either a dictionary or a `ConfigSource` object, return
        a `ConfigSource` object. This lets a function accept either type
        of object as an argument.
        """
        if isinstance(value, ConfigSource):
            return value
        elif isinstance(value, dict):
            return ConfigSource(value)
        else:
            raise TypeError('source value must be a dict')

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

    def resolve(self):
        """The core (internal) data retrieval method. Generates (value,
        source) pairs for each source that contains a value for this
        view. May raise ConfigTypeError if a type error occurs while
        traversing a source.
        """
        raise NotImplementedError

    def first(self):
        """Return a (value, source) pair for the first object found for
        this view. This amounts to the first element returned by
        `resolve`. If no values are available, a NotFoundError is
        raised.
        """
        pairs = self.resolve()
        try:
            return iter_first(pairs)
        except ValueError:
            raise NotFoundError("{0} not found".format(self.name))

    def exists(self):
        """Determine whether the view has a setting in any source.
        """
        try:
            self.first()
        except NotFoundError:
            return False
        return True

    def add(self, value):
        """Set the *default* value for this configuration view. The
        specified value is added as the lowest-priority configuration
        data source.
        """
        raise NotImplementedError

    def set(self, value):
        """*Override* the value for this configuration view. The
        specified value is added as the highest-priority configuration
        data source.
        """
        raise NotImplementedError

    def root(self):
        """The RootView object from which this view is descended.
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

    def set_args(self, namespace):
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

        for dic, _ in self.resolve():
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
        for collection, _ in self.resolve():
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

    # Validation and conversion.

    def get(self, typ=None):
        """Returns the canonical value for the view, checked against the
        passed-in type. If the value is not an instance of the given
        type, a ConfigTypeError is raised. May also raise a
        NotFoundError.
        """
        value, _ = self.first()

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

    def as_filename(self):
        """Get a string as a normalized as an absolute, tilde-free path.

        Relative paths are relative to the configuration directory (see
        the `config_dir` method) if they come from a file. Otherwise,
        they are relative to the current working directory. This helps
        attain the expected behavior when using command-line options.
        """
        path, source = self.first()
        if not isinstance(path, BASESTRING):
            raise ConfigTypeError('{0} must be a filename, not {1}'.format(
                self.name, type(path).__name__
            ))
        path = os.path.expanduser(STRING(path))

        if not os.path.isabs(path) and source.filename:
            # From defaults: relative to the app's directory.
            path = os.path.join(self.root().config_dir(), path)

        return os.path.abspath(path)

    def as_choice(self, choices):
        """Ensure that the value is among a collection of choices and
        return it. If `choices` is a dictionary, then return the
        corresponding value rather than the value itself (the key).
        """
        value = self.get()

        if value not in choices:
            raise ConfigValueError(
                '{0} must be one of {1}, not {2}'.format(
                    self.name, repr(list(choices)), repr(value)
                )
            )

        if isinstance(choices, dict):
            return choices[value]
        else:
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

    def flatten(self):
        """Create a hierarchy of OrderedDicts containing the data from
        this view, recursively reifying all views to get their
        represented values.
        """
        od = OrderedDict()
        for key, view in self.items():
            try:
                od[key] = view.flatten()
            except ConfigTypeError:
                od[key] = view.get()
        return od


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
        self.sources.append(ConfigSource.of(obj))

    def set(self, value):
        self.sources.insert(0, ConfigSource.of(value))

    def resolve(self):
        return ((dict(s), s) for s in self.sources)

    def clear(self):
        """Remove all sources from this configuration."""
        del self.sources[:]

    def root(self):
        return self


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

    def resolve(self):
        for collection, source in self.parent.resolve():
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
            yield value, source

    def set(self, value):
        self.parent.set({self.key: value})

    def add(self, value):
        self.parent.add({self.key: value})

    def root(self):
        return self.parent.root()


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
    """Return a platform-specific list of candidates for user
    configuration directories on the system.

    The candidates are in order of priority, from highest to lowest. The
    last element is the "fallback" location to be used when no
    higher-priority config file exists.
    """
    paths = []

    if platform.system() == 'Darwin':
        paths.append(MAC_DIR)
        paths.append(UNIX_DIR_FALLBACK)
        if UNIX_DIR_VAR in os.environ:
            paths.append(os.environ[UNIX_DIR_VAR])

    elif platform.system() == 'Windows':
        paths.append(WINDOWS_DIR_FALLBACK)
        if WINDOWS_DIR_VAR in os.environ:
            paths.append(os.environ[WINDOWS_DIR_VAR])

    else:
        # Assume Unix.
        paths.append(UNIX_DIR_FALLBACK)
        if UNIX_DIR_VAR in os.environ:
            paths.append(os.environ[UNIX_DIR_VAR])

    # Expand and deduplicate paths.
    out = []
    for path in paths:
        path = os.path.abspath(os.path.expanduser(path))
        if path not in out:
            out.append(path)
    return out


# YAML loading.

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


# YAML dumping.

class Dumper(yaml.SafeDumper):
    """A PyYAML Dumper that represents OrderedDicts as ordinary mappings
    (in order, of course).
    """
    # From http://pyyaml.org/attachment/ticket/161/use_ordered_dict.py
    def represent_mapping(self, tag, mapping, flow_style=None):
        value = []
        node = yaml.MappingNode(tag, value, flow_style=flow_style)
        if self.alias_key is not None:
            self.represented_objects[self.alias_key] = node
        best_style = False
        if hasattr(mapping, 'items'):
            mapping = list(mapping.items())
        for item_key, item_value in mapping:
            node_key = self.represent_data(item_key)
            node_value = self.represent_data(item_value)
            if not (isinstance(node_key, yaml.ScalarNode)
                    and not node_key.style):
                best_style = False
            if not (isinstance(node_value, yaml.ScalarNode)
                    and not node_value.style):
                best_style = False
            value.append((node_key, node_value))
        if flow_style is None:
            if self.default_flow_style is not None:
                node.flow_style = self.default_flow_style
            else:
                node.flow_style = best_style
        return node

    def represent_list(self, data):
        """If a list has less than 4 items, represent it in inline style
        (i.e. comma separated, within square brackets).
        """
        node = super(Dumper, self).represent_list(data)
        length = len(data)
        if self.default_flow_style is None and length < 4:
            node.flow_style = True
        elif self.default_flow_style is None:
            node.flow_style = False
        return node

    def represent_bool(self, data):
        """Represent bool as 'yes' or 'no' instead of 'true' or 'false'.
        """
        if data:
            value = 'yes'
        else:
            value = 'no'
        return self.represent_scalar('tag:yaml.org,2002:bool', value)

    def represent_none(self, data):
        """Represent a None value with nothing instead of 'none'.
        """
        return self.represent_scalar('tag:yaml.org,2002:null', '')

Dumper.add_representer(OrderedDict, Dumper.represent_dict)
Dumper.add_representer(bool, Dumper.represent_bool)
Dumper.add_representer(type(None), Dumper.represent_none)
Dumper.add_representer(list, Dumper.represent_list)

def restore_yaml_comments(data, default_data):
    """Scan default_data for comments (we include empty lines in our
    definition of comments) and place them before the same keys in data.
    Only works with comments that are on one or more own lines, i.e.
    not next to a yaml mapping.
    """
    comment_map = dict()
    default_lines = iter(default_data.splitlines())
    for line in default_lines:
        if not line:
            comment = "\n"
        elif line.startswith("#"):
            comment = "{0}\n".format(line)
        else:
            continue
        while True:
            line = next(default_lines)
            if line and not line.startswith("#"):
                break
            comment += "{0}\n".format(line)
        key = line.split(':')[0].strip()
        comment_map[key] = comment
    out_lines = iter(data.splitlines())
    out_data = ""
    for line in out_lines:
        key = line.split(':')[0].strip()
        if key in comment_map:
            out_data += comment_map[key]
        out_data += "{0}\n".format(line)
    return out_data


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

    def user_config_path(self):
        """Points to the location of the user configuration.

        The file may not exist.
        """
        return os.path.join(self.config_dir(), CONFIG_FILENAME)

    def _add_user_source(self):
        """Add the configuration options from the YAML file in the
        user's configuration directory (given by `config_dir`) if it
        exists.
        """
        filename = self.user_config_path()
        if os.path.isfile(filename):
            self.add(ConfigSource(load_yaml(filename) or {}, filename))

    def _add_default_source(self):
        """Add the package's default configuration settings. This looks
        for a YAML file located inside the package for the module
        `modname` if it was given.
        """
        if self.modname:
            pkg_path = _package_path(self.modname)
            if pkg_path:
                filename = os.path.join(pkg_path, DEFAULT_FILENAME)
                if os.path.isfile(filename):
                    self.add(ConfigSource(load_yaml(filename), filename, True))

    def read(self, user=True, defaults=True):
        """Find and read the files for this configuration and set them
        as the sources for this configuration. To disable either
        discovered user configuration files or the in-package defaults,
        set `user` or `defaults` to `False`.
        """
        if user:
            self._add_user_source()
        if defaults:
            self._add_default_source()

    def config_dir(self):
        """Get the path to the user configuration directory. The
        directory is guaranteed to exist as a postcondition (one may be
        created if none exist).

        If the application's ``...DIR`` environment variable is set, it
        is used as the configuration directory. Otherwise,
        platform-specific standard configuration locations are searched
        for a ``config.yaml`` file. If no configuration file is found, a
        fallback path is used.
        """
        # If environment variable is set, use it.
        if self._env_var in os.environ:
            appdir = os.environ[self._env_var]
            appdir = os.path.abspath(os.path.expanduser(appdir))
            if os.path.isfile(appdir):
                raise ConfigError('{0} must be a directory'.format(
                    self._env_var
                ))

        else:
            # Search platform-specific locations. If no config file is
            # found, fall back to the final directory in the list.
            for confdir in config_dirs():
                appdir = os.path.join(confdir, self.appname)
                if os.path.isfile(os.path.join(appdir, CONFIG_FILENAME)):
                    break

        # Ensure that the directory exists.
        if not os.path.isdir(appdir):
            os.makedirs(appdir)
        return appdir

    def set_file(self, filename):
        """Parses the file as YAML and inserts it into the configuration
        sources with highest priority.
        """
        filename = os.path.abspath(filename)
        self.set(ConfigSource(load_yaml(filename), filename))

    def dump(self, full=True):
        """Dump the Configuration object to a YAML file.

        The order of the keys is determined from the default
        configuration file. All keys not in the default configuration
        will be appended to the end of the file.

        :param filename:  The file to dump the configuration to, or None
                          if the YAML string should be returned instead
        :type filename:   unicode
        :param full:      Dump settings that don't differ from the defaults
                          as well
        """
        if full:
            out_dict = self.flatten()
        else:
            # Exclude defaults when flattening.
            sources = [s for s in self.sources if not s.default]
            out_dict = RootView(sources).flatten()

        yaml_out = yaml.dump(out_dict, Dumper=Dumper,
                             default_flow_style=None, indent=4,
                             width=1000)

        # Restore comments to the YAML text.
        default_source = None
        for source in self.sources:
            if source.default:
                default_source = source
                break
        if default_source:
            with open(default_source.filename, 'r') as fp:
                default_data = fp.read()
            yaml_out = restore_yaml_comments(yaml_out, default_data)

        return yaml_out


class LazyConfig(Configuration):
    """A Configuration at reads files on demand when it is first
    accessed. This is appropriate for using as a global config object at
    the module level.
    """
    def __init__(self, appname, modname=None):
        super(LazyConfig, self).__init__(appname, modname, False)
        self._materialized = False  # Have we read the files yet?
        self._lazy_prefix = []  # Pre-materialization calls to set().
        self._lazy_suffix = []  # Calls to add().

    def read(self, user=True, defaults=True):
        self._materialized = True
        super(LazyConfig, self).read(user, defaults)

    def resolve(self):
        if not self._materialized:
            # Read files and unspool buffers.
            self.read()
            self.sources += self._lazy_suffix
            self.sources[:0] = self._lazy_prefix
        return super(LazyConfig, self).resolve()

    def add(self, value):
        super(LazyConfig, self).add(value)
        if not self._materialized:
            # Buffer additions to end.
            self._lazy_suffix += self.sources
            del self.sources[:]

    def set(self, value):
        super(LazyConfig, self).set(value)
        if not self._materialized:
            # Buffer additions to beginning.
            self._lazy_prefix[:0] = self.sources
            del self.sources[:]

    def clear(self):
        """Remove all sources from this configuration."""
        del self.sources[:]
        self._lazy_suffix = []
        self._lazy_prefix = []
