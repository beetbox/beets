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

"""The core data store and collection logic for beets.
"""
import os
import sys
import logging
import shlex
import unicodedata
import time
import re
from unidecode import unidecode
from beets.mediafile import MediaFile, MutagenError, UnreadableFileError
from beets import plugins
from beets import util
from beets.util import bytestring_path, syspath, normpath, samefile
from beets.util.functemplate import Template
from beets import dbcore
from beets.dbcore import types
import beets


log = logging.getLogger('beets')


# Library-specific query types.

class PathQuery(dbcore.FieldQuery):
    """A query that matches all items under a given path."""
    def __init__(self, field, pattern, fast=True):
        super(PathQuery, self).__init__(field, pattern, fast)

        # Match the path as a single file.
        self.file_path = util.bytestring_path(util.normpath(pattern))
        # As a directory (prefix).
        self.dir_path = util.bytestring_path(os.path.join(self.file_path, ''))

    def match(self, item):
        return (item.path == self.file_path) or \
            item.path.startswith(self.dir_path)

    def clause(self):
        dir_pat = buffer(self.dir_path + '%')
        file_blob = buffer(self.file_path)
        return '({0} = ?) || ({0} LIKE ?)'.format(self.field), \
               (file_blob, dir_pat)


# Library-specific field types.


class DateType(types.Type):
    sql = u'REAL'
    query = dbcore.query.DateQuery
    null = 0.0

    def format(self, value):
        return time.strftime(beets.config['time_format'].get(unicode),
                             time.localtime(value or 0))

    def parse(self, string):
        try:
            # Try a formatted date string.
            return time.mktime(
                time.strptime(string, beets.config['time_format'].get(unicode))
            )
        except ValueError:
            # Fall back to a plain timestamp number.
            try:
                return float(string)
            except ValueError:
                return self.null


class PathType(types.Type):
    sql = u'BLOB'
    query = PathQuery

    def format(self, value):
        return util.displayable_path(value)

    def parse(self, string):
        return normpath(bytestring_path(string))

    def normalize(self, value):
        if isinstance(value, unicode):
            # Paths stored internally as encoded bytes.
            return bytestring_path(value)

        elif isinstance(value, buffer):
            # SQLite must store bytestings as buffers to avoid decoding.
            # We unwrap buffers to bytes.
            return bytes(value)

        else:
            return value


class MusicalKey(types.String):
    """String representing the musical key of a song.

    The standard format is C, Cm, C#, C#m, etc.
    """
    ENHARMONIC = {
        r'db': 'c#',
        r'eb': 'd#',
        r'gb': 'f#',
        r'ab': 'g#',
        r'bb': 'a#',
    }

    def parse(self, key):
        key = key.lower()
        for flat, sharp in self.ENHARMONIC.items():
            key = re.sub(flat, sharp, key)
        key = re.sub(r'[\W\s]+minor', 'm', key)
        return key.capitalize()

    def normalize(self, key):
        if key is None:
            return None
        else:
            return self.parse(key)


# Special path format key.
PF_KEY_DEFAULT = 'default'


# A little SQL utility.
def _orelse(exp1, exp2):
    """Generates an SQLite expression that evaluates to exp1 if exp1 is
    non-null and non-empty or exp2 otherwise.
    """
    return ("""(CASE {0} WHEN NULL THEN {1}
                         WHEN "" THEN {1}
                         ELSE {0} END)""").format(exp1, exp2)


# Exceptions.

class FileOperationError(Exception):
    """Indicates an error when interacting with a file on disk.
    Possibilities include an unsupported media type, a permissions
    error, and an unhandled Mutagen exception.
    """
    def __init__(self, path, reason):
        """Create an exception describing an operation on the file at
        `path` with the underlying (chained) exception `reason`.
        """
        super(FileOperationError, self).__init__(path, reason)
        self.path = path
        self.reason = reason

    def __unicode__(self):
        """Get a string representing the error. Describes both the
        underlying reason and the file path in question.
        """
        return u'{0}: {1}'.format(
            util.displayable_path(self.path),
            unicode(self.reason)
        )

    def __str__(self):
        return unicode(self).encode('utf8')


class ReadError(FileOperationError):
    """An error while reading a file (i.e. in `Item.read`).
    """
    def __unicode__(self):
        return u'error reading ' + super(ReadError, self).__unicode__()


class WriteError(FileOperationError):
    """An error while writing a file (i.e. in `Item.write`).
    """
    def __unicode__(self):
        return u'error writing ' + super(WriteError, self).__unicode__()


# Item and Album model classes.

class LibModel(dbcore.Model):
    """Shared concrete functionality for Items and Albums.
    """
    _bytes_keys = ('path', 'artpath')

    def _template_funcs(self):
        funcs = DefaultTemplateFunctions(self, self._db).functions()
        funcs.update(plugins.template_funcs())
        return funcs

    def store(self):
        super(LibModel, self).store()
        plugins.send('database_change', lib=self._db)

    def remove(self):
        super(LibModel, self).remove()
        plugins.send('database_change', lib=self._db)

    def add(self, lib=None):
        super(LibModel, self).add(lib)
        plugins.send('database_change', lib=self._db)


class Item(LibModel):
    _table = 'items'
    _flex_table = 'item_attributes'
    _fields = {
        'id':       types.PRIMARY_ID,
        'path':     PathType(),
        'album_id': types.FOREIGN_ID,

        'title':                types.STRING,
        'artist':               types.STRING,
        'artist_sort':          types.STRING,
        'artist_credit':        types.STRING,
        'album':                types.STRING,
        'albumartist':          types.STRING,
        'albumartist_sort':     types.STRING,
        'albumartist_credit':   types.STRING,
        'genre':                types.STRING,
        'composer':             types.STRING,
        'grouping':             types.STRING,
        'year':                 types.PaddedInt(4),
        'month':                types.PaddedInt(2),
        'day':                  types.PaddedInt(2),
        'track':                types.PaddedInt(2),
        'tracktotal':           types.PaddedInt(2),
        'disc':                 types.PaddedInt(2),
        'disctotal':            types.PaddedInt(2),
        'lyrics':               types.STRING,
        'comments':             types.STRING,
        'bpm':                  types.INTEGER,
        'comp':                 types.BOOLEAN,
        'mb_trackid':           types.STRING,
        'mb_albumid':           types.STRING,
        'mb_artistid':          types.STRING,
        'mb_albumartistid':     types.STRING,
        'albumtype':            types.STRING,
        'label':                types.STRING,
        'acoustid_fingerprint': types.STRING,
        'acoustid_id':          types.STRING,
        'mb_releasegroupid':    types.STRING,
        'asin':                 types.STRING,
        'catalognum':           types.STRING,
        'script':               types.STRING,
        'language':             types.STRING,
        'country':              types.STRING,
        'albumstatus':          types.STRING,
        'media':                types.STRING,
        'albumdisambig':        types.STRING,
        'disctitle':            types.STRING,
        'encoder':              types.STRING,
        'rg_track_gain':        types.NULL_FLOAT,
        'rg_track_peak':        types.NULL_FLOAT,
        'rg_album_gain':        types.NULL_FLOAT,
        'rg_album_peak':        types.NULL_FLOAT,
        'original_year':        types.PaddedInt(4),
        'original_month':       types.PaddedInt(2),
        'original_day':         types.PaddedInt(2),
        'initial_key':          MusicalKey(),

        'length':      types.FLOAT,
        'bitrate':     types.ScaledInt(1000, u'kbps'),
        'format':      types.STRING,
        'samplerate':  types.ScaledInt(1000, u'kHz'),
        'bitdepth':    types.INTEGER,
        'channels':    types.INTEGER,
        'mtime':       DateType(),
        'added':       DateType(),
    }

    _search_fields = ('artist', 'title', 'comments',
                      'album', 'albumartist', 'genre')

    _media_fields = set(MediaFile.readable_fields()) \
        .intersection(_fields.keys())
    """Set of item fields that are backed by `MediaFile` fields.

    Any kind of field (fixed, flexible, and computed) may be a media
    field. Only these fields are read from disk in `read` and written in
    `write`.
    """

    @classmethod
    def _getters(cls):
        getters = plugins.item_field_getters()
        getters['singleton'] = lambda i: i.album_id is None
        return getters

    @classmethod
    def from_path(cls, path):
        """Creates a new item from the media file at the specified path.
        """
        # Initiate with values that aren't read from files.
        i = cls(album_id=None)
        i.read(path)
        i.mtime = i.current_mtime()  # Initial mtime.
        return i

    def __setitem__(self, key, value):
        """Set the item's value for a standard field or a flexattr.
        """
        # Encode unicode paths and read buffers.
        if key == 'path':
            if isinstance(value, unicode):
                value = bytestring_path(value)
            elif isinstance(value, buffer):
                value = str(value)

        if key in MediaFile.fields():
            self.mtime = 0  # Reset mtime on dirty.

        super(Item, self).__setitem__(key, value)

    def update(self, values):
        """Set all key/value pairs in the mapping. If mtime is
        specified, it is not reset (as it might otherwise be).
        """
        super(Item, self).update(values)
        if self.mtime == 0 and 'mtime' in values:
            self.mtime = values['mtime']

    def get_album(self):
        """Get the Album object that this item belongs to, if any, or
        None if the item is a singleton or is not associated with a
        library.
        """
        if not self._db:
            return None
        return self._db.get_album(self)

    # Interaction with file metadata.

    def read(self, read_path=None):
        """Read the metadata from the associated file.

        If `read_path` is specified, read metadata from that file
        instead. Updates all the properties in `_media_fields`
        from the media file.

        Raises a `ReadError` if the file could not be read.
        """
        if read_path is None:
            read_path = self.path
        else:
            read_path = normpath(read_path)
        try:
            mediafile = MediaFile(syspath(read_path))
        except (OSError, IOError, UnreadableFileError) as exc:
            raise ReadError(read_path, exc)

        for key in self._media_fields:
            value = getattr(mediafile, key)
            if isinstance(value, (int, long)):
                # Filter values wider than 64 bits (in signed representation).
                # SQLite cannot store them. py26: Post transition, we can use:
                # value.bit_length() > 63
                if abs(value) >= 2 ** 63:
                    value = 0
            self[key] = value

        # Database's mtime should now reflect the on-disk value.
        if read_path == self.path:
            self.mtime = self.current_mtime()

        self.path = read_path

    def write(self, path=None):
        """Write the item's metadata to a media file.

        All fields in `_media_fields` are written to disk according to
        the values on this object.

        Can raise either a `ReadError` or a `WriteError`.
        """
        if path is None:
            path = self.path
        else:
            path = normpath(path)

        plugins.send('write', item=self, path=path)

        try:
            mediafile = MediaFile(syspath(path),
                                  id3v23=beets.config['id3v23'].get(bool))
        except (OSError, IOError) as exc:
            raise ReadError(self.path, exc)

        mediafile.update(self)
        try:
            mediafile.save()
        except (OSError, IOError, MutagenError) as exc:
            raise WriteError(self.path, exc)

        # The file has a new mtime.
        if path == self.path:
            self.mtime = self.current_mtime()
        plugins.send('after_write', item=self, path=path)

    def try_write(self, path=None):
        """Calls `write()` but catches and logs `FileOperationError`
        exceptions.

        Returns `False` an exception was caught and `True` otherwise.
        """
        try:
            self.write(path)
            return True
        except FileOperationError as exc:
            log.error(exc)
            return False

    # Files themselves.

    def move_file(self, dest, copy=False):
        """Moves or copies the item's file, updating the path value if
        the move succeeds. If a file exists at ``dest``, then it is
        slightly modified to be unique.
        """
        if not util.samefile(self.path, dest):
            dest = util.unique_path(dest)
        if copy:
            util.copy(self.path, dest)
            plugins.send("item_copied", item=self, source=self.path,
                         destination=dest)
        else:
            plugins.send("before_item_moved", item=self, source=self.path,
                         destination=dest)
            util.move(self.path, dest)
            plugins.send("item_moved", item=self, source=self.path,
                         destination=dest)

        # Either copying or moving succeeded, so update the stored path.
        self.path = dest

    def current_mtime(self):
        """Returns the current mtime of the file, rounded to the nearest
        integer.
        """
        return int(os.path.getmtime(syspath(self.path)))

    # Model methods.

    def remove(self, delete=False, with_album=True):
        """Removes the item. If `delete`, then the associated file is
        removed from disk. If `with_album`, then the item's album (if
        any) is removed if it the item was the last in the album.
        """
        super(Item, self).remove()

        # Remove the album if it is empty.
        if with_album:
            album = self.get_album()
            if album and not album.items():
                album.remove(delete, False)

        # Send a 'item_removed' signal to plugins
        plugins.send('item_removed', item=self)

        # Delete the associated file.
        if delete:
            util.remove(self.path)
            util.prune_dirs(os.path.dirname(self.path), self._db.directory)

        self._db._memotable = {}

    def move(self, copy=False, basedir=None, with_album=True):
        """Move the item to its designated location within the library
        directory (provided by destination()). Subdirectories are
        created as needed. If the operation succeeds, the item's path
        field is updated to reflect the new location.

        If copy is True, moving the file is copied rather than moved.

        basedir overrides the library base directory for the
        destination.

        If the item is in an album, the album is given an opportunity to
        move its art. (This can be disabled by passing
        with_album=False.)

        The item is stored to the database if it is in the database, so
        any dirty fields prior to the move() call will be written as a
        side effect. You probably want to call save() to commit the DB
        transaction.
        """
        self._check_db()
        dest = self.destination(basedir=basedir)

        # Create necessary ancestry for the move.
        util.mkdirall(dest)

        # Perform the move and store the change.
        old_path = self.path
        self.move_file(dest, copy)
        self.store()

        # If this item is in an album, move its art.
        if with_album:
            album = self.get_album()
            if album:
                album.move_art(copy)
                album.store()

        # Prune vacated directory.
        if not copy:
            util.prune_dirs(os.path.dirname(old_path), self._db.directory)

    # Templating.

    def _formatted_mapping(self, for_path=False):
        """Get a mapping containing string-formatted values from either
        this item or the associated album, if any.
        """
        return FormattedItemMapping(self, for_path)

    def destination(self, fragment=False, basedir=None, platform=None,
                    path_formats=None):
        """Returns the path in the library directory designated for the
        item (i.e., where the file ought to be). fragment makes this
        method return just the path fragment underneath the root library
        directory; the path is also returned as Unicode instead of
        encoded as a bytestring. basedir can override the library's base
        directory for the destination.
        """
        self._check_db()
        platform = platform or sys.platform
        basedir = basedir or self._db.directory
        path_formats = path_formats or self._db.path_formats

        # Use a path format based on a query, falling back on the
        # default.
        for query, path_format in path_formats:
            if query == PF_KEY_DEFAULT:
                continue
            query = get_query(query, type(self))
            if query.match(self):
                # The query matches the item! Use the corresponding path
                # format.
                break
        else:
            # No query matched; fall back to default.
            for query, path_format in path_formats:
                if query == PF_KEY_DEFAULT:
                    break
            else:
                assert False, "no default path format"
        if isinstance(path_format, Template):
            subpath_tmpl = path_format
        else:
            subpath_tmpl = Template(path_format)

        # Evaluate the selected template.
        subpath = self.evaluate_template(subpath_tmpl, True)

        # Prepare path for output: normalize Unicode characters.
        if platform == 'darwin':
            subpath = unicodedata.normalize('NFD', subpath)
        else:
            subpath = unicodedata.normalize('NFC', subpath)

        if beets.config['asciify_paths']:
            subpath = unidecode(subpath)

        # Truncate components and remove forbidden characters.
        subpath = util.sanitize_path(subpath, self._db.replacements)

        # Encode for the filesystem.
        if not fragment:
            subpath = bytestring_path(subpath)

        # Preserve extension.
        _, extension = os.path.splitext(self.path)
        if fragment:
            # Outputting Unicode.
            extension = extension.decode('utf8', 'ignore')
        subpath += extension.lower()

        # Truncate too-long components.
        maxlen = beets.config['max_filename_length'].get(int)
        if not maxlen:
            # When zero, try to determine from filesystem.
            maxlen = util.max_filename_length(self._db.directory)
        subpath = util.truncate_path(subpath, maxlen)

        if fragment:
            return subpath
        else:
            return normpath(os.path.join(basedir, subpath))


class FormattedItemMapping(dbcore.db.FormattedMapping):
    """A `dict`-like formatted view of an item that inherits album fields.

    The accessor ``mapping[key]`` returns the formated version of either
    ``item[key]`` or ``album[key]``. Here `album` is the album
    associated to `item` if it exists.
    """
    def __init__(self, item, for_path=False):
        super(FormattedItemMapping, self).__init__(item, for_path)
        self.album = item.get_album()
        self.album_keys = []
        if self.album:
            for key in self.album.keys(True):
                if key in Album.item_keys or key not in item._fields.keys():
                    self.album_keys.append(key)
        self.all_keys = set(self.model_keys).union(self.album_keys)

    def _get(self, key):
        """Get the value for a key, either from the album or the item.
        Raise a KeyError for invalid keys.
        """
        if key in self.album_keys:
            return self.album._get_formatted(key, self.for_path)
        elif key in self.model_keys:
            return self.model._get_formatted(key, self.for_path)
        else:
            raise KeyError(key)

    def __getitem__(self, key):
        """Get the value for a key. Certain unset values are remapped.
        """
        value = self._get(key)

        # `artist` and `albumartist` fields fall back to one another.
        # This is helpful in path formats when the album artist is unset
        # on as-is imports.
        if key == 'artist' and not value:
            return self._get('albumartist')
        elif key == 'albumartist' and not value:
            return self._get('artist')
        else:
            return value

    def __iter__(self):
        return iter(self.all_keys)

    def __len__(self):
        return len(self.all_keys)


class Album(LibModel):
    """Provides access to information about albums stored in a
    library. Reflects the library's "albums" table, including album
    art.
    """
    _table = 'albums'
    _flex_table = 'album_attributes'
    _fields = {
        'id':      types.PRIMARY_ID,
        'artpath': PathType(),
        'added':   DateType(),

        'albumartist':        types.STRING,
        'albumartist_sort':   types.STRING,
        'albumartist_credit': types.STRING,
        'album':              types.STRING,
        'genre':              types.STRING,
        'year':               types.PaddedInt(4),
        'month':              types.PaddedInt(2),
        'day':                types.PaddedInt(2),
        'tracktotal':         types.PaddedInt(2),
        'disctotal':          types.PaddedInt(2),
        'comp':               types.BOOLEAN,
        'mb_albumid':         types.STRING,
        'mb_albumartistid':   types.STRING,
        'albumtype':          types.STRING,
        'label':              types.STRING,
        'mb_releasegroupid':  types.STRING,
        'asin':               types.STRING,
        'catalognum':         types.STRING,
        'script':             types.STRING,
        'language':           types.STRING,
        'country':            types.STRING,
        'albumstatus':        types.STRING,
        'media':              types.STRING,
        'albumdisambig':      types.STRING,
        'rg_album_gain':      types.NULL_FLOAT,
        'rg_album_peak':      types.NULL_FLOAT,
        'original_year':      types.PaddedInt(4),
        'original_month':     types.PaddedInt(2),
        'original_day':       types.PaddedInt(2),
    }

    _search_fields = ('album', 'albumartist', 'genre')

    item_keys = [
        'added',
        'albumartist',
        'albumartist_sort',
        'albumartist_credit',
        'album',
        'genre',
        'year',
        'month',
        'day',
        'tracktotal',
        'disctotal',
        'comp',
        'mb_albumid',
        'mb_albumartistid',
        'albumtype',
        'label',
        'mb_releasegroupid',
        'asin',
        'catalognum',
        'script',
        'language',
        'country',
        'albumstatus',
        'media',
        'albumdisambig',
        'rg_album_gain',
        'rg_album_peak',
        'original_year',
        'original_month',
        'original_day',
    ]
    """List of keys that are set on an album's items.
    """

    @classmethod
    def _getters(cls):
        # In addition to plugin-provided computed fields, also expose
        # the album's directory as `path`.
        getters = plugins.album_field_getters()
        getters['path'] = Album.item_dir
        return getters

    def items(self):
        """Returns an iterable over the items associated with this
        album.
        """
        return self._db.items(dbcore.MatchQuery('album_id', self.id))

    def remove(self, delete=False, with_items=True):
        """Removes this album and all its associated items from the
        library. If delete, then the items' files are also deleted
        from disk, along with any album art. The directories
        containing the album are also removed (recursively) if empty.
        Set with_items to False to avoid removing the album's items.
        """
        super(Album, self).remove()

        # Delete art file.
        if delete:
            artpath = self.artpath
            if artpath:
                util.remove(artpath)

        # Remove (and possibly delete) the constituent items.
        if with_items:
            for item in self.items():
                item.remove(delete, False)

    def move_art(self, copy=False):
        """Move or copy any existing album art so that it remains in the
        same directory as the items.
        """
        old_art = self.artpath
        if not old_art:
            return

        new_art = self.art_destination(old_art)
        if new_art == old_art:
            return

        new_art = util.unique_path(new_art)
        log.debug('moving album art %s to %s' % (old_art, new_art))
        if copy:
            util.copy(old_art, new_art)
        else:
            util.move(old_art, new_art)
        self.artpath = new_art

        # Prune old path when moving.
        if not copy:
            util.prune_dirs(os.path.dirname(old_art),
                            self._db.directory)

    def move(self, copy=False, basedir=None):
        """Moves (or copies) all items to their destination. Any album
        art moves along with them. basedir overrides the library base
        directory for the destination. The album is stored to the
        database, persisting any modifications to its metadata.
        """
        basedir = basedir or self._db.directory

        # Ensure new metadata is available to items for destination
        # computation.
        self.store()

        # Move items.
        items = list(self.items())
        for item in items:
            item.move(copy, basedir=basedir, with_album=False)

        # Move art.
        self.move_art(copy)
        self.store()

    def item_dir(self):
        """Returns the directory containing the album's first item,
        provided that such an item exists.
        """
        item = self.items().get()
        if not item:
            raise ValueError('empty album')
        return os.path.dirname(item.path)

    def art_destination(self, image, item_dir=None):
        """Returns a path to the destination for the album art image
        for the album. `image` is the path of the image that will be
        moved there (used for its extension).

        The path construction uses the existing path of the album's
        items, so the album must contain at least one item or
        item_dir must be provided.
        """
        image = bytestring_path(image)
        item_dir = item_dir or self.item_dir()

        filename_tmpl = Template(beets.config['art_filename'].get(unicode))
        subpath = self.evaluate_template(filename_tmpl, True)
        if beets.config['asciify_paths']:
            subpath = unidecode(subpath)
        subpath = util.sanitize_path(subpath,
                                     replacements=self._db.replacements)
        subpath = bytestring_path(subpath)

        _, ext = os.path.splitext(image)
        dest = os.path.join(item_dir, subpath + ext)

        return bytestring_path(dest)

    def set_art(self, path, copy=True):
        """Sets the album's cover art to the image at the given path.
        The image is copied (or moved) into place, replacing any
        existing art.
        """
        path = bytestring_path(path)
        oldart = self.artpath
        artdest = self.art_destination(path)

        if oldart and samefile(path, oldart):
            # Art already set.
            return
        elif samefile(path, artdest):
            # Art already in place.
            self.artpath = path
            return

        # Normal operation.
        if oldart == artdest:
            util.remove(oldart)
        artdest = util.unique_path(artdest)
        if copy:
            util.copy(path, artdest)
        else:
            util.move(path, artdest)
        self.artpath = artdest

    def store(self):
        """Update the database with the album information. The album's
        tracks are also updated.
        """
        # Get modified track fields.
        track_updates = {}
        for key in self.item_keys:
            if key in self._dirty:
                track_updates[key] = self[key]

        with self._db.transaction():
            super(Album, self).store()
            if track_updates:
                for item in self.items():
                    for key, value in track_updates.items():
                        item[key] = value
                    item.store()


# Query construction helper.

def get_query(val, model_cls):
    """Take a value which may be None, a query string, a query string
    list, or a Query object, and return a suitable Query object.

    `model_cls` is the subclass of Model indicating which entity this
    is a query for (i.e., Album or Item) and is used to determine which
    fields are searched.
    """
    # Get query types and their prefix characters.
    prefixes = {':': dbcore.query.RegexpQuery}
    prefixes.update(plugins.queries())

    # Convert a single string into a list of space-separated
    # criteria.
    if isinstance(val, basestring):
        # A bug in Python < 2.7.3 prevents correct shlex splitting of
        # Unicode strings.
        # http://bugs.python.org/issue6988
        if isinstance(val, unicode):
            val = val.encode('utf8')
        val = [s.decode('utf8') for s in shlex.split(val)]

    if val is None:
        return dbcore.query.TrueQuery()

    elif isinstance(val, list) or isinstance(val, tuple):
        # Special-case path-like queries, which are non-field queries
        # containing path separators (/).
        if 'path' in model_cls._fields:
            path_parts = []
            non_path_parts = []
            for s in val:
                if s.find(os.sep, 0, s.find(':')) != -1:
                    # Separator precedes colon.
                    path_parts.append(s)
                else:
                    non_path_parts.append(s)
        else:
            path_parts = ()
            non_path_parts = val

        # Parse remaining parts and construct an AndQuery.
        query = dbcore.query_from_strings(
            dbcore.AndQuery, model_cls, prefixes, non_path_parts
        )

        # Add path queries to aggregate query.
        if path_parts:
            query.subqueries += [PathQuery('path', s) for s in path_parts]
        return query

    elif isinstance(val, dbcore.Query):
        return val

    else:
        raise ValueError('query must be None or have type Query or str')


# The Library: interface to the database.

class Library(dbcore.Database):
    """A database of music containing songs and albums.
    """
    _models = (Item, Album)

    def __init__(self, path='library.blb',
                 directory='~/Music',
                 path_formats=((PF_KEY_DEFAULT,
                               '$artist/$album/$track $title'),),
                 replacements=None):
        if path != ':memory:':
            self.path = bytestring_path(normpath(path))
        super(Library, self).__init__(path)

        self.directory = bytestring_path(normpath(directory))
        self.path_formats = path_formats
        self.replacements = replacements

        self._memotable = {}  # Used for template substitution performance.

    # Adding objects to the database.

    def add(self, obj):
        """Add the :class:`Item` or :class:`Album` object to the library
        database. Return the object's new id.
        """
        obj.add(self)
        self._memotable = {}
        return obj.id

    def add_album(self, items):
        """Create a new album consisting of a list of items.

        The items are added to the database if they don't yet have an
        ID. Return a new :class:`Album` object. The list items must not
        be empty.
        """
        if not items:
            raise ValueError(u'need at least one item')

        # Create the album structure using metadata from the first item.
        values = dict((key, items[0][key]) for key in Album.item_keys)
        album = Album(self, **values)

        # Add the album structure and set the items' album_id fields.
        # Store or add the items.
        with self.transaction():
            album.add(self)
            for item in items:
                item.album_id = album.id
                if item.id is None:
                    item.add(self)
                else:
                    item.store()

        return album

    # Querying.

    def _fetch(self, model_cls, query, order_by=None):
        """Parse a query and fetch.
        """
        return super(Library, self)._fetch(
            model_cls, get_query(query, model_cls), order_by
        )

    def albums(self, query=None):
        """Get a sorted list of :class:`Album` objects matching the
        given query.
        """
        order = '{0}, album'.format(
            _orelse("albumartist_sort", "albumartist")
        )
        return self._fetch(Album, query, order)

    def items(self, query=None):
        """Get a sorted list of :class:`Item` objects matching the given
        query.
        """
        order = '{0}, album, disc, track'.format(
            _orelse("artist_sort", "artist")
        )
        return self._fetch(Item, query, order)

    # Convenience accessors.

    def get_item(self, id):
        """Fetch an :class:`Item` by its ID. Returns `None` if no match is
        found.
        """
        return self._get(Item, id)

    def get_album(self, item_or_id):
        """Given an album ID or an item associated with an album, return
        an :class:`Album` object for the album. If no such album exists,
        returns `None`.
        """
        if isinstance(item_or_id, int):
            album_id = item_or_id
        else:
            album_id = item_or_id.album_id
        if album_id is None:
            return None
        return self._get(Album, album_id)


# Default path template resources.

def _int_arg(s):
    """Convert a string argument to an integer for use in a template
    function.  May raise a ValueError.
    """
    return int(s.strip())


class DefaultTemplateFunctions(object):
    """A container class for the default functions provided to path
    templates. These functions are contained in an object to provide
    additional context to the functions -- specifically, the Item being
    evaluated.
    """
    _prefix = 'tmpl_'

    def __init__(self, item=None, lib=None):
        """Paramaterize the functions. If `item` or `lib` is None, then
        some functions (namely, ``aunique``) will always evaluate to the
        empty string.
        """
        self.item = item
        self.lib = lib

    def functions(self):
        """Returns a dictionary containing the functions defined in this
        object. The keys are function names (as exposed in templates)
        and the values are Python functions.
        """
        out = {}
        for key in self._func_names:
            out[key[len(self._prefix):]] = getattr(self, key)
        return out

    @staticmethod
    def tmpl_lower(s):
        """Convert a string to lower case."""
        return s.lower()

    @staticmethod
    def tmpl_upper(s):
        """Covert a string to upper case."""
        return s.upper()

    @staticmethod
    def tmpl_title(s):
        """Convert a string to title case."""
        return s.title()

    @staticmethod
    def tmpl_left(s, chars):
        """Get the leftmost characters of a string."""
        return s[0:_int_arg(chars)]

    @staticmethod
    def tmpl_right(s, chars):
        """Get the rightmost characters of a string."""
        return s[-_int_arg(chars):]

    @staticmethod
    def tmpl_if(condition, trueval, falseval=u''):
        """If ``condition`` is nonempty and nonzero, emit ``trueval``;
        otherwise, emit ``falseval`` (if provided).
        """
        try:
            int_condition = _int_arg(condition)
        except ValueError:
            if condition.lower() == "false":
                return falseval
        else:
            condition = int_condition

        if condition:
            return trueval
        else:
            return falseval

    @staticmethod
    def tmpl_asciify(s):
        """Translate non-ASCII characters to their ASCII equivalents.
        """
        return unidecode(s)

    @staticmethod
    def tmpl_time(s, format):
        """Format a time value using `strftime`.
        """
        cur_fmt = beets.config['time_format'].get(unicode)
        return time.strftime(format, time.strptime(s, cur_fmt))

    def tmpl_aunique(self, keys=None, disam=None):
        """Generate a string that is guaranteed to be unique among all
        albums in the library who share the same set of keys. A fields
        from "disam" is used in the string if one is sufficient to
        disambiguate the albums. Otherwise, a fallback opaque value is
        used. Both "keys" and "disam" should be given as
        whitespace-separated lists of field names.
        """
        # Fast paths: no album, no item or library, or memoized value.
        if not self.item or not self.lib:
            return u''
        if self.item.album_id is None:
            return u''
        memokey = ('aunique', keys, disam, self.item.album_id)
        memoval = self.lib._memotable.get(memokey)
        if memoval is not None:
            return memoval

        keys = keys or 'albumartist album'
        disam = disam or 'albumtype year label catalognum albumdisambig'
        keys = keys.split()
        disam = disam.split()

        album = self.lib.get_album(self.item)
        if not album:
            # Do nothing for singletons.
            self.lib._memotable[memokey] = u''
            return u''

        # Find matching albums to disambiguate with.
        subqueries = []
        for key in keys:
            value = getattr(album, key)
            subqueries.append(dbcore.MatchQuery(key, value))
        albums = self.lib.albums(dbcore.AndQuery(subqueries))

        # If there's only one album to matching these details, then do
        # nothing.
        if len(albums) == 1:
            self.lib._memotable[memokey] = u''
            return u''

        # Find the first disambiguator that distinguishes the albums.
        for disambiguator in disam:
            # Get the value for each album for the current field.
            disam_values = set([getattr(a, disambiguator) for a in albums])

            # If the set of unique values is equal to the number of
            # albums in the disambiguation set, we're done -- this is
            # sufficient disambiguation.
            if len(disam_values) == len(albums):
                break

        else:
            # No disambiguator distinguished all fields.
            res = u' {0}'.format(album.id)
            self.lib._memotable[memokey] = res
            return res

        # Flatten disambiguation value into a string.
        disam_value = album._get_formatted(disambiguator, True)
        res = u' [{0}]'.format(disam_value)
        self.lib._memotable[memokey] = res
        return res


# Get the name of tmpl_* functions in the above class.
DefaultTemplateFunctions._func_names = \
    [s for s in dir(DefaultTemplateFunctions)
     if s.startswith(DefaultTemplateFunctions._prefix)]
