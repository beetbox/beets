ImportMtimes Plugin
===================

The ``importmtimes`` plugin is useful when an existing collection is imported
and the time when albums and items were added should be preserved.

The :abbr:`mtime (modification time)` of files that are imported into the
library are assumed to represent the time when the items were originally
added.

File modification times are imported as follows:

* For all items, ``item.mtime`` is set to the mtime of the file
  from which the item is imported from.
* For singleton items with no album, ``item.added`` is set to ``item.mtime``
  during import.
* For items that are part of an album, ``album.added`` and ``item.added`` is
  set to the oldest mtime of the album items.
* The mtime of an album's directory is ignored.

There are no configuration options for this plugin.

This plugin can only be used if Beets is :doc:`configured </reference/config>` to copy
files on import.