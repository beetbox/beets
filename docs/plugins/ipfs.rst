IPFS Plugin
===========

The ``ipfs`` plugin makes it easy to share your library and music with friends.
The plugin uses `ipfs`_ for storing the libraries and the file content.

.. _ipfs: http://ipfs.io/

Installation
------------

This plugin requires `go-ipfs`_ running as a dameon and that the ipfs command is
in the users $PATH.

.. _go-ipfs: https://github.com/ipfs/go-ipfs

Enable the ``ipfs`` plugin in your configuration (see :ref:`using-plugins`).

Usage
-----

To add albums to ipfs, making them shareable, use the -a or --add flag. If used
without arguments it will add all albums in the local library.  When added all
items and albums will get a ipfs entry in the database containing the hash of
that specific file/folder.

These hashes can then be given to a friend and they can ``get`` that album from
ipfs and import it to beets using the -g or --get flag.
If the argument passed to the -g flag isn't a ipfs hash it'll be used as a
query instead, getting all albums matching the query.

Using the -p or --publish flag a copy of the local library will be
published to ipfs. Only albums/items with ipfs records in the database will
published, and local paths will be stripped from the library. A hash of the
library will be returned to the user.

A friend can then import this remote library by using the -i or --import flag.
To tag an imported library with a specific name by passing a name as the second
argument to -i, after the hash.
The content of all remote libraries will be combined into an additional library
as long as the content doesn't already exist in the joined library.

When remote libraries has been imported you can search them by using the -l or
--list flag. The hash of albums matching the query will be returned, this can
then be used with -g to fetch and import the album to the local library.

