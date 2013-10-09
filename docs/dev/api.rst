API Documentation
=================

.. currentmodule:: beets.library

This page describes the internal API of beets' core. It's a work in
progress---since beets is an application first and a library second, its API
has been mainly undocumented until recently. Please file bugs if you run
across incomplete or incorrect docs here.

The :class:`Library` object is the central repository for data in beets. It
represents a database containing songs, which are :class:`Item` instances, and
groups of items, which are :class:`Album` instances.

The Library Class
-----------------

.. autoclass:: Library(path, directory[, path_formats[, replacements]])

    .. automethod:: items

    .. automethod:: albums

    .. automethod:: get_item

    .. automethod:: get_album

    .. automethod:: add

    .. automethod:: add_album

    .. automethod:: transaction

Transactions
''''''''''''

The :class:`Library` class provides the basic methods necessary to access and
manipulate its contents. To perform more complicated operations atomically, or
to interact directly with the underlying SQLite database, you must use a
*transaction*. For example::

    lib = Library()
    with lib.transaction() as tx:
        items = lib.items(query)
        lib.add_album(list(items))

.. autoclass:: Transaction
    :members:

Model Classes
-------------

The two model entities in beets libraries, :class:`Item` and :class:`Album`,
share base classes that provide generic data storage. The :class:`LibModel`
class inherits from :class:`FlexModel`, and both :class:`Item` and
:class:`Album` inherit from it.

The fields model classes can be accessed using attributes (dots, as in
``item.artist``) or items (brackets, as in ``item['artist']``). The
:class:`FlexModel` base class provides some methods that resemble `dict`
objects.

.. autoclass:: FlexModel
    :members:

.. autoclass:: LibModel
    :members:

Item
''''

.. autoclass:: Item
    :members:

Album
'''''

.. autoclass:: Album
    :members:
