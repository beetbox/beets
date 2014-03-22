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
import json
import os.path
from argparse import ArgumentParser

from beets import library
from beets import dbcore


class Attachment(dbcore.db.Model):

    _fields = {
        'url':      dbcore.types.String(),
        'ref':      dbcore.types.Integer(),
        'ref_type': dbcore.types.String(),
        'type':     dbcore.types.String(),
    }
    _table = 'attachments'
    _flex_table = 'attachment_metadata'
    # FIXME do we need a _search_fields property?

    def __init__(self, db=None, libdir=None, **values):
        super(Attachment, self).__init__(db, **values)
        self.libdir = libdir

    @classmethod
    def _getters(cls):
        return []

    @property
    def location(self):
        """Return an url string with the ``file`` scheme omitted and
        resolved to an absolute path.
        """
        url = self.resolve()
        if url.scheme == 'file':
            return url.path
        else:
            return urlparse.urlunparse(url)

    @property
    def entity(self):
        """Return the ``Item`` or ``Album`` we are attached to.
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
        """Set the ``ref`` and ``ref_type`` properties so that
        ``self.entity() == entity``.
        """
        if isinstance(entity, library.Item):
            self.ref_type = 'item'
        elif isinstance(entity, library.Album):
            self.ref_type = 'album'
        else:
            raise ValueError('{} must be a Item or Album'.format(entity))

        if not entity.id:
            raise ValueError('{} must have an id',format(entity))
        self.ref = entity.id

    def move(self, destination=None, copy=False, force=False):
        """Moves the attachment from its original ``url`` to its
        destination URL.

        If `destination` is given it must be a path. If the path is relative, it is
        treated relative to the ``libdir``.

        If the destination is `None` the method retrieves a template
        from a `type -> template` map using the attachements type. It
        then evaluates the template in the context of the attachment and
        its associated entity.

        The method tries to retrieve the resource from ``self.url`` and
        saves it to ``destination``. If the destination already exists
        and ``force`` is ``False`` it raises an error. Otherwise the
        destination is overwritten and ``self.url`` is set to
        ``destination``.

        If ``copy`` is ``False`` and the original ``url`` pointed to a
        local file it removes that file.
        """
        # TODO implement
        raise NotImplementedError

    def resolve(self):
        """Return a url structure for the ``url`` property.

        This is similar to ``urlparse(attachment.url)``.  If ``url`` has
        no schema it defaults to ``file``. If the schema is ``file`` and
        the path is relative it is resolved relative to the ``libdir``.

        The return value is an instance of ``urlparse.ParseResult``.
        """
        (scheme, netloc, path, params, query, fragment) = \
                urlparse.urlparse(self.url, scheme='file')
        if not os.path.isabs(path):
            assert os.path.isabs(beetsdir)
            path = os.path.normpath(os.path.join(beetsdir, path))
        return urlparse.ParseResult(scheme, netloc, path, params, query, fragment)

    def _validate(self):
        # TODO integrate this into the `store()` method.
        assert self.entity
        assert re.match(r'^[a-zA-Z][-\w]*', self.type)
        urlparse.urlparse(self.url)

    def __getattr__(self, key):
        if key in self._fields.keys():
            return self[key]
        else:
            return object.__getattr__(self, key)

    def __setattr__(self, key, value):
        if key in self._fields.keys():
            self[key] = value
        else:
            object.__setattr__(self, key, value)


class AttachmentFactory(object):
    """Factory that creates or finds attachments in the database.

    Using this factory is the prefered way of creating attachments as it
    allows plugins to provide additional data.
    """

    def __init__(self, db=None, libdir=None):
        self._db = db
        self._libdir = libdir
        self._discoverers = []
        self._collectors = []

    def find(self, attachment_query=None, entity_query=None):
        """See Library documentation"""
        self._db.attachments(attachment_query, entity_query)

    def discover(self, url, entity=None):
        """Yield a list of attachments for types registered with that url.

        The method uses the registered type discoverer functions to get
        a list of types for ``path``. For each type it yields an
        attachment created with `create_with_type`.

        The scheme of the url defaults to ``file``.
        """
        url = urlparse.urlparse(url, scheme='file')
        if url.scheme != 'file':
            # TODO Discoverers are only required to handle paths. In the
            # future we might want to add the possibility to register
            # discoverers for general URLs.
            return

        for type in  self._discover_types(url.path):
            yield self.create(url.path, type, entity)

    def create(self, url, type, entity=None):
        """Return a populated ``Attachment`` instance.

        The ``url``, ``type``, and ``entity`` properties of the
        attachment are set corresponding to the arguments.  The method
        also populates the ``meta`` property with data retrieved from
        all registered collectors.
        """
        # TODO extend this to handle general urls
        attachment = Attachment(db=self._db, beetsdir=self._libdir,
                                url=url, type=type)
        if entity is not None:
            attachment.entity = entity
        for key, value in self._collect_meta(type, url).items():
            attachment[key] = value
        return attachment

    def register_discoverer(self, discover):
        """`discover` is a callable accepting the path of an attachment
        as its only argument. If it was able to determine the type it
        returns its name as a string. Otherwise it must return ``None``
        """
        self._discoverers.append(discover)

    def register_collector(self, collector):
        self._collectors.append(collector)

    def register_plugin(self, plugin):
        self.register_discoverer(plugin.attachment_discoverer)
        self.register_collector(plugin.attachment_collector)

    def _discover_types(self, url):
        types = []
        for discover in self._discoverers:
            try:
                type = discover(url)
                if type:
                    types.append(type)
            except:
                pass
        return types

    def _collect_meta(self, type, url):
        all_meta = {}
        for collector in self._collectors:
            meta = collector(type, url)
            if isinstance(meta, dict):
                all_meta.update(meta)
        return all_meta


class AttachmentCommand(ArgumentParser):
    """Abstract class to be used by plugins that deal with attachments.
    """

    name = None
    """Invoke the command if this string is given as the subcommand.

    If ``name`` is "myplugin" the command is run when using ``beet
    myplugin`` on the command line.
    """

    aliases = []
    """Alternative names to invoke this command by.
    """

    factory = None
    """Instance of ``AtachmentFactory``.

    This property will be set by beets before running the command.
    """

    def __init__(self):
        super(AttachmentCommand, self).__init__()

    def run(self, arguments):
        """Execute the command.

        :param arguments: A namespace object as returned by ``parse_args()``.
        """
        raise NotImplementedError

    def add_arguments(self, arguments):
        """Adds custom arguments with ``ArgumentParser.add_argument()``.

        The method is called by beets prior to calling ``parse_args``.
        """
        pass

class LibraryMixin(object):
    """Extends ``beets.library.Library`` with attachment queries.
    """

    def attachments(self, attachment_query=None, entity_query=None):
        """Yield all attachments in the library matching
        ``attachment_query`` and their associated items matching
        ``entity_query``.

        Calling `attachments(None, entity_query)` is equivalent to::

            library.albums(entity_query).attachments() + \
              library.items(entity_query).attachments()
        """
        # TODO implement
        raise NotImplementedError


class LibModelMixin(object):
    """Extends ``beets.library.LibModel`` with attachment queries.
    """

    def attachments(self):
        """Return a list of attachements associated to this model.
        """
        # TODO implement
        raise NotImplementedError
