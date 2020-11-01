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

.. _SQLite: https://sqlite.org/index.html
.. _ORM: https://en.wikipedia.org/wiki/Object-relational_mapping


Model Classes
-------------

The two model entities in beets libraries, :class:`Item` and :class:`Album`,
share a base class, :class:`LibModel`, that provides common functionality. That
class itself specialises :class:`dbcore.Model` which provides an ORM-like
abstraction.

To get or change the metadata of a model (an item or album), either access its
attributes (e.g., ``print(album.year)`` or ``album.year = 2012``) or use the
``dict``-like interface (e.g. ``item['artist']``).


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

.. _MediaFile: https://mediafile.readthedocs.io/en/latest/

Items also track their modification times (mtimes) to help detect when they
become out of sync with on-disk metadata, mainly to speed up the
:ref:`update-cmd` (which needs to check whether the database is in sync with
the filesystem). This feature turns out to be sort of complicated.

For any :class:`Item`, there are two mtimes: the on-disk mtime (maintained by
the OS) and the database mtime (maintained by beets). Correspondingly, there is
on-disk metadata (ID3 tags, for example) and DB metadata. The goal with the
mtime is to ensure that the on-disk and DB mtimes match when the on-disk and DB
metadata are in sync; this lets beets do a quick mtime check and avoid
rereading files in some circumstances.

Specifically, beets attempts to maintain the following invariant:

    If the on-disk metadata differs from the DB metadata, then the on-disk
    mtime must be greater than the DB mtime.

As a result, it is always valid for the DB mtime to be zero (assuming that real
disk mtimes are always positive). However, whenever possible, beets tries to
set ``db_mtime = disk_mtime`` at points where it knows the metadata is
synchronized. When it is possible that the metadata is out of sync, beets can
then just set ``db_mtime = 0`` to return to a consistent state.

This leads to the following implementation policy:

  * On every write of disk metadata (``Item.write()``), the DB mtime is updated
    to match the post-write disk mtime.
  * Same for metadata reads (``Item.read()``).
  * On every modification to DB metadata (``item.field = ...``), the DB mtime
    is reset to zero.


.. autoclass:: Item

    .. automethod:: __init__

    .. automethod:: from_path

    .. automethod:: get_album

    .. automethod:: destination

    .. automethod:: current_mtime

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

Album
'''''

An :class:`Album` is a collection of Items in the database. Every item in the
database has either zero or one associated albums (accessible via
``item.album_id``).  An item that has no associated album is called a
singleton.
Changing fields on an album (e.g. ``album.year = 2012``) updates the album
itself and also changes the same field in all associated items.

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

    Albums extend the normal model interface to also forward changes to their
    items:

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

.. _blog post: https://beets.io/blog/sqlite-nightmare.html

.. currentmodule:: beets.dbcore.db

.. autoclass:: Transaction
    :members:


Queries
-------

To access albums and items in a library, we use :doc:`/reference/query`.
In beets, the :class:`Query` abstract base class represents a criterion that
matches items or albums in the database.
Every subclass of :class:`Query` must implement two methods, which implement
two different ways of identifying matching items/albums.

The ``clause()`` method should return an SQLite ``WHERE`` clause that matches
appropriate albums/items. This allows for efficient batch queries.
Correspondingly, the ``match(item)`` method should take an :class:`Item` object
and return a boolean, indicating whether or not a specific item matches the
criterion. This alternate implementation allows clients to determine whether
items that have already been fetched from the database match the query.

There are many different types of queries. Just as an example,
:class:`FieldQuery` determines whether a certain field matches a certain value
(an equality query).
:class:`AndQuery` (like its abstract superclass, :class:`CollectionQuery`)
takes a set of other query objects and bundles them together, matching only
albums/items that match all constituent queries.

Beets has a human-writable plain-text query syntax that can be parsed into
:class:`Query` objects. Calling ``AndQuery.from_strings`` parses a list of
query parts into a query object that can then be used with :class:`Library`
objects.
