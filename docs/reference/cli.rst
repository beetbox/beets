Command-Line Interface
======================

.. only:: man

    SYNOPSIS
    --------

    | **beet** [*args*...] *command* [*args*...]
    | **beet help** *command*

.. only:: html

    **beet** is the command-line interface to beets.

    You invoke beets by specifying a *command*, like so::

        beet COMMAND [ARGS...]

    The rest of this document describes the available commands. If you ever need
    a quick list of what's available, just type ``beet help`` or ``beet help
    COMMAND`` for help with a specific command.

Commands
--------

.. only:: html

    Here are the built-in commands available in beets:

    .. contents::
        :local:
        :depth: 1

    Also be sure to see the :ref:`global flags <global-flags>`.

.. _import-cmd:

import
``````
::

    beet import [-CWAPRqst] [-l LOGPATH] DIR...
    beet import [options] -L QUERY

Add music to your library, attempting to get correct tags for it from
MusicBrainz.

Point the command at a directory full of music. The directory can be a single
album or a directory whose leaf subdirectories are albums (the latter case is
true of typical Artist/Album organizations and many people's "downloads"
folders). The music will be copied to a configurable directory structure (see
below) and added to a library database (see below). The command is interactive
and will try to get you to verify MusicBrainz tags that it thinks are suspect.
(This means that importing a large amount of music is therefore very tedious
right now; this is something we need to work on. Read the
:doc:`autotagging guide </guides/tagger>` if you need help.)

* By default, the command copies files your the library directory and
  updates the ID3 tags on your music. If you'd like to leave your music
  files untouched, try the ``-C`` (don't copy) and ``-W`` (don't write tags)
  options. You can also disable this behavior by default in the
  configuration file (below).

* Also, you can disable the autotagging behavior entirely using ``-A``
  (don't autotag)---then your music will be imported with its existing
  metadata.

* During a long tagging import, it can be useful to keep track of albums
  that weren't tagged successfully---either because they're not in the
  MusicBrainz database or because something's wrong with the files. Use the
  ``-l`` option to specify a filename to log every time you skip an album
  or import it "as-is" or an album gets skipped as a duplicate.

* Relatedly, the ``-q`` (quiet) option can help with large imports by
  autotagging without ever bothering to ask for user input. Whenever the
  normal autotagger mode would ask for confirmation, the quiet mode
  pessimistically skips the album. The quiet mode also disables the tagger's
  ability to resume interrupted imports.

* Speaking of resuming interrupted imports, the tagger will prompt you if it
  seems like the last import of the directory was interrupted (by you or by
  a crash). If you want to skip this prompt, you can say "yes" automatically
  by providing ``-p`` or "no" using ``-P``. The resuming feature can be
  disabled by default using a configuration option (see below).

* If you want to import only the *new* stuff from a directory, use the
  ``-i``
  option to run an *incremental* import. With this flag, beets will keep
  track of every directory it ever imports and avoid importing them again.
  This is useful if you have an "incoming" directory that you periodically
  add things to.
  To get this to work correctly, you'll need to use an incremental import *every
  time* you run an import on the directory in question---including the first
  time, when no subdirectories will be skipped. So consider enabling the
  ``incremental`` configuration option.

* By default, beets will proceed without asking if it finds a very close
  metadata match. To disable this and have the importer ask you every time,
  use the ``-t`` (for *timid*) option.

* The importer typically works in a whole-album-at-a-time mode. If you
  instead want to import individual, non-album tracks, use the *singleton*
  mode by supplying the ``-s`` option.

* If you have an album that's split across several directories under a common
  top directory, use the ``--flat`` option. This takes all the music files
  under the directory (recursively) and treats them as a single large album
  instead of as one album per directory. This can help with your more stubborn
  multi-disc albums.

* Similarly, if you have one directory that contains multiple albums, use the
  ``--group-albums`` option to split the files based on their metadata before
  matching them as separate albums.

.. only:: html

    Reimporting
    ^^^^^^^^^^^

    The ``import`` command can also be used to "reimport" music that you've
    already added to your library. This is useful when you change your mind
    about some selections you made during the initial import, or if you prefer
    to import everything "as-is" and then correct tags later.

    Just point the ``beet import`` command at a directory of files that are
    already catalogged in your library. Beets will automatically detect this
    situation and avoid duplicating any items. In this situation, the "copy
    files" option (``-c``/``-C`` on the command line or ``copy`` in the
    config file) has slightly different behavior: it causes files to be *moved*,
    rather than duplicated, if they're already in your library. (The same is
    true, of course, if ``move`` is enabled.) That is, your directory
    structure will be updated to reflect the new tags if copying is enabled; you
    never end up with two copies of the file.

    The ``-L`` (``--library``) flag is also useful for retagging. Instead of
    listing paths you want to import on the command line, specify a :doc:`query
    string <query>` that matches items from your library. In this case, the
    ``-s`` (singleton) flag controls whether the query matches individual items
    or full albums. If you want to retag your whole library, just supply a null
    query, which matches everything: ``beet import -L``

    Note that, if you just want to update your files' tags according to
    changes in the MusicBrainz database, the :doc:`/plugins/mbsync` is a
    better choice. Reimporting uses the full matching machinery to guess
    metadata matches; ``mbsync`` just relies on MusicBrainz IDs.

.. _list-cmd:

list
````
::

    beet list [-apf] QUERY

:doc:`Queries <query>` the database for music.

Want to search for "Gronlandic Edit" by of Montreal? Try ``beet list
gronlandic``.  Maybe you want to see everything released in 2009 with
"vegetables" in the title? Try ``beet list year:2009 title:vegetables``. (Read
more in :doc:`query`.)

You can use the ``-a`` switch to search for albums instead of individual items.
In this case, the queries you use are restricted to album-level fields: for
example, you can search for ``year:1969`` but query parts for item-level fields
like ``title:foo`` will be ignored. Remember that ``artist`` is an item-level
field; ``albumartist`` is the corresponding album field.

The ``-p`` option makes beets print out filenames of matched items, which might
be useful for piping into other Unix commands (such as `xargs`_). Similarly, the
``-f`` option lets you specify a specific format with which to print every album
or track. This uses the same template syntax as beets' :doc:`path formats
<pathformat>`. For example, the command ``beet ls -af '$album: $tracktotal'
beatles`` prints out the number of tracks on each Beatles album. In Unix shells,
remember to enclose the template argument in single quotes to avoid environment
variable expansion.

.. _xargs: http://en.wikipedia.org/wiki/Xargs

.. _remove-cmd:

remove
``````
::

    beet remove [-ad] QUERY

Remove music from your library.

This command uses the same :doc:`query <query>` syntax as the ``list`` command.
You'll be shown a list of the files that will be removed and asked to confirm.
By default, this just removes entries from the library database; it doesn't
touch the files on disk. To actually delete the files, use ``beet remove -d``.

.. _modify-cmd:

modify
``````
::

    beet modify [-MWay] QUERY FIELD=VALUE...

Change the metadata for items or albums in the database.

Supply a :doc:`query <query>` matching the things you want to change and a
series of ``field=value`` pairs. For example, ``beet modify genius of love
artist="Tom Tom Club"`` will change the artist for the track "Genius of Love."
The ``-a`` switch operates on albums instead of individual tracks. Items will
automatically be moved around when necessary if they're in your library
directory, but you can disable that with ``-M``. Tags will be written to the
files according to the settings you have for imports, but these can be
overridden with ``-w`` (write tags, the default) and ``-W`` (don't write tags).
Finally, this command politely asks for your permission before making any
changes, but you can skip that prompt with the ``-y`` switch.

.. _move-cmd:

move
````
::

    beet move [-ca] [-d DIR] QUERY

Move or copy items in your library.

This command, by default, acts as a library consolidator: items matching the
query are renamed into your library directory structure. By specifying a
destination directory with ``-d`` manually, you can move items matching a query
anywhere in your filesystem. The ``-c`` option copies files instead of moving
them. As with other commands, the ``-a`` option matches albums instead of items.

.. _update-cmd:

update
``````
::

    beet update [-aM] QUERY

Update the library (and, optionally, move files) to reflect out-of-band metadata
changes and file deletions.

This will scan all the matched files and read their tags, populating the
database with the new values. By default, files will be renamed according to
their new metadata; disable this with ``-M``.

To perform a "dry run" of an update, just use the ``-p`` (for "pretend") flag.
This will show you all the proposed changes but won't actually change anything
on disk.

When an updated track is part of an album, the album-level fields of *all*
tracks from the album are also updated. (Specifically, the command copies
album-level data from the first track on the album and applies it to the
rest of the tracks.) This means that, if album-level fields aren't identical
within an album, some changes shown by the ``update`` command may be
overridden by data from other tracks on the same album. This means that
running the ``update`` command multiple times may show the same changes being
applied.


.. _write-cmd:

write
`````
::

    beet write [-ap] [QUERY]

Write metadata from the database into files' tags.

When you make changes to the metadata stored in beets' library database
(during import or with the :ref:`modify-cmd` command, for example), you often
have the option of storing changes only in the database, leaving your files
untouched. The ``write`` command lets you later change your mind and write the
contents of the database into the files.

The ``-p`` option previews metadata changes without actually applying them.

You can think of this command as the opposite of :ref:`update-cmd`.


.. _stats-cmd:

stats
`````
::

    beet stats [-e] [QUERY]

Show some statistics on your entire library (if you don't provide a
:doc:`query <query>`) or the matched items (if you do).

The ``-e`` (``--exact``) option makes the calculation of total file size more
accurate but slower.

.. _fields-cmd:

fields
``````
::

    beet fields

Show the item and album metadata fields available for use in :doc:`query` and
:doc:`pathformat`. Includes any template fields provided by plugins.

.. _global-flags:

Global Flags
------------

Beets has a few "global" flags that affect all commands. These must appear
between the executable name (``beet``) and the command---for example, ``beet -v
import ...``.

* ``-l LIBPATH``: specify the library database file to use.
* ``-d DIRECTORY``: specify the library root directory.
* ``-v``: verbose mode; prints out a deluge of debugging information. Please use
  this flag when reporting bugs.
* ``-c FILE``: read a specified YAML :doc:`configuration file <config>`.

Beets also uses the ``BEETSDIR`` environment variable to look for
configuration and data.

.. only:: man

    See Also
    --------

    ``http://beets.readthedocs.org/``

    :manpage:`beetsconfig(5)`
