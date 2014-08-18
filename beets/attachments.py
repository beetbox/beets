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
from fnmatch import fnmatch

from beets import dbcore
from beets.dbcore.query import Query, AndQuery, MatchQuery, OrQuery, FalseQuery
from beets import util
from beets.util import normpath, displayable_path
from beets.util.functemplate import Template


log = logging.getLogger('beets')


AUDIO_EXTENSIONS = ['.mp3', '.ogg', '.mp4', '.m4a', '.mpc',
                    '.wma', '.wv', '.flac', '.aiff', '.ape']

DEFAULT_TEMPLATE = '${entity_prefix}${basename}'


def config(key):
    from beets import config
    return config['attachments'][key]


def track_separators():
    return config('track separators').get(list) + [os.sep]


def ref_type(entity):
    # FIXME prevents circular dependency
    from beets.library import Item, Album
    if isinstance(entity, Item):
        return 'item'
    elif isinstance(entity, Album):
        return 'album'


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
        self._entity = entity
        self._basename = None

    @property
    def entity(self):
        """Return the `Item` or `Album` we are attached to.
        """
        if self._entity is None and self.ref:
            query = dbcore.query.MatchQuery('id', self.ref)
            if self.ref_type == 'item':
                self._entity = self._db.items(query).get()
            elif self.ref_type == 'album':
                self._entity = self._db.albums(query).get()
        return self._entity

    @entity.setter
    def entity(self, entity):
        """Set the `ref` and `ref_type` properties so that
        `self.entity == entity`.
        """
        self._entity = entity
        # FIXME we cannot use self.ref = None because none is converted
        # to 0.
        self._values_fixed['ref'] = None
        self._values_fixed['ref_type'] = None

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

        if os.path.exists(dest):
            if overwrite:
                log.warn('overwrite attachment destination {0}'
                         .format(displayable_path(dest)))
            else:
                log.warn('attachment destination already exists: {0}'
                         .format(displayable_path(dest)))
                root, ext = os.path.splitext(dest)

                alternative = 0
                while os.path.exists(dest):
                    alternative += 1
                    dest = root + ".{0}".format(alternative) + ext

        if copy:
            util.copy(self.path, dest, overwrite)
            log.info('copy attachment to {0}'
                     .format(displayable_path(dest)))
        else:
            util.move(self.path, dest, overwrite)
            log.info('move attachment to {0}'
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
    def basename(self):
        """Return the value assigned to the attribute or calculate it
        from `AttachmentFactory.basename()`.
        """
        # TODO doc
        if self._basename is None:
            return AttachmentFactory.basename(self.path, self.entity)
        else:
            return self._basename

    @basename.setter
    def basename(self, basename):
        self._basename = basename

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
        for path_spec in reversed(config('paths').get(list)):
            if isinstance(path_spec, basestring):
                return Template(path_spec)

            if 'ext' in path_spec:
                template_str = '${ext_prefix}.' + path_spec.pop('ext')
            if 'path' in path_spec:
                template_str = path_spec.pop('path')
            queries = [MatchQuery(k, v) for k, v in path_spec.items()]
            if AndQuery(queries).match(self):
                return Template(template_str)
        return Template(DEFAULT_TEMPLATE)

    def store(self):
        self._validate()
        if self.id is None:
            self.add()
        else:
            super(Attachment, self).store()

    def _validate(self):
        if self.ref is None or self.ref_type is None:
            entity = self.entity
            if entity is None or entity.id is None:
                raise ValueError('{} must have an id'.format(entity))
            self.ref_type = ref_type(entity)
            self.ref = entity.id

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
        if ref_type(self.entity) == 'album':
            return self['entity_dir']
        elif ref_type(self.entity) == 'item':
            return self['track_base'] + track_separators()[0]

    @property
    def ext_prefix(self):
        """Absolute path to be used with different extensions.

        For albums this is `/path/to/album/dir/Album Artist - Album Name`.

        For tracks (i.e. items) this is the tracks path without the
        extension (`track_base`).
        """
        if ref_type(self.entity) == 'album':
            base = '{0} - {1}'.format(self.entity_mapping['albumartist'],
                                      self.entity_mapping['album'])
            return os.path.join(self['entity_dir'], base)
        elif ref_type(self.entity) == 'item':
            return self['track_base']

    @property
    def entity_dir(self):
        """The album directory for album attachments or the directory
        containing the track file for track attachments.

        The directory includes a trailing slash.
        """
        if ref_type(self.entity) == 'album':
            return self.entity.item_dir() + os.sep
        elif ref_type(self.entity) == 'item':
            return os.path.dirname(self.entity.path) + os.sep

    @property
    def track_base(self):
        """For tack attachments, return the track path without its extension.
        """
        if ref_type(self.entity) == 'item':
            return os.path.splitext(self.entity.path)[0]

    @property
    def basename(self):
        """See `attachment.basename`
        """
        return self.attachment.basename

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

    def create(self, path, type, entity=None):
        """Return a populated `Attachment` instance.

        The `path`, `type`, and `entity` properties of the attachment
        are set corresponding to the arguments.  In addition the method
        set retrieves meta data from registered collectors and and adds
        it as flexible attributes.

        If an attachment with the same path, ref, ref_type and type
        attributes already exists in the database, it returns that
        record

        Also sets the attachments's basename to the value returned by
        `Attachment.basename()`. Therefore, if the entity is moved
        later, we retain the basename instead of recalculating it
        through `attachment.basename`.
        """
        # TODO entity should not be optional
        attachment = Attachment(db=self._db, path=path,
                                entity=entity, type=type)
        if entity and entity.id:
            existing = self.find(AndQuery([
                MatchQuery('path', attachment.path),
                MatchQuery('ref', entity.id),
                MatchQuery('ref_type', ref_type(entity)),
                MatchQuery('type', attachment.type),
            ])).get()
            if existing is not None:
                attachment = existing

        attachment.basename = self.basename(path, entity)
        for key, value in self._collect_meta(type, attachment.path).items():
            attachment[key] = value
        return attachment

    def add(self, path, type, entity):
        """Create an attachment, add it to the database and return it.

        This is the same as calling `create()` and then adding the
        attachment to the database.
        """
        attachment = self.create(path, type, entity)
        attachment.add()
        return attachment

    def find(self, attachment_query=None, album_query=None, item_query=None):
        """Yield all attachments in the library matching
        `attachment_query` and their associated items matching
        `entity_query`.

        Calling `attachments(None, entity_query)` is equivalent to::

            library.albums(entity_query).attachments() + \
              library.items(entity_query).attachments()
        """
        # FIXME make this faster with joins
        queries = []
        from beets.library import Item, Album
        if album_query:
            queries.append(AttachmentEntityQuery(album_query, Album))
            if not item_query:
                queries.append(AttachmentEntityQuery(FalseQuery(), Item))
        if item_query:
            queries.append(AttachmentEntityQuery(item_query, Item))
            if not album_query:
                queries.append(AttachmentEntityQuery(FalseQuery(), Album))

        if queries:
            queries = [OrQuery(queries)]
        if attachment_query:
            queries.append(attachment_query)
        return self._db._fetch(Attachment, AndQuery(queries))

    def parse_and_find(self, *query_strings):
        from beets.library import get_query, Item, Album
        queries = {Item: [], Album: [], Attachment: []}
        for q in query_strings:
            if q.startswith('a:'):
                queries[Album].append(q[2:])
            elif q.startswith('t:'):
                queries[Item].append(q[2:])
            elif q.startswith('e:'):
                queries[Album].append(q[2:])
                queries[Item].append(q[2:])
            else:
                queries[Attachment].append(q)

        for klass, qs in queries.items():
            if qs:
                queries[klass] = get_query(qs, klass)
            else:
                queries[klass] = None
        return self.find(queries[Attachment], queries[Album], queries[Item])

    def discover(self, entity_or_prefix, local=None):
        """Return a list of non-audio file paths that start with the
        entity prefix.

        For albums the entity prefix is the album directory.  For items it
        is the item's path, excluding the extension.

        If the `local` argument is given the method returns a singleton
        list consisting of the path `entity_prefix + separator + local` if
        it exists. Multiple separators are tried depening on the entity
        type. For albums the only separator is the directory separator.
        For items the separtors are configured by `attachments.item_sep`
        """
        # TODO return attachments with create()
        # FIXME we need to handle paths as `entity_prefix` because of
        # the importer.
        prefix, dir = self.path_prefix(entity_or_prefix)
        if local is None:
            return self._discover_full(prefix, dir)
        else:
            return self._discover_local(prefix, local)

    def _discover_full(self, prefix, dir):
        discovered = []
        for dirpath, dirnames, filenames in os.walk(dir):
            for dirname in dirnames:
                path = os.path.join(dirpath, dirname)
                if not path.startswith(prefix):
                    dirnames.remove(dirname)

            for filename in filenames:
                path = os.path.join(dirpath, filename)
                ext = os.path.splitext(path)[1].lower()
                if path.startswith(prefix) and ext not in AUDIO_EXTENSIONS:
                    discovered.append(path)
        return discovered

    def _discover_local(self, prefix, local):
        seps = track_separators()
        if local[0] == '.':
            seps.append('')
        for sep in seps:
            path = prefix + sep + local
            if os.path.isfile(path):
                return [path]
        return []

    def detect(self, path, entity=None):
        """Yield a list of attachments for types registered with the path.

        The method uses the registered type detector functions to get
        a list of types for `path`. For each type it yields an attachment
        through `create`.
        """
        # TODO entity should not be optional
        # TODO update doc
        types = self._detect_plugin_types(path)
        types.update(self._detect_config_types(path))
        for type in types:
            yield self.create(path, type, entity)

    @classmethod
    def basename(cls, path, entity_or_prefix):
        """Compute the basename of a path with respect to the entity.

        Gets the prefix from `path_prefix()` and separators from the
        configuration. Tries to remove any combination of `prefix +
        separator` from the binning of `path` and return the remaining
        string. If this fails, the method strips all parent directories
        from `path`.

        Examples::
            path = '/root/track.cover.jpg'
            prefix = '/root/track.mp3'
            basename(path, prefix) == 'cover.jpg'

            item = Item(path='/root/track.mp3')
            basename(path, item) == 'cover.jpg'

            path = '/root/track/cover.jpg'
            basename(path, item) == 'cover.jpg'

            path = '/different/root/track - cover.jpg'
            basename(path, item) == 'track - cover.jpg'

            album = Album()  # with `item_dir() == '/album'`
            path = '/album/covers/front.jpg'
            basename(path, album) == 'covers/front.jpg'
        """
        # FIXME require entity_or_prefix to be Item or Album
        # TODO check os.path.basename(path) for prefixes
        if not entity_or_prefix:
            return os.path.basename(path)

        if ref_type(entity_or_prefix) == 'album':
            separators = [os.sep]
        else:
            separators = track_separators()

        prefix, _ = cls.path_prefix(entity_or_prefix)
        for sep in separators:
            if path.startswith(prefix + sep):
                return path[(len(prefix) + len(sep)):]
        return os.path.basename(path)

    @classmethod
    def path_prefix(cls, entity_or_prefix):
        # TODO doc
        if isinstance(entity_or_prefix, basestring):
            if os.path.isdir(entity_or_prefix):
                dir = entity_or_prefix
                prefix = dir
            else:
                prefix = os.path.splitext(entity_or_prefix)[0]
                dir = os.path.dirname(prefix)
        elif ref_type(entity_or_prefix) == 'album':
            try:
                dir = entity_or_prefix.item_dir()
                prefix = dir
            except ValueError:
                raise ValueError('Could not determine album directory')
        else:  # entity is track
            if entity_or_prefix.path is None:
                raise ValueError('Item has no path')
            prefix = os.path.splitext(entity_or_prefix.path)[0]
            dir = os.path.dirname(prefix)
        return (prefix, dir)

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

    def _detect_plugin_types(self, path):
        types = set()
        # TODO Make list unique
        for detector in self._detectors:
            try:
                type = detector(path)
                if type:
                    types.add(type)
            except:
                # TODO logging?
                pass
        return types

    def _detect_config_types(self, path):
        types = set()
        types_config = config('types')
        if not types_config.exists():
            return types

        basename = os.path.basename(path)
        for pattern, type in types_config.get(dict).items():
            if ((pattern[0] == '/' and pattern[-1] == '/'
                 and re.match(pattern[1:-1] + '$', basename))
                or fnmatch(basename, pattern)):
                 types.add(type)

        return types

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

    def __init__(self, entity_query, entity_class=None):
        self.query = entity_query
        self.entity_class = entity_class

    def match(self, attachment):
        entity = attachment.entity
        if self.entity_class and not isinstance(entity, self.entity_class):
            return False
        return self.query.match(entity)


class LibModelMixin(object):
    """Get associated attachments of `beets.library.LibModel` instances.
    """

    def attachments(self):
        return self._db._fetch(Attachment, AttachmentRefQuery(self))
