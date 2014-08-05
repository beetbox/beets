# This file is part of beets.
# Copyright 2014, Thomas Scholtes.
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


import re
import os.path
import collections
import logging
from argparse import ArgumentParser

from beets import dbcore
from beets.dbcore.query import Query, AndQuery, MatchQuery
from beets import util
from beets.util import normpath, displayable_path
from beets.util.functemplate import Template


log = logging.getLogger('beets')


AUDIO_EXTENSIONS = ['.mp3', '.ogg', '.mp4', '.m4a', '.mpc',
                    '.wma', '.wv', '.flac', '.aiff', '.ape']


def ref_type(entity):
    # FIXME prevents circular dependency
    from beets.library import Item, Album
    if isinstance(entity, Item):
        return 'item'
    elif isinstance(entity, Album):
        return 'album'
    else:
        raise ValueError('{} must be a Item or Album'.format(entity))


class Attachment(dbcore.db.Model):
    """Represents an attachment in the database.

    An attachment has four properties that correspond to fields in the
    database: `path`, `type`, `ref`, and `ref_type`. Flexible
    attributes are accessed as `attachment[key]`.
    """

    _fields = {
        'id':       dbcore.types.Id(),
        'path':     dbcore.types.String(),
        'ref':      dbcore.types.Integer(),
        'ref_type': dbcore.types.String(),
        'type':     dbcore.types.String(),
    }
    _table = 'attachments'
    _flex_table = 'attachment_metadata'

    def __init__(self, db=None, entity=None, path=None, **values):
        super(Attachment, self).__init__(db, **values)
        if path is not None:
            self.path = path
        if entity is not None:
            self.entity = entity

    @property
    def entity(self):
        """Return the `Item` or `Album` we are attached to.
        """
        # TODO cache this for performance
        if self.ref is None or self.ref_type is None:
            return None
        query = dbcore.query.MatchQuery('id', self.ref)
        if self.ref_type == 'item':
            return self._db.items(query).get()
        elif self.ref_type == 'album':
            return self._db.albums(query).get()

    @entity.setter
    def entity(self, entity):
        """Set the `ref` and `ref_type` properties so that
        `self.entity == entity`.
        """
        self.ref_type = ref_type(entity)
        if not entity.id:
            raise ValueError('{} must have an id', format(entity))
        self.ref = entity.id

    def move(self, dest=None, copy=False, overwrite=False):
        """Moves the attachment from its original `path` to `dest` and
        updates `self.path`.

        The `dest` parameter defaults to the `destination property`. If
        it specified, it must be an absolute path.

        If the destination already exists and `overwrite` is `False` an
        alternative is chosen. For example if the destination is
        `/path/to/file.ext` then the alternative is
        `/path/to/file.1.ext`. If the alternative exists, too, the
        integer is increased until the path does not exist.

        If `copy` is `False` (the default) then the original file is deleted.
        """
        if dest is None:
            dest = self.destination

        if self.path == dest:
            return self.path

        if os.path.exists(dest) and not overwrite:
            root, ext = os.path.splitext(dest)
            log.warn('attachment destination already exists: {0}'
                     .format(displayable_path(dest)))

            alternative = 0
            while os.path.exists(dest):
                alternative += 1
                dest = root + ".{0}".format(alternative) + ext

        if copy:
            util.copy(self.path, dest, overwrite)
            log.warn('copy attachment to {0}'
                     .format(displayable_path(dest)))
        else:
            util.move(self.path, dest, overwrite)
            log.warn('move attachment to {0}'
                     .format(displayable_path(dest)))
        self.path = dest
        self.store()
        return self.path

    @property
    def path(self):
        path = self['path']
        if not os.path.isabs(path):
            libdir = self._db.directory
            assert os.path.isabs(libdir)
            path = os.path.normpath(os.path.join(libdir, path))
        return normpath(path)

    @path.setter
    def path(self, value):
        self['path'] = normpath(value)

    @property
    def destination(self):
        template = self._destination_template()
        mapping = DestinationTemplateMapping(self)
        path = template.substitute(mapping)
        if not os.path.isabs(path):
            path = mapping.entity_prefix + path
        # TODO replacing stuff
        return normpath(path)

    def _destination_template(self):
        # TODO template functions
        # FIXME circular dependency
        from beets import config
        for path_spec in reversed(config['attachment']['paths'].get()):
            if isinstance(path_spec, basestring):
                return Template(path_spec)

            if 'ext' in path_spec:
                template_str = '${ext_prefix}.' + path_spec.pop('ext')
            if 'path' in path_spec:
                template_str = path_spec.pop('path')
            queries = [MatchQuery(k, v) for k, v in path_spec.items()]
            if AndQuery(queries).match(self):
                return Template(template_str)

    def _validate(self):
        # TODO integrate this into the `store()` method.
        assert self.entity
        assert re.match(r'^[a-zA-Z][-\w]*', self.type)

    def __getattr__(self, key):
        # Called only if attribute was not found on self or in the class
        # tree.
        if key in self._fields.keys():
            return self[key]
        else:
            # Raises attribute error
            self.__getattribute__(key)

    def __setattr__(self, key, value):
        # Unlike dbcore.Model we do not provide attribute setters for
        # flexible fields.
        if key in self._fields.keys():
            self[key] = value
        else:
            object.__setattr__(self, key, value)

    @classmethod
    def _getters(cls):
        return {}


class DestinationTemplateMapping(collections.Mapping):
    """View of an attachment's attributes, its entity's attributes and
    additional computed values.

    If a key is requested it first looks for a property with the same
    name on the class and returns its value. It then looks for an
    attribute of the attachment and finally for an attribute of the
    attachment's entity.
    """

    @property
    def entity_prefix(self):
        """Absolute path prefix depending on the entity's path.

        For albums this is the album directory including a trailing
        directory separator.

        For tracks (i.e. items) this is the tracks path without the
        extension and ` - ` attached, e.g. `/path/to/track - `
        """
        if self.attachment.ref_type == 'album':
            return self['entity_dir']
        elif self.attachment.ref_type == 'item':
            return self['track_base'] + ' - '

    @property
    def ext_prefix(self):
        """Absolute path to be used with different extensions.

        For albums this is `/path/to/album/dir/Album Artist - Album Name`.

        For tracks (i.e. items) this is the tracks path without the
        extension (`track_base`).
        """
        if self.attachment.ref_type == 'album':
            base = '{0} - {1}'.format(self.entity_mapping['albumartist'],
                                      self.entity_mapping['album'])
            return os.path.join(self['entity_dir'], base)
        elif self.attachment.ref_type == 'item':
            return self['track_base']

    @property
    def entity_dir(self):
        """The album directory for album attachments or the directory
        containing the track file for track attachments.

        The directory includes a trailing slash.
        """
        if self.attachment.ref_type == 'album':
            return self.entity.item_dir() + os.sep
        elif self.attachment.ref_type == 'item':
            return os.path.dirname(self.entity.path) + os.sep

    @property
    def track_base(self):
        """For tack attachments, return the track path without its extension.
        """
        if self.attachment.ref_type == 'item':
            return os.path.splitext(self.entity.path)[0]

    @property
    def basename(self):
        """Filename of the attachment's path in its parent directory.
        """
        return os.path.basename(self.attachment.path)

    @property
    def ext(self):
        """Extension of the attachment's path without a leading dot.
        """
        ext = os.path.splitext(self.attachment.path)[1]
        if ext:
            ext = ext[1:]
        return ext

    @property
    def libdir(self):
        """Absolute path of the beets music directory.
        """
        return self.attachment._db.directory

    def __init__(self, attachment):
        self.attachment = attachment
        self.entity = attachment.entity
        self.entity_mapping = self.entity._formatted_mapping(for_path=True)

        self._getters = []
        for name, method in type(self).__dict__.items():
            if isinstance(method, property):
                self._getters.append(name)
        self._keys = set(attachment.keys(True))
        self._keys.union(self.entity_mapping.keys())
        self._keys.union(self._getters)

    def __getitem__(self, key):
        if key in self._getters:
            return self.__getattribute__(key)
        elif key in self.attachment:
            return self.attachment._get_formatted(key, for_path=True)
        elif key in self.entity_mapping:
            return self.entity[key]
        else:
            raise KeyError(key)

    def __iter__(self):
        return self._keys

    def __len__(self):
        return len(self._keys)


class AttachmentFactory(object):
    """Create and find attachments in the database.

    Using this factory is the prefered way of creating attachments as it
    allows plugins to provide additional data.
    """

    def __init__(self, db=None):
        self._db = db
        self._libdir = db.directory
        self._detectors = []
        self._collectors = []

    def find(self, attachment_query=None, entity_query=None):
        """Yield all attachments in the library matching
        `attachment_query` and their associated items matching
        `entity_query`.

        Calling `attachments(None, entity_query)` is equivalent to::

            library.albums(entity_query).attachments() + \
              library.items(entity_query).attachments()
        """
        # FIXME make this faster with joins
        queries = [AttachmentEntityQuery(entity_query)]
        if attachment_query:
            queries.append(attachment_query)
        return self._db._fetch(Attachment, AndQuery(queries))

    def detect(self, path, entity=None):
        """Yield a list of attachments for types registered with the path.

        The method uses the registered type detector functions to get
        a list of types for `path`. For each type it yields an attachment
        through `create`.
        """
        for type in self._detect_types(path):
            yield self.create(path, type, entity)

    def discover(self, entity, local=None):
        """Return a list of non-audio files whose path start with the
        entity prefix.

        For albums the entity prefix is the album directory.  For items it
        is the item's path, excluding the extension.

        If the `local` argument is given the method returns a singleton
        list consisting of the path `entity_preifix + separator + local` if
        it exists. Multiple separators are tried depening on the entity
        type. For albums the only separator is the directory separator.
        For items the separtors are configured by `attachments.item_sep`
        """
        if local is None:
            return self._discover_full(entity)
        else:
            return self._discover_local(entity, local)

    def _discover_full(self, entity):
        if ref_type(entity) == 'album':
            entity_dir = entity.item_dir()
            entity_prefix = entity_dir
        else:
            entity_dir = os.path.dirname(entity.path)
            entity_prefix = os.path.splitext(entity.path)[0]

        discovered = []
        for dirpath, dirnames, filenames in os.walk(entity_dir):
            for dirname in dirnames:
                path = os.path.join(dirpath, dirname)
                if not path.startswith(entity_prefix):
                    dirnames.remove(dirname)

            for filename in filenames:
                path = os.path.join(dirpath, filename)
                ext = os.path.splitext(path)[1].lower()
                if path.startswith(entity_prefix) \
                   and ext not in AUDIO_EXTENSIONS:
                    discovered.append(path)
        return discovered

    def _discover_local(self, entity, local):
        if ref_type(entity) == 'album':
            seps = [os.sep]
            entity_prefix = entity.item_dir()
        else:
            # TODO make this configurable
            seps = [os.sep, ' - ', '', ' ', '-', '_', '.']
            entity_prefix = os.path.splitext(entity.path)[0]

        for sep in seps:
            path = entity_prefix + sep + local
            if os.path.isfile(path):
                return [path]
        return []

    def create(self, path, type, entity=None):
        """Return a populated `Attachment` instance.

        The `path`, `type`, and `entity` properties of the attachment
        are set corresponding to the arguments.  In addition the method
        set retrieves meta data from registered collectors and and adds
        it as flexible attributes
        """
        attachment = Attachment(db=self._db, path=path,
                                entity=entity, type=type)
        for key, value in self._collect_meta(type, attachment.path).items():
            attachment[key] = value
        return attachment

    def add(self, path, type, entity):
        """Create an attachment, add it to the database and return it.

        This is the same as calling `create()` and then adding the
        attachment to the database.
        """
        attachment = self.create(path, type, entity)
        self._db.add(attachment)
        return attachment

    def register_detector(self, detector):
        """`detector` is a callable accepting the path of an attachment
        as its only argument. If it was able to determine the type it
        returns its name as a string. Otherwise it must return `None`
        """
        self._detectors.append(detector)

    def register_collector(self, collector):
        """`collector` is a callable accepting the type and path of an
        attachment as its arguments. The `collector` should return a
        dictionary of metadata it was able to retrieve from the source
        or `None`.
        """
        self._collectors.append(collector)

    def register_plugins(self, plugins):
        for plugin in plugins:
            if hasattr(plugin, 'attachment_detector'):
                self.register_detector(plugin.attachment_detector)
            if hasattr(plugin, 'attachment_collector'):
                self.register_collector(plugin.attachment_collector)

    def _detect_types(self, path):
        """Yield a list of types registered for the path.

        Uses the functions from `register_detector` and the
        `attachments.types` configuration.
        """
        # FIXME circular dependency
        from beets import config
        for detector in self._detectors:
            try:
                type = detector(path)
                if type:
                    yield type
            except:
                # TODO logging?
                pass

        types_config = config['attachments']['types']
        if types_config.exists():
            for matcher, type in types_config.get(dict).items():
                if re.match(matcher, path):
                    yield type

    def _collect_meta(self, type, path):
        all_meta = {}
        for collector in self._collectors:
            try:
                # TODO maybe we should provide file handle for checking
                # content
                meta = collector(type, path)
                if isinstance(meta, dict):
                    all_meta.update(meta)
            except:
                # TODO logging?
                pass
        return all_meta


class AttachmentCommand(ArgumentParser):
    """Abstract class to be used by plugins that deal with attachments.
    """

    name = None
    """Invoke the command if this string is given as the subcommand.

    If `name` is "myplugin" the command is run when using `beet
    myplugin` on the command line.
    """

    aliases = []
    """Alternative names to invoke this command by.
    """

    factory = None
    """Instance of `AtachmentFactory`.

    This property will be set by beets before running the command.
    """

    def __init__(self):
        super(AttachmentCommand, self).__init__()

    def run(self, arguments):
        """Execute the command.

        :param arguments: A namespace object as returned by `parse_args()`.
        """
        raise NotImplementedError

    def add_arguments(self, arguments):
        """Adds custom arguments with `ArgumentParser.add_argument()`.

        The method is called by beets prior to calling `parse_args`.
        """
        pass


class AttachmentRefQuery(Query):
    """Matches any attachment whose entity is `entity`.
    """

    def __init__(self, entity):
        self.entity = entity

    def clause(self):
        return ('(ref = ? AND ref_type = ?)',
                (self.entity.id, ref_type(self.entity)))

    def match(self, attachment):
        return attachment.entity == self.entity


class AttachmentEntityQuery(Query):
    """Matches any attachment whose entity matches `entity_query`.
    """

    def __init__(self, entity_query):
        self.query = entity_query

    def match(self, attachment):
        if self.query is not None:
            return self.query.match(attachment.query)
        else:
            return True


class LibModelMixin(object):
    """Get associated attachments of `beets.library.LibModel` instances.
    """

    def attachments(self):
        return self._db._fetch(Attachment, AttachmentRefQuery(self))
