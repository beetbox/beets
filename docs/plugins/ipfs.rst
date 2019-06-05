IPFS Plugin
===========

The ``ipfs`` plugin makes it easy to share your library and music with friends.
The plugin uses `ipfs`_ for storing the library and file content.

.. _ipfs: https://ipfs.io/

Installation
------------

This plugin requires `go-ipfs`_ to be running as a daemon and that the
associated ``ipfs`` command is on the user's ``$PATH``.

.. _go-ipfs: https://github.com/ipfs/go-ipfs

Once you have the client installed, enable the ``ipfs`` plugin in your
configuration (see :ref:`using-plugins`).

Usage
-----

This plugin can store and retrieve music individually, or it can share entire
library databases.

Adding
''''''

To add albums to ipfs, making them shareable, use the ``-a`` or ``--add``
flag. If used without arguments it will add all albums in the local library.
When added, all items and albums will get an "ipfs" field in the database
containing the hash of that specific file/folder. Newly imported albums will
be added automatically to ipfs by default (see below).

Retrieving
''''''''''

You can give the ipfs hash for some music to a friend. They can get that album
from ipfs, and import it into beets, using the ``-g`` or ``--get`` flag. If
the argument passed to the ``-g`` flag isn't an ipfs hash, it will be used as
a query instead, getting all albums matching the query.

Sharing Libraries
'''''''''''''''''

Using the ``-p`` or ``--publish`` flag, a copy of the local library will be
published to ipfs. Only albums/items with ipfs records in the database will
published, and local paths will be stripped from the library. A hash of the
library will be returned to the user.

A friend can then import this remote library by using the ``-i`` or
``--import`` flag. To tag an imported library with a specific name by passing
a name as the second argument to ``-i,`` after the hash. The content of all
remote libraries will be combined into an additional library as long as the
content doesn't already exist in the joined library.

When remote libraries has been imported you can search them by using the
``-l`` or ``--list`` flag. The hash of albums matching the query will be
returned, and this can then be used with ``-g`` to fetch and import the album
to the local library.

Ipfs can be mounted as a FUSE file system. This means that music in a remote
library can be streamed directly, without importing them to the local library
first. If the ``/ipfs`` folder is mounted then matching queries will be sent
to the :doc:`/plugins/play` using the ``-m`` or ``--play`` flag.

Configuration
-------------

The ipfs plugin will automatically add imported albums to ipfs and add those
hashes to the database. This can be turned off by setting the ``auto`` option
in the ``ipfs:`` section of the config to ``no``.

If the setting ``nocopy`` is true (defaults false) then the plugin will pass the ``--nocopy`` option when adding things to ipfs. If the filestore option of ipfs is enabled this will mean files are neither removed from beets nor copied somewhere else.
