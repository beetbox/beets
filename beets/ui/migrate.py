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

"""Conversion from legacy (pre-1.1) configuration to Confit/YAML
configuration.
"""
import os
import ConfigParser
import codecs
import yaml
import logging
import time
import itertools
import re

import beets
from beets import util
from beets import ui
from beets.util import confit

CONFIG_PATH_VAR = 'BEETSCONFIG'
DEFAULT_CONFIG_FILENAME_UNIX = '.beetsconfig'
DEFAULT_CONFIG_FILENAME_WINDOWS = 'beetsconfig.ini'
DEFAULT_LIBRARY_FILENAME_UNIX = '.beetsmusic.blb'
DEFAULT_LIBRARY_FILENAME_WINDOWS = 'beetsmusic.blb'
WINDOWS_BASEDIR = os.environ.get('APPDATA') or '~'

OLD_CONFIG_SUFFIX = '.old'
PLUGIN_NAMES = {
    'rdm': 'random',
    'fuzzy_search': 'fuzzy',
}
AUTO_KEYS = ('automatic', 'autofetch', 'autoembed', 'autoscrub')
IMPORTFEEDS_PREFIX = 'feeds_'
CONFIG_MIGRATED_MESSAGE = u"""
You appear to be upgrading from beets 1.0 (or earlier) to 1.1. Your
configuration file has been migrated automatically to:
{newconfig}
Edit this file to configure beets. You might want to remove your
old-style ".beetsconfig" file now. See the documentation for more
details on the new configuration system:
http://beets.readthedocs.org/page/reference/config.html
""".strip()
DB_MIGRATED_MESSAGE = u'Your database file has also been copied to:\n{newdb}'
YAML_COMMENT = '# Automatically migrated from legacy .beetsconfig.\n\n'

log = logging.getLogger('beets')

# An itertools recipe.
def grouper(n, iterable):
    args = [iter(iterable)] * n
    return itertools.izip_longest(*args)

def _displace(fn):
    """Move a file aside using a timestamp suffix so a new file can be
    put in its place.
    """
    util.move(
        fn,
        u'{0}.old.{1}'.format(fn, int(time.time())),
        True
    )

def default_paths():
    """Produces the appropriate default config and library database
    paths for the current system. On Unix, this is always in ~. On
    Windows, tries ~ first and then $APPDATA for the config and library
    files (for backwards compatibility).
    """
    windows = os.path.__name__ == 'ntpath'
    if windows:
        windata = os.environ.get('APPDATA') or '~'

    # Shorthand for joining paths.
    def exp(*vals):
        return os.path.expanduser(os.path.join(*vals))

    config = exp('~', DEFAULT_CONFIG_FILENAME_UNIX)
    if windows and not os.path.exists(config):
        config = exp(windata, DEFAULT_CONFIG_FILENAME_WINDOWS)

    libpath = exp('~', DEFAULT_LIBRARY_FILENAME_UNIX)
    if windows and not os.path.exists(libpath):
        libpath = exp(windata, DEFAULT_LIBRARY_FILENAME_WINDOWS)

    return config, libpath

def get_config():
    """Using the same logic as beets 1.0, locate and read the
    .beetsconfig file. Return a ConfigParser instance or None if no
    config is found.
    """
    default_config, default_libpath = default_paths()
    if CONFIG_PATH_VAR in os.environ:
        configpath = os.path.expanduser(os.environ[CONFIG_PATH_VAR])
    else:
        configpath = default_config

    config = ConfigParser.SafeConfigParser()
    if os.path.exists(util.syspath(configpath)):
        with codecs.open(configpath, 'r', encoding='utf-8') as f:
            config.readfp(f)
        return config, configpath
    else:
        return None, configpath

def flatten_config(config):
    """Given a ConfigParser, flatten the values into a dict-of-dicts
    representation where each section gets its own dictionary of values.
    """
    out = confit.OrderedDict()
    for section in config.sections():
        sec_dict = out[section] = confit.OrderedDict()
        for option in config.options(section):
            sec_dict[option] = config.get(section, option, True)
    return out

def transform_value(value):
    """Given a string read as the value of a config option, return a
    massaged version of that value (possibly with a different type).
    """
    # Booleans.
    if value.lower() in ('false', 'no', 'off'):
        return False
    elif value.lower() in ('true', 'yes', 'on'):
        return True

    # Integers.
    try:
        return int(value)
    except ValueError:
        pass

    # Floats.
    try:
        return float(value)
    except ValueError:
        pass
    
    return value

def transform_data(data):
    """Given a dict-of-dicts representation of legacy config data, tweak
    the data into a new form. This new form is suitable for dumping as
    YAML.
    """
    out = confit.OrderedDict()

    for section, pairs in data.items():
        if section == 'beets':
            # The "main" section. In the new config system, these values
            # are in the "root": no section at all.
            for key, value in pairs.items():
                value = transform_value(value)

                if key.startswith('import_'):
                    # Importer config is now under an "import:" key.
                    if 'import' not in out:
                        out['import'] = confit.OrderedDict()
                    out['import'][key[7:]] = value

                elif key == 'plugins':
                    # Renamed plugins.
                    plugins = value.split()
                    new_plugins = [PLUGIN_NAMES.get(p, p) for p in plugins]
                    out['plugins'] = ' '.join(new_plugins)

                elif key == 'replace':
                    # YAMLy representation for character replacements.
                    replacements = confit.OrderedDict()
                    for pat, repl in grouper(2, value.split()):
                        if repl == '<strip>':
                            repl = ''
                        replacements[pat] = repl
                    out['replace'] = replacements

                elif key == 'pluginpath':
                    # Used to be a colon-separated string. Now a list.
                    out['pluginpath'] = value.split(':')

                else:
                    out[key] = value

        elif pairs:
            # Other sections (plugins, etc).
            sec_out = out[section] = confit.OrderedDict()
            for key, value in pairs.items():

                # Standardized "auto" option.
                if key in AUTO_KEYS:
                    key = 'auto'

                # Unnecessary : hack in queries.
                if section == 'paths':
                    key = key.replace('_', ':')

                # Changed option names for importfeeds plugin.
                if section == 'importfeeds':
                    if key.startswith(IMPORTFEEDS_PREFIX):
                        key = key[len(IMPORTFEEDS_PREFIX):]
                
                sec_out[key] = transform_value(value)

    return out

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
        best_style = True
        if hasattr(mapping, 'items'):
            mapping = list(mapping.items())
        for item_key, item_value in mapping:
            node_key = self.represent_data(item_key)
            node_value = self.represent_data(item_value)
            if not (isinstance(node_key, yaml.ScalarNode) and \
                    not node_key.style):
                best_style = False
            if not (isinstance(node_value, yaml.ScalarNode) and \
                    not node_value.style):
                best_style = False
            value.append((node_key, node_value))
        if flow_style is None:
            if self.default_flow_style is not None:
                node.flow_style = self.default_flow_style
            else:
                node.flow_style = best_style
        return node
Dumper.add_representer(confit.OrderedDict, Dumper.represent_dict)

def migrate_config(replace=False):
    """Migrate a legacy beetsconfig file to a new-style config.yaml file
    in an appropriate place. If `replace` is enabled, then any existing
    config.yaml will be moved aside. Otherwise, the process is aborted
    when the file exists.
    """

    # Load legacy configuration data, if any.
    config, configpath = get_config()
    if not config:
        log.debug(u'no config file found at {0}'.format(
            util.displayable_path(configpath)
            ))
        return

    # Get the new configuration file path and possibly move it out of
    # the way.
    destfn = os.path.join(beets.config.config_dir(), confit.CONFIG_FILENAME)
    if os.path.exists(destfn):
        if replace:
            log.debug(u'moving old config aside: {0}'.format(
                util.displayable_path(destfn)
            ))
            _displace(destfn)
        else:
            # File exists and we won't replace it. We're done.
            return

    log.debug(u'migrating config file {0}'.format(
        util.displayable_path(configpath)
    ))

    # Convert the configuration to a data structure ready to be dumped
    # as the new Confit file.
    data = transform_data(flatten_config(config))

    # Encode result as YAML.
    yaml_out = yaml.dump(
        data,
        Dumper=Dumper,
        default_flow_style=False,
        indent=4,
        width=1000,
    )
    # A ridiculous little hack to add some whitespace between "sections"
    # in the YAML output. I hope this doesn't break any YAML syntax.
    yaml_out = re.sub(r'(\n\w+:\n    [^-\s])', '\n\\1', yaml_out)
    yaml_out = YAML_COMMENT + yaml_out

    # Write the data to the new config destination.
    log.debug(u'writing migrated config to {0}'.format(
        util.displayable_path(destfn)
    ))
    with open(destfn, 'w') as f:
        f.write(yaml_out)
    return destfn

def migrate_db(replace=False):
    """Copy the beets library database file to the new location (e.g.,
    from ~/.beetsmusic.blb to ~/.config/beets/library.db).
    """
    _, srcfn = default_paths()
    destfn = beets.config['library'].as_filename()

    if not os.path.exists(srcfn) or srcfn == destfn:
        # Old DB does not exist or we're configured to point to the same
        # database. Do nothing.
        return
    
    if os.path.exists(destfn):
        if replace:
            log.debug(u'moving old database aside: {0}'.format(
                util.displayable_path(destfn)
            ))
            _displace(destfn)
        else:
            return

    log.debug(u'copying database from {0} to {1}'.format(
        util.displayable_path(srcfn), util.displayable_path(destfn)
    ))
    util.copy(srcfn, destfn)
    return destfn

def migrate_state(replace=False):
    """Copy the beets runtime state file from the old path (i.e.,
    ~/.beetsstate) to the new path (i.e., ~/.config/beets/state.pickle).
    """
    srcfn = os.path.expanduser(os.path.join('~', '.beetsstate'))
    if not os.path.exists(srcfn):
        return

    destfn = beets.config['statefile'].as_filename()
    if os.path.exists(destfn):
        if replace:
            _displace(destfn)
        else:
            return

    log.debug(u'copying state file from {0} to {1}'.format(
        util.displayable_path(srcfn), util.displayable_path(destfn)
    ))
    util.copy(srcfn, destfn)
    return destfn


# Automatic migration when beets starts.

def automigrate():
    """Migrate the configuration, database, and state files. If any
    migration occurs, print out a notice with some helpful next steps.
    """
    config_fn = migrate_config()
    db_fn = migrate_db()
    migrate_state()

    if config_fn:
        ui.print_(ui.colorize('fuchsia', u'MIGRATED CONFIGURATION'))

        ui.print_(CONFIG_MIGRATED_MESSAGE.format(
            newconfig=util.displayable_path(config_fn))
        )
        if db_fn:
            ui.print_(DB_MIGRATED_MESSAGE.format(
                newdb=util.displayable_path(db_fn)
            ))

        ui.input_(ui.colorize('fuchsia', u'Press ENTER to continue:'))
        ui.print_()


# CLI command for explicit migration.

migrate_cmd = ui.Subcommand('migrate', help='convert legacy config')
def migrate_func(lib, opts, args):
    """Explicit command for migrating files. Existing files in each
    destination are moved aside.
    """
    config_fn = migrate_config(replace=True)
    if config_fn:
        log.info(u'Migrated configuration to: {0}'.format(
            util.displayable_path(config_fn)
        ))
    db_fn = migrate_db(replace=True)
    if db_fn:
        log.info(u'Migrated library database to: {0}'.format(
            util.displayable_path(db_fn)
        ))
    state_fn = migrate_state(replace=True)
    if state_fn:
        log.info(u'Migrated state file to: {0}'.format(
            util.displayable_path(state_fn)
        ))
migrate_cmd.func = migrate_func
