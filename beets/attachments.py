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
import urlparse
from argparse import ArgumentParser

from beets import dbcore
from beets.dbcore.query import Query, AndQuery


class Attachment(dbcore.db.Model):
    """Represents an attachment in the database.

    An attachment has four properties that correspond to fields in the
    database: `url`, `type`, `ref`, and `ref_type`. Flexible
    attributes are accessed as `attachment[key]`.
    """

    _fields = {
        'id':       dbcore.types.Id(),
        'url':      dbcore.types.String(),
        'ref':      dbcore.types.Integer(),
        'ref_type': dbcore.types.String(),
        'type':     dbcore.types.String(),
    }
    _table = 'attachments'
    _flex_table = 'attachment_metadata'

    def __init__(self, db=None, libdir=None, path=None, **values):
        if path is not None:
            values['url'] = path
        super(Attachment, self).__init__(db, **values)
        self.libdir = libdir

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
        # FIXME prevents circular dependency
        from beets.library import Item, Album
        if isinstance(entity, Item):
            self.ref_type = 'item'
        elif isinstance(entity, Album):
            self.ref_type = 'album'
        else:
            raise ValueError('{} must be a Item or Album'.format(entity))

        if not entity.id:
            raise ValueError('{} must have an id', format(entity))
        self.ref = entity.id

    def move(self, destination=None, copy=False, force=False):
        """Moves the attachment from its original `url` to its
        destination URL.

        If `destination` is given it must be a path. If the path is
        relative, it is treated relative to the `libdir`.

        If the destination is `None` the method retrieves a template
        from a `type -> template` map using the attachements type. It
        then evaluates the template in the context of the attachment and
        its associated entity.

        The method tries to retrieve the resource from `self.url` and
        saves it to `destination`. If the destination already exists and
        `force` is `False` it raises an error. Otherwise the destination
        is overwritten and `self.url` is set to `destination`.

        If `copy` is `False` and the original `url` pointed to a local
        file it removes that file.
        """
        # TODO implement
        raise NotImplementedError

    @property
    def path(self):
        if self.resolve().scheme == 'file':
            return self.resolve().path

    @path.setter
    def path(self, value):
        self.url = value

    def resolve(self):
        """Return a url structure for the `url` property.

        This is similar to `urlparse(attachment.url)`.  If `url` has
        no schema it defaults to `file`. If the schema is `file` and
        the path is relative it is resolved relative to the `libdir`.

        The return value is an instance of `urlparse.ParseResult`.
        """
        (scheme, netloc, path, params, query, fragment) = \
            urlparse.urlparse(self.url, scheme='file')
        # if not os.path.isabs(path):
        #     assert os.path.isabs(beetsdir)
        #     path = os.path.normpath(os.path.join(beetsdir, path))
        return urlparse.ParseResult(scheme, netloc, path,
                                    params, query, fragment)

    def _validate(self):
        # TODO integrate this into the `store()` method.
        assert self.entity
        assert re.match(r'^[a-zA-Z][-\w]*', self.type)
        urlparse.urlparse(self.url)

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

    def __init__(self, db=None, libdir=None):
        self._db = db
        self._libdir = libdir
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

    def discover(self, url, entity=None):
        """Yield a list of attachments for types registered with the url.

        The method uses the registered type discoverer functions to get
        a list of types for `url`. For each type it yields an attachment
        created with `create_with_type`.

        The scheme of the url defaults to `file`.
        """
        url = urlparse.urlparse(url, scheme='file')
        if url.scheme != 'file':
            # TODO Discoverers are only required to handle paths. In the
            # future we might want to add the possibility to register
            # discoverers for general URLs.
            return

        for type in self._discover_types(url.path):
            yield self.create(url.path, type, entity)

    def create(self, url, type, entity=None):
        """Return a populated `Attachment` instance.

        The `url`, `type`, and `entity` properties of the attachment are
        set corresponding to the arguments.  The method also set
        flexible attributes for metadata retrieved from all registered
        collectors.
        """
        # TODO extend this to handle general urls
        attachment = Attachment(db=self._db, libdir=self._libdir,
                                url=url, type=type)
        if entity is not None:
            attachment.entity = entity
        for key, value in self._collect_meta(type, url).items():
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

    def register_plugin(self, plugin):
        self.register_discoverer(plugin.attachment_discoverer)
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


class AttachmentEntityQuery(Query):

    def __init__(self, query):
        self.query = query

    def match(self, attachment):
        if self.query is not None:
            return self.query.match(attachment.entity)
        else:
            return True


class LibModelMixin(object):
    """Get associated attachments of `beets.library.LibModel` instances.
    """

    def attachments(self):
        # TODO implement
        raise NotImplementedError
