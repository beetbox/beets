# -*- coding: utf-8 -*-
# This file is part of Confuse.
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

"""Worry-free YAML configuration files.
"""
from __future__ import division, absolute_import, print_function

import platform
import os
import pkgutil
import sys
import yaml
import collections
import re
from collections import OrderedDict

UNIX_DIR_VAR = 'XDG_CONFIG_HOME'
UNIX_DIR_FALLBACK = '~/.config'
WINDOWS_DIR_VAR = 'APPDATA'
WINDOWS_DIR_FALLBACK = '~\\AppData\\Roaming'
MAC_DIR = '~/Library/Application Support'

CONFIG_FILENAME = 'config.yaml'
DEFAULT_FILENAME = 'config_default.yaml'
ROOT_NAME = 'root'

YAML_TAB_PROBLEM = "found character '\\t' that cannot start any token"

REDACTED_TOMBSTONE = 'REDACTED'


# Utilities.

PY3 = sys.version_info[0] == 3
STRING = str if PY3 else unicode  # noqa: F821
BASESTRING = str if PY3 else basestring  # noqa: F821
NUMERIC_TYPES = (int, float) if PY3 else (int, float, long)  # noqa: F821


def iter_first(sequence):
    """Get the first element from an iterable or raise a ValueError if
    the iterator generates no values.
    """
    it = iter(sequence)
    try:
        return next(it)
    except StopIteration:
        raise ValueError()


# Exceptions.

class ConfigError(Exception):
    """Base class for exceptions raised when querying a configuration.
    """


class NotFoundError(ConfigError):
    """A requested value could not be found in the configuration trees.
    """


class ConfigValueError(ConfigError):
    """The value in the configuration is illegal."""


class ConfigTypeError(ConfigValueError):
    """The value in the configuration did not match the expected type.
    """


class ConfigTemplateError(ConfigError):
    """Base class for exceptions raised because of an invalid template.
    """


class ConfigReadError(ConfigError):
    """A configuration file could not be read."""
    def __init__(self, filename, reason=None):
        self.filename = filename
        self.reason = reason

        message = u'file {0} could not be read'.format(filename)
        if isinstance(reason, yaml.scanner.ScannerError) and \
                reason.problem == YAML_TAB_PROBLEM:
            # Special-case error message for tab indentation in YAML markup.
            message += u': found tab character at line {0}, column {1}'.format(
                reason.problem_mark.line + 1,
                reason.problem_mark.column + 1,
            )
        elif reason:
            # Generic error message uses exception's message.
            message += u': {0}'.format(reason)

        super(ConfigReadError, self).__init__(message)


# Views and sources.

class ConfigSource(dict):
    """A dictionary augmented with metadata about the source of the
    configuration.
    """
    def __init__(self, value, filename=None, default=False):
        super(ConfigSource, self).__init__(value)
        if filename is not None and not isinstance(filename, BASESTRING):
            raise TypeError(u'filename must be a string or None')
        self.filename = filename
        self.default = default

    def __repr__(self):
        return 'ConfigSource({0!r}, {1!r}, {2!r})'.format(
            super(ConfigSource, self),
            self.filename,
            self.default,
        )

    @classmethod
    def of(cls, value):
        """Given either a dictionary or a `ConfigSource` object, return
        a `ConfigSource` object. This lets a function accept either type
        of object as an argument.
        """
        if isinstance(value, ConfigSource):
            return value
        elif isinstance(value, dict):
            return ConfigSource(value)
        else:
            raise TypeError(u'source value must be a dict')


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
            raise NotFoundError(u"{0} not found".format(self.name))

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
        return '<{}: {}>'.format(self.__class__.__name__, self.name)

    def __iter__(self):
        """Iterate over the keys of a dictionary view or the *subviews*
        of a list view.
        """
        # Try getting the keys, if this is a dictionary view.
        try:
            keys = self.keys()
            for key in keys:
                yield key

        except ConfigTypeError:
            # Otherwise, try iterating over a list.
            collection = self.get()
            if not isinstance(collection, (list, tuple)):
                raise ConfigTypeError(
                    u'{0} must be a dictionary or a list, not {1}'.format(
                        self.name, type(collection).__name__
                    )
                )

            # Yield all the indices in the list.
            for index in range(len(collection)):
                yield self[index]

    def __getitem__(self, key):
        """Get a subview of this view."""
        return Subview(self, key)

    def __setitem__(self, key, value):
        """Create an overlay source to assign a given key under this
        view.
        """
        self.set({key: value})

    def __contains__(self, key):
        return self[key].exists()

    def set_args(self, namespace):
        """Overlay parsed command-line arguments, generated by a library
        like argparse or optparse, onto this view's value. ``namespace``
        can be a ``dict`` or namespace object.
        """
        args = {}
        if isinstance(namespace, dict):
            items = namespace.items()
        else:
            items = namespace.__dict__.items()
        for key, value in items:
            if value is not None:  # Avoid unset options.
                args[key] = value
        self.set(args)

    # Magical conversions. These special methods make it possible to use
    # View objects somewhat transparently in certain circumstances. For
    # example, rather than using ``view.get(bool)``, it's possible to
    # just say ``bool(view)`` or use ``view`` in a conditional.

    def __str__(self):
        """Get the value for this view as a bytestring.
        """
        if PY3:
            return self.__unicode__()
        else:
            return bytes(self.get())

    def __unicode__(self):
        """Get the value for this view as a Unicode string.
        """
        return STRING(self.get())

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
                    u'{0} must be a dict, not {1}'.format(
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
                    u'{0} must be an iterable, not {1}'.format(
                        self.name, type(collection).__name__
                    )
                )
            for value in it:
                yield value

    # Validation and conversion.

    def flatten(self, redact=False):
        """Create a hierarchy of OrderedDicts containing the data from
        this view, recursively reifying all views to get their
        represented values.

        If `redact` is set, then sensitive values are replaced with
        the string "REDACTED".
        """
        od = OrderedDict()
        for key, view in self.items():
            if redact and view.redact:
                od[key] = REDACTED_TOMBSTONE
            else:
                try:
                    od[key] = view.flatten(redact=redact)
                except ConfigTypeError:
                    od[key] = view.get()
        return od

    def get(self, template=None):
        """Retrieve the value for this view according to the template.

        The `template` against which the values are checked can be
        anything convertible to a `Template` using `as_template`. This
        means you can pass in a default integer or string value, for
        example, or a type to just check that something matches the type
        you expect.

        May raise a `ConfigValueError` (or its subclass,
        `ConfigTypeError`) or a `NotFoundError` when the configuration
        doesn't satisfy the template.
        """
        return as_template(template).value(self, template)

    # Shortcuts for common templates.

    def as_filename(self):
        """Get the value as a path. Equivalent to `get(Filename())`.
        """
        return self.get(Filename())

    def as_choice(self, choices):
        """Get the value from a list of choices. Equivalent to
        `get(Choice(choices))`.
        """
        return self.get(Choice(choices))

    def as_number(self):
        """Get the value as any number type: int or float. Equivalent to
        `get(Number())`.
        """
        return self.get(Number())

    def as_str_seq(self, split=True):
        """Get the value as a sequence of strings. Equivalent to
        `get(StrSeq())`.
        """
        return self.get(StrSeq(split=split))

    def as_str(self):
        """Get the value as a (Unicode) string. Equivalent to
        `get(unicode)` on Python 2 and `get(str)` on Python 3.
        """
        return self.get(String())

    # Redaction.

    @property
    def redact(self):
        """Whether the view contains sensitive information and should be
        redacted from output.
        """
        return () in self.get_redactions()

    @redact.setter
    def redact(self, flag):
        self.set_redaction((), flag)

    def set_redaction(self, path, flag):
        """Add or remove a redaction for a key path, which should be an
        iterable of keys.
        """
        raise NotImplementedError()

    def get_redactions(self):
        """Get the set of currently-redacted sub-key-paths at this view.
        """
        raise NotImplementedError()


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
        self.redactions = set()

    def add(self, obj):
        self.sources.append(ConfigSource.of(obj))

    def set(self, value):
        self.sources.insert(0, ConfigSource.of(value))

    def resolve(self):
        return ((dict(s), s) for s in self.sources)

    def clear(self):
        """Remove all sources (and redactions) from this
        configuration.
        """
        del self.sources[:]
        self.redactions.clear()

    def root(self):
        return self

    def set_redaction(self, path, flag):
        if flag:
            self.redactions.add(path)
        elif path in self.redactions:
            self.redactions.remove(path)

    def get_redactions(self):
        return self.redactions


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
            self.name += u'#{0}'.format(self.key)
        elif isinstance(self.key, bytes):
            self.name += self.key.decode('utf-8')
        elif isinstance(self.key, STRING):
            self.name += self.key
        else:
            self.name += repr(self.key)

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
                    u"{0} must be a collection, not {1}".format(
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

    def set_redaction(self, path, flag):
        self.parent.set_redaction((self.key,) + path, flag)

    def get_redactions(self):
        return (kp[1:] for kp in self.parent.get_redactions()
                if kp and kp[0] == self.key)


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
                u'expected a mapping node, but found %s' % node.id,
                node.start_mark
            )

        mapping = OrderedDict()
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                hash(key)
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(
                    u'while constructing a mapping',
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
        with open(filename, 'rb') as f:
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
            if not (isinstance(node_key, yaml.ScalarNode) and
                    not node_key.style):
                best_style = False
            if not (isinstance(node_value, yaml.ScalarNode) and
                    not node_value.style):
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
            value = u'yes'
        else:
            value = u'no'
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
                raise ConfigError(u'{0} must be a directory'.format(
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

    def dump(self, full=True, redact=False):
        """Dump the Configuration object to a YAML file.

        The order of the keys is determined from the default
        configuration file. All keys not in the default configuration
        will be appended to the end of the file.

        :param filename:  The file to dump the configuration to, or None
                          if the YAML string should be returned instead
        :type filename:   unicode
        :param full:      Dump settings that don't differ from the defaults
                          as well
        :param redact:    Remove sensitive information (views with the `redact`
                          flag set) from the output
        """
        if full:
            out_dict = self.flatten(redact=redact)
        else:
            # Exclude defaults when flattening.
            sources = [s for s in self.sources if not s.default]
            temp_root = RootView(sources)
            temp_root.redactions = self.redactions
            out_dict = temp_root.flatten(redact=redact)

        yaml_out = yaml.dump(out_dict, Dumper=Dumper,
                             default_flow_style=None, indent=4,
                             width=1000)

        # Restore comments to the YAML text.
        default_source = None
        for source in self.sources:
            if source.default:
                default_source = source
                break
        if default_source and default_source.filename:
            with open(default_source.filename, 'rb') as fp:
                default_data = fp.read()
            yaml_out = restore_yaml_comments(yaml_out,
                                             default_data.decode('utf8'))

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
        super(LazyConfig, self).clear()
        self._lazy_suffix = []
        self._lazy_prefix = []


# "Validated" configuration views: experimental!


REQUIRED = object()
"""A sentinel indicating that there is no default value and an exception
should be raised when the value is missing.
"""


class Template(object):
    """A value template for configuration fields.

    The template works like a type and instructs Confuse about how to
    interpret a deserialized YAML value. This includes type conversions,
    providing a default value, and validating for errors. For example, a
    filepath type might expand tildes and check that the file exists.
    """
    def __init__(self, default=REQUIRED):
        """Create a template with a given default value.

        If `default` is the sentinel `REQUIRED` (as it is by default),
        then an error will be raised when a value is missing. Otherwise,
        missing values will instead return `default`.
        """
        self.default = default

    def __call__(self, view):
        """Invoking a template on a view gets the view's value according
        to the template.
        """
        return self.value(view, self)

    def value(self, view, template=None):
        """Get the value for a `ConfigView`.

        May raise a `NotFoundError` if the value is missing (and the
        template requires it) or a `ConfigValueError` for invalid values.
        """
        if view.exists():
            value, _ = view.first()
            return self.convert(value, view)
        elif self.default is REQUIRED:
            # Missing required value. This is an error.
            raise NotFoundError(u"{0} not found".format(view.name))
        else:
            # Missing value, but not required.
            return self.default

    def convert(self, value, view):
        """Convert the YAML-deserialized value to a value of the desired
        type.

        Subclasses should override this to provide useful conversions.
        May raise a `ConfigValueError` when the configuration is wrong.
        """
        # Default implementation does no conversion.
        return value

    def fail(self, message, view, type_error=False):
        """Raise an exception indicating that a value cannot be
        accepted.

        `type_error` indicates whether the error is due to a type
        mismatch rather than a malformed value. In this case, a more
        specific exception is raised.
        """
        exc_class = ConfigTypeError if type_error else ConfigValueError
        raise exc_class(
            u'{0}: {1}'.format(view.name, message)
        )

    def __repr__(self):
        return '{0}({1})'.format(
            type(self).__name__,
            '' if self.default is REQUIRED else repr(self.default),
        )


class Integer(Template):
    """An integer configuration value template.
    """
    def convert(self, value, view):
        """Check that the value is an integer. Floats are rounded.
        """
        if isinstance(value, int):
            return value
        elif isinstance(value, float):
            return int(value)
        else:
            self.fail(u'must be a number', view, True)


class Number(Template):
    """A numeric type: either an integer or a floating-point number.
    """
    def convert(self, value, view):
        """Check that the value is an int or a float.
        """
        if isinstance(value, NUMERIC_TYPES):
            return value
        else:
            self.fail(
                u'must be numeric, not {0}'.format(type(value).__name__),
                view,
                True
            )


class MappingTemplate(Template):
    """A template that uses a dictionary to specify other types for the
    values for a set of keys and produce a validated `AttrDict`.
    """
    def __init__(self, mapping):
        """Create a template according to a dict (mapping). The
        mapping's values should themselves either be Types or
        convertible to Types.
        """
        subtemplates = {}
        for key, typ in mapping.items():
            subtemplates[key] = as_template(typ)
        self.subtemplates = subtemplates

    def value(self, view, template=None):
        """Get a dict with the same keys as the template and values
        validated according to the value types.
        """
        out = AttrDict()
        for key, typ in self.subtemplates.items():
            out[key] = typ.value(view[key], self)
        return out

    def __repr__(self):
        return 'MappingTemplate({0})'.format(repr(self.subtemplates))


class String(Template):
    """A string configuration value template.
    """
    def __init__(self, default=REQUIRED, pattern=None):
        """Create a template with the added optional `pattern` argument,
        a regular expression string that the value should match.
        """
        super(String, self).__init__(default)
        self.pattern = pattern
        if pattern:
            self.regex = re.compile(pattern)

    def __repr__(self):
        args = []

        if self.default is not REQUIRED:
            args.append(repr(self.default))

        if self.pattern is not None:
            args.append('pattern=' + repr(self.pattern))

        return 'String({0})'.format(', '.join(args))

    def convert(self, value, view):
        """Check that the value is a string and matches the pattern.
        """
        if isinstance(value, BASESTRING):
            if self.pattern and not self.regex.match(value):
                self.fail(
                    u"must match the pattern {0}".format(self.pattern),
                    view
                )
            return value
        else:
            self.fail(u'must be a string', view, True)


class Choice(Template):
    """A template that permits values from a sequence of choices.
    """
    def __init__(self, choices):
        """Create a template that validates any of the values from the
        iterable `choices`.

        If `choices` is a map, then the corresponding value is emitted.
        Otherwise, the value itself is emitted.
        """
        self.choices = choices

    def convert(self, value, view):
        """Ensure that the value is among the choices (and remap if the
        choices are a mapping).
        """
        if value not in self.choices:
            self.fail(
                u'must be one of {0}, not {1}'.format(
                    repr(list(self.choices)), repr(value)
                ),
                view
            )

        if isinstance(self.choices, collections.Mapping):
            return self.choices[value]
        else:
            return value

    def __repr__(self):
        return 'Choice({0!r})'.format(self.choices)


class OneOf(Template):
    """A template that permits values complying to one of the given templates.
    """
    def __init__(self, allowed, default=REQUIRED):
        super(OneOf, self).__init__(default)
        self.allowed = list(allowed)

    def __repr__(self):
        args = []

        if self.allowed is not None:
            args.append('allowed=' + repr(self.allowed))

        if self.default is not REQUIRED:
            args.append(repr(self.default))

        return 'OneOf({0})'.format(', '.join(args))

    def value(self, view, template):
        self.template = template
        return super(OneOf, self).value(view, template)

    def convert(self, value, view):
        """Ensure that the value follows at least one template.
        """
        is_mapping = isinstance(self.template, MappingTemplate)

        for candidate in self.allowed:
            try:
                if is_mapping:
                    if isinstance(candidate, Filename) and \
                            candidate.relative_to:
                        next_template = candidate.template_with_relatives(
                            view,
                            self.template
                        )

                        next_template.subtemplates[view.key] = as_template(
                            candidate
                        )
                    else:
                        next_template = MappingTemplate({view.key: candidate})

                    return view.parent.get(next_template)[view.key]
                else:
                    return view.get(candidate)
            except ConfigTemplateError:
                raise
            except ConfigError:
                pass
            except ValueError as exc:
                raise ConfigTemplateError(exc)

        self.fail(
            u'must be one of {0}, not {1}'.format(
                repr(self.allowed), repr(value)
            ),
            view
        )


class StrSeq(Template):
    """A template for values that are lists of strings.

    Validates both actual YAML string lists and single strings. Strings
    can optionally be split on whitespace.
    """
    def __init__(self, split=True):
        """Create a new template.

        `split` indicates whether, when the underlying value is a single
        string, it should be split on whitespace. Otherwise, the
        resulting value is a list containing a single string.
        """
        super(StrSeq, self).__init__()
        self.split = split

    def convert(self, value, view):
        if isinstance(value, bytes):
            value = value.decode('utf-8', 'ignore')

        if isinstance(value, STRING):
            if self.split:
                return value.split()
            else:
                return [value]

        try:
            value = list(value)
        except TypeError:
            self.fail(u'must be a whitespace-separated string or a list',
                      view, True)

        def convert(x):
            if isinstance(x, STRING):
                return x
            elif isinstance(x, bytes):
                return x.decode('utf-8', 'ignore')
            else:
                self.fail(u'must be a list of strings', view, True)
        return list(map(convert, value))


class Filename(Template):
    """A template that validates strings as filenames.

    Filenames are returned as absolute, tilde-free paths.

    Relative paths are relative to the template's `cwd` argument
    when it is specified, then the configuration directory (see
    the `config_dir` method) if they come from a file. Otherwise,
    they are relative to the current working directory. This helps
    attain the expected behavior when using command-line options.
    """
    def __init__(self, default=REQUIRED, cwd=None, relative_to=None,
                 in_app_dir=False):
        """`relative_to` is the name of a sibling value that is
        being validated at the same time.

        `in_app_dir` indicates whether the path should be resolved
        inside the application's config directory (even when the setting
        does not come from a file).
        """
        super(Filename, self).__init__(default)
        self.cwd = cwd
        self.relative_to = relative_to
        self.in_app_dir = in_app_dir

    def __repr__(self):
        args = []

        if self.default is not REQUIRED:
            args.append(repr(self.default))

        if self.cwd is not None:
            args.append('cwd=' + repr(self.cwd))

        if self.relative_to is not None:
            args.append('relative_to=' + repr(self.relative_to))

        if self.in_app_dir:
            args.append('in_app_dir=True')

        return 'Filename({0})'.format(', '.join(args))

    def resolve_relative_to(self, view, template):
        if not isinstance(template, (collections.Mapping, MappingTemplate)):
            # disallow config.get(Filename(relative_to='foo'))
            raise ConfigTemplateError(
                u'relative_to may only be used when getting multiple values.'
            )

        elif self.relative_to == view.key:
            raise ConfigTemplateError(
                u'{0} is relative to itself'.format(view.name)
            )

        elif self.relative_to not in view.parent.keys():
            # self.relative_to is not in the config
            self.fail(
                (
                    u'needs sibling value "{0}" to expand relative path'
                ).format(self.relative_to),
                view
            )

        old_template = {}
        old_template.update(template.subtemplates)

        # save time by skipping MappingTemplate's init loop
        next_template = MappingTemplate({})
        next_relative = self.relative_to

        # gather all the needed templates and nothing else
        while next_relative is not None:
            try:
                # pop to avoid infinite loop because of recursive
                # relative paths
                rel_to_template = old_template.pop(next_relative)
            except KeyError:
                if next_relative in template.subtemplates:
                    # we encountered this config key previously
                    raise ConfigTemplateError((
                        u'{0} and {1} are recursively relative'
                    ).format(view.name, self.relative_to))
                else:
                    raise ConfigTemplateError((
                        u'missing template for {0}, needed to expand {1}\'s' +
                        u'relative path'
                    ).format(self.relative_to, view.name))

            next_template.subtemplates[next_relative] = rel_to_template
            next_relative = rel_to_template.relative_to

        return view.parent.get(next_template)[self.relative_to]

    def value(self, view, template=None):
        path, source = view.first()
        if not isinstance(path, BASESTRING):
            self.fail(
                u'must be a filename, not {0}'.format(type(path).__name__),
                view,
                True
            )
        path = os.path.expanduser(STRING(path))

        if not os.path.isabs(path):
            if self.cwd is not None:
                # relative to the template's argument
                path = os.path.join(self.cwd, path)

            elif self.relative_to is not None:
                path = os.path.join(
                    self.resolve_relative_to(view, template),
                    path,
                )

            elif source.filename or self.in_app_dir:
                # From defaults: relative to the app's directory.
                path = os.path.join(view.root().config_dir(), path)

        return os.path.abspath(path)


class TypeTemplate(Template):
    """A simple template that checks that a value is an instance of a
    desired Python type.
    """
    def __init__(self, typ, default=REQUIRED):
        """Create a template that checks that the value is an instance
        of `typ`.
        """
        super(TypeTemplate, self).__init__(default)
        self.typ = typ

    def convert(self, value, view):
        if not isinstance(value, self.typ):
            self.fail(
                u'must be a {0}, not {1}'.format(
                    self.typ.__name__,
                    type(value).__name__,
                ),
                view,
                True
            )
        return value


class AttrDict(dict):
    """A `dict` subclass that can be accessed via attributes (dot
    notation) for convenience.
    """
    def __getattr__(self, key):
        if key in self:
            return self[key]
        else:
            raise AttributeError(key)


def as_template(value):
    """Convert a simple "shorthand" Python value to a `Template`.
    """
    if isinstance(value, Template):
        # If it's already a Template, pass it through.
        return value
    elif isinstance(value, collections.Mapping):
        # Dictionaries work as templates.
        return MappingTemplate(value)
    elif value is int:
        return Integer()
    elif isinstance(value, int):
        return Integer(value)
    elif isinstance(value, type) and issubclass(value, BASESTRING):
        return String()
    elif isinstance(value, BASESTRING):
        return String(value)
    elif isinstance(value, set):
        # convert to list to avoid hash related problems
        return Choice(list(value))
    elif isinstance(value, list):
        return OneOf(value)
    elif value is float:
        return Number()
    elif value is None:
        return Template()
    elif value is dict:
        return TypeTemplate(collections.Mapping)
    elif value is list:
        return TypeTemplate(collections.Sequence)
    elif isinstance(value, type):
        return TypeTemplate(value)
    else:
        raise ValueError(u'cannot convert to template: {0!r}'.format(value))
