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
from argparse import ArgumentParser
import os.path

from beets import dbcore
from beets.dbcore.query import Query, AndQuery


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
        if self.ref is None or self.ref_type is None:
            return None
        query = dbcore.query.MatchQuery('id', self.ref)
        if self.ref_type == 'item':
            self._db.items(query)
        elif self.ref_type == 'album':
            self._db.albums(query)

    @entity.setter
    def entity(self, entity):
        """Set the `ref` and `ref_type` properties so that
        `self.entity == entity`.
        """
        self.ref_type = ref_type(entity)
        if not entity.id:
            raise ValueError('{} must have an id', format(entity))
        self.ref = entity.id

    def move(self, destination=None, copy=False, force=False):
        """Moves the attachment from its original `path` to
        `destination` and updates `self.path`.

        If `destination` is given it must be a path. If the path is
        relative, it is treated relative to the `libdir`.

        TODO: Review next paragraph.
        If the destination is `None` the method retrieves a template
        from a `type -> template` map using the attachements type. It
        then evaluates the template in the context of the attachment and
        its associated entity.

        If the destination already exists and `force` is `False` it
        raises an error.

        If `copy` is `False` (the default) then the original file is deleted.
        """
        # TODO implement
        raise NotImplementedError

    @property
    def path(self):
        path = self['path']
        if not os.path.isabs(path):
            libdir = self._db.directory
            assert os.path.isabs(libdir)
            path = os.path.normpath(os.path.join(libdir, path))
        return path

    @path.setter
    def path(self, value):
        self['path'] = value


    def _validate(self):
        # TODO integrate this into the `store()` method.
        assert self.entity
        assert re.match(r'^[a-zA-Z][-\w]*', self.type)

    def __getattr__(self, key):
        if key in self._fields.keys():
            return self[key]
        else:
            object.__getattr__(self, key)

    def __setattr__(self, key, value):
        # Unlike dbcore.Model we do not provide attribute setters for
        # flexible fields.
        if key in self._fields.keys():
            self[key] = value
        else:
            object.__setattr__(self, key, value)

    @classmethod
    def _getters(cls):
        return []


class AttachmentFactory(object):
    """Create and find attachments in the database.

    Using this factory is the prefered way of creating attachments as it
    allows plugins to provide additional data.
    """

    def __init__(self, db=None):
        self._db = db
        self._libdir = db.directory
        self._discoverers = []
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

    def discover(self, path, entity=None):
        """Yield a list of attachments for types registered with the path.

        The method uses the registered type discoverer functions to get
        a list of types for `path`. For each type it yields an attachment
        through `create`.
        """
        for type in self._discover_types(path):
            yield self.create(path, type, entity)

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

    def register_discoverer(self, discover):
        """`discover` is a callable accepting the path of an attachment
        as its only argument. If it was able to determine the type it
        returns its name as a string. Otherwise it must return `None`
        """
        self._discoverers.append(discover)

    def register_collector(self, collector):
        """`collector` is a callable accepting the type and path of an
        attachment as its arguments. The `collector` should return a
        dictionary of metadata it was able to retrieve from the source
        or `None`.
        """
        self._collectors.append(collector)

    def register_plugins(self, plugins):
        for plugin in plugins:
            if hasattr(plugin, 'attachment_discoverer'):
                self.register_discoverer(plugin.attachment_discoverer)
            if hasattr(plugin, 'attachment_collector'):
                self.register_collector(plugin.attachment_collector)

    def _discover_types(self, path):
        types = []
        for discover in self._discoverers:
            try:
                type = discover(path)
                if type:
                    types.append(type)
            except:
                # TODO logging?
                pass
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
