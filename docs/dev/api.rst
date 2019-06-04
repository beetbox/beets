Library Database API
====================

.. currentmodule:: beets.library

This page describes the internal API of beets' core database features. It
doesn't exhaustively document the API, but is aimed at giving an overview of
the architecture to orient anyone who wants to dive into the code.

The :class:`Library` object is the central repository for data in beets. It
represents a database containing songs, which are :class:`Item` instances, and
groups of items, which are :class:`Album` instances.

The Library Class
-----------------

The :class:`Library` is typically instantiated as a singleton. A single
invocation of beets usually has only one :class:`Library`. It's powered by
:class:`dbcore.Database` under the hood, which handles the `SQLite`_
abstraction, something like a very minimal `ORM`_. The library is also
responsible for handling queries to retrieve stored objects.

.. autoclass:: Library(path, directory[, path_formats[, replacements]])

    .. automethod:: __init__

    You can add new items or albums to the library:

    .. automethod:: add

    .. automethod:: add_album

    And there are methods for querying the database:

    .. automethod:: items

    .. automethod:: albums

    .. automethod:: get_item

    .. automethod:: get_album

    Any modifications must go through a :class:`Transaction` which you get can
    using this method:

    .. automethod:: transaction

.. _SQLite: http://sqlite.org/
.. _ORM: http://en.wikipedia.org/wiki/Object-relational_mapping


Model Classes
-------------

The two model entities in beets libraries, :class:`Item` and :class:`Album`,
share a base class, :class:`LibModel`, that provides common functionality and
ORM-like abstraction.

Model base
''''''''''

Models use dirty-flags to track when the object's metadata goes out of
sync with the database. The dirty dictionary maps field names to booleans
indicating whether the field has been written since the object was last
synchronized (via load or store) with the database.

.. autoclass:: LibModel

    .. automethod:: all_keys

    .. automethod:: __init__

    .. autoattribute:: _types

    .. autoattribute:: _fields

    There are CRUD-like methods for interacting with the database:

    .. automethod:: store

    .. automethod:: load

    .. automethod:: remove

    .. automethod:: add

    The fields model classes can be accessed using attributes (dots, as in
    ``item.artist``) or items (brackets, as in ``item['artist']``).
    The base class :class:`dbcore.Model` has a ``dict``-like interface, so
    normal the normal mapping API is supported:

    .. automethod:: keys

    .. automethod:: update

    .. automethod:: items

    .. automethod:: get

Item
''''

Each :class:`Item` object represents a song or track. (We use the more generic
term item because, one day, beets might support non-music media.) An item can
either be purely abstract, in which case it's just a bag of metadata fields,
or it can have an associated file (indicated by ``item.path``).

In terms of the underlying SQLite database, items are backed by a single table
called items with one column per metadata fields. The metadata fields currently
in use are listed in ``library.py`` in ``Item._fields``.

To read and write a file's tags, we use the `MediaFile`_ library.
To make changes to either the database or the tags on a file, you
update an item's fields (e.g., ``item.title = "Let It Be"``) and then call
``item.write()``.

.. _MediaFile: http://mediafile.readthedocs.io/

.. autoclass:: Item

    .. automethod:: __init__

    .. automethod:: from_path

    .. automethod:: get_album

    .. automethod:: destination

    The methods ``read()`` and ``write()`` are complementary: one reads a
    file's tags and updates the item's metadata fields accordingly while the
    other takes the item's fields and writes them to the file's tags.

    .. automethod:: read

    .. automethod:: write

    .. automethod:: try_write

    .. automethod:: try_sync

    The :class:`Item` class supplements the normal model interface so that they
    interacting with the filesystem as well:

    .. automethod:: move

    .. automethod:: remove

    Items also track their modification times (mtimes) to help detect when they
    become out of sync with on-disk metadata.

    .. automethod:: current_mtime

Album
'''''

An :class:`Album` is a collection of Items in the database. Every item in the
database has either zero or one associated albums (accessible via
``item.album_id``).  An item that has no associated album is called a
singleton.

An :class:`Album` object keeps track of album-level metadata, which is (mostly)
a subset of the track-level metadata. The album-level metadata fields are
listed in ``Album._fields``.
For those fields that are both item-level and album-level (e.g., ``year`` or
``albumartist``), every item in an album should share the same value. Albums
use an SQLite table called ``albums``, in which each column is an album
metadata field.

.. autoclass:: Album

    .. automethod:: __init__

    .. automethod:: item_dir

    To get or change an album's metadata, use its fields (e.g.,
    ``print(album.year)`` or ``album.year = 2012``). Changing fields in this
    way updates the album itself and also changes the same field in all
    associated items:

    .. autoattribute:: item_keys

    .. automethod:: store

    .. automethod:: try_sync

    .. automethod:: move

    .. automethod:: remove

    Albums also manage album art, image files that are associated with each
    album:

    .. automethod:: set_art

    .. automethod:: move_art

    .. automethod:: art_destination

Transactions
''''''''''''

The :class:`Library` class provides the basic methods necessary to access and
manipulate its contents. To perform more complicated operations atomically, or
to interact directly with the underlying SQLite database, you must use a
*transaction* (see this `blog post`_ for motivation). For example::

    lib = Library()
    with lib.transaction() as tx:
        items = lib.items(query)
        lib.add_album(list(items))

.. _blog post: http://beets.io/blog/sqlite-nightmare.html

.. currentmodule:: beets.dbcore.db

.. autoclass:: Transaction
    :members:
