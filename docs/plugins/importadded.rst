ImportAdded Plugin
==================

The ``importadded`` plugin is useful when an existing collection is imported
and the time when albums and items were added should be preserved.

The :abbr:`mtime (modification time)` of files that are imported into the
library are assumed to represent the time when the items were originally
added.

The ``item.added`` field is populated as follows:

* For singleton items with no album, ``item.added`` is set to the item's file
  mtime before it was imported.
* For items that are part of an album, ``album.added`` and ``item.added`` is
  set to the oldest mtime of the files in the album before they were imported.
  The mtime of album directories are ignored.

This plugin can optionally be configured to also preserve mtimes::

    importadded:
        preserve_mtimes: yes # default: no

File modification times are preserved as follows:

* For all items:

  * ``item.mtime`` is set to the mtime of the file
    from which the item is imported from.
  * The mtime of the file ``item.path`` is set to ``item.mtime``.

Note that there is no ``album.mtime`` field in the database and that the mtime
of album directories on disk aren't preserved.
