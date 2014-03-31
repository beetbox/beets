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
import re
import sys
import logging
import shlex
import unicodedata
import time
from unidecode import unidecode
from beets.mediafile import MediaFile, MutagenError
from beets import plugins
from beets import util
from beets.util import bytestring_path, syspath, normpath, samefile
from beets.util.functemplate import Template
from beets import dbcore
from beets.dbcore import types
import beets



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


class SingletonQuery(dbcore.Query):
    """Matches either singleton or non-singleton items."""
    def __init__(self, sense):
        self.sense = sense

    def clause(self):
        if self.sense:
            return "album_id ISNULL", ()
        else:
            return "NOT album_id ISNULL", ()

    def match(self, item):
        return (not item.album_id) == self.sense



# Library-specific field types.


class DateType(types.Type):
    sql = u'REAL'
    query = dbcore.query.DateQuery

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
                return 0.0


class PathType(types.Type):
    sql = u'BLOB'
    query = PathQuery

    def format(self, value):
        return util.displayable_path(value)

    def parse(self, string):
        return normpath(bytestring_path(string))



# Model field lists.


# Fields in the "items" database table; all the metadata available for
# items in the library. These are used directly in SQL; they are
# vulnerable to injection if accessible to the user.
# Each tuple has the following values:
# - The name of the field.
# - The (Python) type of the field.
# - Is the field writable?
# - Does the field reflect an attribute of a MediaFile?
ITEM_FIELDS = [
    ('id',       types.Id(),      False, False),
    ('path',     PathType(),      False, False),
    ('album_id', types.Integer(), False, False),

    ('title',                types.String(),     True, True),
    ('artist',               types.String(),     True, True),
    ('artist_sort',          types.String(),     True, True),
    ('artist_credit',        types.String(),     True, True),
    ('album',                types.String(),     True, True),
    ('albumartist',          types.String(),     True, True),
    ('albumartist_sort',     types.String(),     True, True),
    ('albumartist_credit',   types.String(),     True, True),
    ('genre',                types.String(),     True, True),
    ('composer',             types.String(),     True, True),
    ('grouping',             types.String(),     True, True),
    ('year',                 types.PaddedInt(4), True, True),
    ('month',                types.PaddedInt(2), True, True),
    ('day',                  types.PaddedInt(2), True, True),
    ('track',                types.PaddedInt(2), True, True),
    ('tracktotal',           types.PaddedInt(2), True, True),
    ('disc',                 types.PaddedInt(2), True, True),
    ('disctotal',            types.PaddedInt(2), True, True),
    ('lyrics',               types.String(),     True, True),
    ('comments',             types.String(),     True, True),
    ('bpm',                  types.Integer(),    True, True),
    ('comp',                 types.Boolean(),    True, True),
    ('mb_trackid',           types.String(),     True, True),
    ('mb_albumid',           types.String(),     True, True),
    ('mb_artistid',          types.String(),     True, True),
    ('mb_albumartistid',     types.String(),     True, True),
    ('albumtype',            types.String(),     True, True),
    ('label',                types.String(),     True, True),
    ('acoustid_fingerprint', types.String(),     True, True),
    ('acoustid_id',          types.String(),     True, True),
    ('mb_releasegroupid',    types.String(),     True, True),
    ('asin',                 types.String(),     True, True),
    ('catalognum',           types.String(),     True, True),
    ('script',               types.String(),     True, True),
    ('language',             types.String(),     True, True),
    ('country',              types.String(),     True, True),
    ('albumstatus',          types.String(),     True, True),
    ('media',                types.String(),     True, True),
    ('albumdisambig',        types.String(),     True, True),
    ('disctitle',            types.String(),     True, True),
    ('encoder',              types.String(),     True, True),
    ('rg_track_gain',        types.Float(),      True, True),
    ('rg_track_peak',        types.Float(),      True, True),
    ('rg_album_gain',        types.Float(),      True, True),
    ('rg_album_peak',        types.Float(),      True, True),
    ('original_year',        types.PaddedInt(4), True, True),
    ('original_month',       types.PaddedInt(2), True, True),
    ('original_day',         types.PaddedInt(2), True, True),

    ('length',      types.Float(),                  False, True),
    ('bitrate',     types.ScaledInt(1000, u'kbps'), False, True),
    ('format',      types.String(),                 False, True),
    ('samplerate',  types.ScaledInt(1000, u'kHz'),  False, True),
    ('bitdepth',    types.Integer(),                False, True),
    ('channels',    types.Integer(),                False, True),
    ('mtime',       DateType(),                     False, False),
    ('added',       DateType(),                     False, False),
]
ITEM_KEYS_WRITABLE = [f[0] for f in ITEM_FIELDS if f[3] and f[2]]
ITEM_KEYS_META     = [f[0] for f in ITEM_FIELDS if f[3]]
ITEM_KEYS          = [f[0] for f in ITEM_FIELDS]

# Database fields for the "albums" table.
# The third entry in each tuple indicates whether the field reflects an
# identically-named field in the items table.
ALBUM_FIELDS = [
    ('id',      types.Id(), False),
    ('artpath', PathType(), False),
    ('added',   DateType(), True),

    ('albumartist',        types.String(),     True),
    ('albumartist_sort',   types.String(),     True),
    ('albumartist_credit', types.String(),     True),
    ('album',              types.String(),     True),
    ('genre',              types.String(),     True),
    ('year',               types.PaddedInt(4), True),
    ('month',              types.PaddedInt(2), True),
    ('day',                types.PaddedInt(2), True),
    ('tracktotal',         types.PaddedInt(2), True),
    ('disctotal',          types.PaddedInt(2), True),
    ('comp',               types.Boolean(),    True),
    ('mb_albumid',         types.String(),     True),
    ('mb_albumartistid',   types.String(),     True),
    ('albumtype',          types.String(),     True),
    ('label',              types.String(),     True),
    ('mb_releasegroupid',  types.String(),     True),
    ('asin',               types.String(),     True),
    ('catalognum',         types.String(),     True),
    ('script',             types.String(),     True),
    ('language',           types.String(),     True),
    ('country',            types.String(),     True),
    ('albumstatus',        types.String(),     True),
    ('media',              types.String(),     True),
    ('albumdisambig',      types.String(),     True),
    ('rg_album_gain',      types.Float(),      True),
    ('rg_album_peak',      types.Float(),      True),
    ('original_year',      types.PaddedInt(4), True),
    ('original_month',     types.PaddedInt(2), True),
    ('original_day',       types.PaddedInt(2), True),
]
ALBUM_KEYS = [f[0] for f in ALBUM_FIELDS]
ALBUM_KEYS_ITEM = [f[0] for f in ALBUM_FIELDS if f[2]]


# Default search fields for each model.
ALBUM_DEFAULT_FIELDS = ('album', 'albumartist', 'genre')
ITEM_DEFAULT_FIELDS = ALBUM_DEFAULT_FIELDS + ('artist', 'title', 'comments')


# Special path format key.
PF_KEY_DEFAULT = 'default'


# Logger.
log = logging.getLogger('beets')
if not log.handlers:
    log.addHandler(logging.StreamHandler())
log.propagate = False  # Don't propagate to root handler.


# A little SQL utility.
def _orelse(exp1, exp2):
    """Generates an SQLite expression that evaluates to exp1 if exp1 is
    non-null and non-empty or exp2 otherwise.
    """
    return ('(CASE {0} WHEN NULL THEN {1} '
                      'WHEN "" THEN {1} '
                      'ELSE {0} END)').format(exp1, exp2)



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
    _fields = dict((name, typ) for (name, typ, _, _) in ITEM_FIELDS)
    _table = 'items'
    _flex_table = 'item_attributes'
    _search_fields = ITEM_DEFAULT_FIELDS

    @classmethod
    def _getters(cls):
        return plugins.item_field_getters()

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

        if key in ITEM_KEYS_WRITABLE:
            self.mtime = 0  # Reset mtime on dirty.

        super(Item, self).__setitem__(key, value)

    def update(self, values):
        """Sett all key/value pairs in the mapping. If mtime is
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
        """Read the metadata from the associated file. If read_path is
        specified, read metadata from that file instead.

        Raises a `ReadError` if the file could not be read.
        """
        if read_path is None:
            read_path = self.path
        else:
            read_path = normpath(read_path)
        try:
            f = MediaFile(syspath(read_path))
        except (OSError, IOError) as exc:
            raise ReadError(read_path, exc)

        for key in ITEM_KEYS_META:
            value = getattr(f, key)
            if isinstance(value, (int, long)):
                # Filter values wider than 64 bits (in signed
                # representation). SQLite cannot store them.
                # py26: Post transition, we can use:
                # value.bit_length() > 63
                if abs(value) >= 2 ** 63:
                    value = 0
            setattr(self, key, value)

        # Database's mtime should now reflect the on-disk value.
        if read_path == self.path:
            self.mtime = self.current_mtime()

        self.path = read_path

    def write(self):
        """Write the item's metadata to the associated file.

        Can raise either a `ReadError` or a `WriteError`.
        """
        try:
            f = MediaFile(syspath(self.path))
        except (OSError, IOError) as exc:
            raise ReadError(self.path, exc)

        plugins.send('write', item=self)

        for key in ITEM_KEYS_WRITABLE:
            setattr(f, key, self[key])
        try:
            f.save(id3v23=beets.config['id3v23'].get(bool))
        except (OSError, IOError, MutagenError) as exc:
            raise WriteError(self.path, exc)

        # The file has a new mtime.
        self.mtime = self.current_mtime()
        plugins.send('after_write', item=self)


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
        mapping = super(Item, self)._formatted_mapping(for_path)

        # Merge in album-level fields.
        album = self.get_album()
        if album:
            for key in album.keys(True):
                if key in ALBUM_KEYS_ITEM or key not in ITEM_KEYS:
                    mapping[key] = album._get_formatted(key, for_path)

        # Use the album artist if the track artist is not set and
        # vice-versa.
        if not mapping['artist']:
            mapping['artist'] = mapping['albumartist']
        if not mapping['albumartist']:
            mapping['albumartist'] = mapping['artist']

        return mapping

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


class Album(LibModel):
    """Provides access to information about albums stored in a
    library. Reflects the library's "albums" table, including album
    art.
    """
    _fields = dict((name, typ) for (name, typ, _) in ALBUM_FIELDS)
    _table = 'albums'
    _flex_table = 'album_attributes'
    _search_fields = ALBUM_DEFAULT_FIELDS

    @classmethod
    def _getters(cls):
        # In addition to plugin-provided computed fields, also expose
        # the album's directory as `path`.
        getters = plugins.album_field_getters()
        getters['path'] = Album.item_dir
        return getters

    def __setitem__(self, key, value):
        """Set the value of an album attribute."""
        if key == 'artpath':
            if isinstance(value, unicode):
                value = bytestring_path(value)
            elif isinstance(value, buffer):
                value = bytes(value)
        super(Album, self).__setitem__(key, value)

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
        for key in ALBUM_KEYS_ITEM:
            if key in self._dirty:
                track_updates[key] = self[key]

        with self._db.transaction():
            super(Album, self).store()
            if track_updates:
                for item in self.items():
                    for key, value in track_updates.items():
                        item[key] = value
                    item.store()



# Query construction and parsing helpers.


PARSE_QUERY_PART_REGEX = re.compile(
    # Non-capturing optional segment for the keyword.
    r'(?:'
        r'(\S+?)'    # The field key.
        r'(?<!\\):'  # Unescaped :
    r')?'

    r'(.*)',         # The term itself.

    re.I  # Case-insensitive.
)

def parse_query_part(part, query_classes={}, prefixes={},
                     default_class=dbcore.query.SubstringQuery):
    """Take a query in the form of a key/value pair separated by a
    colon and return a tuple of `(key, value, cls)`. `key` may be None,
    indicating that any field may be matched. `cls` is a subclass of
    `FieldQuery`.

    The optional `query_classes` parameter maps field names to default
    query types; `default_class` is the fallback. `prefixes` is a map
    from query prefix markers and query types. Prefix-indicated queries
    take precedence over type-based queries.

    To determine the query class, two factors are used: prefixes and
    field types. For example, the colon prefix denotes a regular
    expression query and a type map might provide a special kind of
    query for numeric values. If neither a prefix nor a specific query
    class is available, `default_class` is used.

    For instance,
    'stapler' -> (None, 'stapler', SubstringQuery)
    'color:red' -> ('color', 'red', SubstringQuery)
    ':^Quiet' -> (None, '^Quiet', RegexpQuery)
    'color::b..e' -> ('color', 'b..e', RegexpQuery)

    Prefixes may be "escaped" with a backslash to disable the keying
    behavior.
    """
    part = part.strip()
    match = PARSE_QUERY_PART_REGEX.match(part)

    assert match  # Regex should always match.
    key = match.group(1)
    term = match.group(2).replace('\:', ':')

    # Match the search term against the list of prefixes.
    for pre, query_class in prefixes.items():
        if term.startswith(pre):
            return key, term[len(pre):], query_class

    # No matching prefix: use type-based or fallback/default query.
    query_class = query_classes.get(key, default_class)
    return key, term, query_class


def construct_query_part(query_part, model_cls):
    """Create a query from a single query component, `query_part`, for
    querying instances of `model_cls`. Return a `Query` instance.
    """
    # Shortcut for empty query parts.
    if not query_part:
        return dbcore.query.TrueQuery()

    # Set up and parse the string.
    query_classes = dict((k, t.query) for (k, t) in model_cls._fields.items())
    prefixes = {':': dbcore.query.RegexpQuery}
    prefixes.update(plugins.queries())
    key, pattern, query_class = \
            parse_query_part(query_part, query_classes, prefixes)

    # No key specified.
    if key is None:
        if os.sep in pattern and 'path' in model_cls._fields:
            # This looks like a path.
            return PathQuery('path', pattern)
        elif issubclass(query_class, dbcore.FieldQuery):
            # The query type matches a specific field, but none was
            # specified. So we use a version of the query that matches
            # any field.
            return dbcore.query.AnyFieldQuery(pattern,
                                              model_cls._search_fields,
                                              query_class)
        else:
            # Other query type.
            return query_class(pattern)

    key = key.lower()

    # Singleton query (not a real field).
    if key == 'singleton':
        return SingletonQuery(util.str2bool(pattern))

    # Other field.
    else:
        return query_class(key.lower(), pattern, key in model_cls._fields)


def query_from_strings(query_cls, model_cls, query_parts):
    """Creates a collection query of type `query_cls` from a list of
    strings in the format used by parse_query_part. `model_cls`
    determines how queries are constructed from strings.
    """
    subqueries = []
    for part in query_parts:
        subqueries.append(construct_query_part(part, model_cls))
    if not subqueries:  # No terms in query.
        subqueries = [dbcore.query.TrueQuery()]
    return query_cls(subqueries)


def get_query(val, model_cls):
    """Takes a value which may be None, a query string, a query string
    list, or a Query object, and returns a suitable Query object.
    `model_cls` is the subclass of Model indicating which entity this
    is a query for (i.e., Album or Item) and is used to determine which
    fields are searched.
    """
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
        return query_from_strings(dbcore.AndQuery, model_cls, val)
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
        """Create a new album consisting of a list of items. The items
        are added to the database if they don't yet have an ID. Return a
        new :class:`Album` object.
        """
        # Create the album structure using metadata from the first item.
        values = dict((key, items[0][key]) for key in ALBUM_KEYS_ITEM)
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
            condition = _int_arg(condition)
        except ValueError:
            condition = condition.strip()
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
