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

    The rest of this document describes the available
    commands. If you ever need a quick list of what's available, just
    type ``beet help`` or ``beet help COMMAND`` for help with a specific
    command.

    Beets also offers shell completion. For bash, see the `completion`_
    command; for zsh, see the accompanying `completion script`_ for the
    ``beet`` command.




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

    beet import [-CWAPRqst] [-l LOGPATH] PATH...
    beet import [options] -L QUERY

Add music to your library, attempting to get correct tags for it from
MusicBrainz.

Point the command at some music: directories, single files, or
compressed archives. The music will be copied to a configurable
directory structure and added to a library database. The command is
interactive and will try to get you to verify MusicBrainz tags that it
thinks are suspect. See the :doc:`autotagging guide </guides/tagger>`
for detail on how to use the interactive tag-correction flow.

Directories passed to the import command can contain either a single
album or many, in which case the leaf directories will be considered
albums (the latter case is true of typical Artist/Album organizations
and many people's "downloads" folders). The path can also be a single
song or an archive. Beets supports `zip` and `tar` archives out of the
box. To extract `rar` files, install the `rarfile`_ package and the
`unrar` command. To extract `7z` files, install the `py7zr`_ package.

Optional command flags:

* By default, the command copies files to your library directory and
  updates the ID3 tags on your music. In order to move the files, instead of
  copying, use the ``-m`` (move) option. If you'd like to leave your music
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

* When beets applies metadata to your music, it will retain the value of any
  existing tags that weren't overwritten, and import them into the database. You
  may prefer to only use existing metadata for finding matches, and to erase it
  completely when new metadata is applied. You can enforce this behavior with
  the ``--from-scratch`` option, or the ``from_scratch`` configuration option.

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

* If you want to preview which files would be imported, use the ``--pretend``
  option. If set, beets will just print a list of files that it would
  otherwise import.

* If you already have a metadata backend ID that matches the items to be
  imported, you can instruct beets to restrict the search to that ID instead of
  searching for other candidates by using the ``--search-id SEARCH_ID`` option.
  Multiple IDs can be specified by simply repeating the option several times.

* You can supply ``--set field=value`` to assign `field` to `value` on import.
  These assignments will merge with (and possibly override) the
  :ref:`set_fields` configuration dictionary. You can use the option multiple
  times on the command line, like so::

    beet import --set genre="Alternative Rock" --set mood="emotional"

.. _rarfile: https://pypi.python.org/pypi/rarfile/
.. _py7zr: https://pypi.org/project/py7zr/

.. only:: html

    .. _reimport:

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
"vegetables" in the title? Try ``beet list year:2009 title:vegetables``. You
can also specify the sort order. (Read more in :doc:`query`.)

You can use the ``-a`` switch to search for albums instead of individual items.
In this case, the queries you use are restricted to album-level fields: for
example, you can search for ``year:1969`` but query parts for item-level fields
like ``title:foo`` will be ignored. Remember that ``artist`` is an item-level
field; ``albumartist`` is the corresponding album field.

The ``-p`` option makes beets print out filenames of matched items, which might
be useful for piping into other Unix commands (such as `xargs`_). Similarly, the
``-f`` option lets you specify a specific format with which to print every album
or track. This uses the same template syntax as beets' :doc:`path formats
<pathformat>`. For example, the command ``beet ls -af '$album: $albumtotal'
beatles`` prints out the number of tracks on each Beatles album. In Unix shells,
remember to enclose the template argument in single quotes to avoid environment
variable expansion.

.. _xargs: https://en.wikipedia.org/wiki/Xargs

.. _remove-cmd:

remove
``````
::

    beet remove [-adf] QUERY

Remove music from your library.

This command uses the same :doc:`query <query>` syntax as the ``list`` command.
By default, it just removes entries from the library database; it doesn't
touch the files on disk. To actually delete the files, use the ``-d`` flag.
When the ``-a`` flag is given, the command operates on albums instead of
individual tracks.

When you run the ``remove`` command, it prints a list of all
affected items in the library and asks for your permission before removing
them. You can then choose to abort (type `n`), confirm (`y`), or interactively
choose some of the items (`s`). In the latter case, the command will prompt you
for every matching item or album and invite you to type `y` to remove the
item/album, `n` to keep it or `q` to exit and only remove the items/albums
selected up to this point.
This option lets you choose precisely which tracks/albums to remove without
spending too much time to carefully craft a query.
If you do not want to be prompted at all, use the ``-f`` option.

.. _modify-cmd:

modify
``````
::

    beet modify [-MWay] [-f FORMAT] QUERY [FIELD=VALUE...] [FIELD!...]

Change the metadata for items or albums in the database.

Supply a :doc:`query <query>` matching the things you want to change and a
series of ``field=value`` pairs. For example, ``beet modify genius of love
artist="Tom Tom Club"`` will change the artist for the track "Genius of Love."
To remove fields (which is only possible for flexible attributes), follow a
field name with an exclamation point: ``field!``.

The ``-a`` switch also operates on albums in addition to the individual tracks.
Without this flag, the command will only change *track-level* data, even if all
the tracks belong to the same album. If you want to change an *album-level*
field, such as ``year`` or ``albumartist``, you'll want to use the ``-a`` flag
to avoid a confusing situation where the data for individual tracks conflicts
with the data for the whole album.

Items will automatically be moved around when necessary if they're in your
library directory, but you can disable that with  ``-M``. Tags will be written
to the files according to the settings you have for imports, but these can be
overridden with ``-w`` (write tags, the default) and ``-W`` (don't write
tags).

When you run the ``modify`` command, it prints a list of all
affected items in the library and asks for your permission before making any
changes. You can then choose to abort the change (type `n`), confirm
(`y`), or interactively choose some of the items (`s`). In the latter case,
the command will prompt you for every matching item or album and invite you to
type `y` to apply the changes, `n` to discard them or `q` to exit and apply
the selected changes. This option lets you choose precisely which data to
change without spending too much time to carefully craft a query. To skip the
prompts entirely, use the ``-y`` option.

.. _move-cmd:

move
````
::

    beet move [-capt] [-d DIR] QUERY

Move or copy items in your library.

This command, by default, acts as a library consolidator: items matching the
query are renamed into your library directory structure. By specifying a
destination directory with ``-d`` manually, you can move items matching a query
anywhere in your filesystem. The ``-c`` option copies files instead of moving
them. As with other commands, the ``-a`` option matches albums instead of items.
The ``-e`` flag (for "export") copies files without changing the database.

To perform a "dry run", just use the ``-p`` (for "pretend") flag. This will
show you a list of files that would be moved but won't actually change anything
on disk. The ``-t`` option sets the timid mode which will ask again
before really moving or copying the files.

.. _update-cmd:

update
``````
::

    beet update [-F] FIELD [-aM] QUERY

Update the library (and, by default, move files) to reflect out-of-band metadata
changes and file deletions.

This will scan all the matched files and read their tags, populating the
database with the new values. By default, files will be renamed according to
their new metadata; disable this with ``-M``. Beets will skip files if their
modification times have not changed, so any out-of-band metadata changes must
also update these for ``beet update`` to recognise that the files have been
edited.

To perform a "dry run" of an update, just use the ``-p`` (for "pretend") flag.
This will show you all the proposed changes but won't actually change anything
on disk.

By default, all the changed metadata will be populated back to the database.
If you only want certain fields to be written, specify them with the ```-F```
flags (which can be used multiple times). For the list of supported fields,
please see ```beet fields```.

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

    beet write [-pf] [QUERY]

Write metadata from the database into files' tags.

When you make changes to the metadata stored in beets' library database
(during import or with the :ref:`modify-cmd` command, for example), you often
have the option of storing changes only in the database, leaving your files
untouched. The ``write`` command lets you later change your mind and write the
contents of the database into the files. By default, this writes the changes only if there is a difference between the database and the tags in the file.

You can think of this command as the opposite of :ref:`update-cmd`.

The ``-p`` option previews metadata changes without actually applying them.

The ``-f`` option forces a write to the file, even if the file tags match the database. This is useful for making sure that enabled plugins that run on write (e.g., the Scrub and Zero plugins) are run on the file.



.. _stats-cmd:

stats
`````
::

    beet stats [-e] [QUERY]

Show some statistics on your entire library (if you don't provide a
:doc:`query <query>`) or the matched items (if you do).

By default, the command calculates file sizes using their bitrate and
duration. The ``-e`` (``--exact``) option reads the exact sizes of each file
(but is slower). The exact mode also outputs the exact duration in seconds.

.. _fields-cmd:

fields
``````
::

    beet fields

Show the item and album metadata fields available for use in :doc:`query` and
:doc:`pathformat`. The listing includes any template fields provided by
plugins and any flexible attributes you've manually assigned to your items and
albums.

.. _config-cmd:

config
``````
::

    beet config [-pdc]
    beet config -e

Show or edit the user configuration. This command does one of three things:

* With no options, print a YAML representation of the current user
  configuration. With the ``--default`` option, beets' default options are
  also included in the dump.
* The ``--path`` option instead shows the path to your configuration file.
  This can be combined with the ``--default`` flag to show where beets keeps
  its internal defaults.
* By default, sensitive information like passwords is removed when dumping the
  configuration. The ``--clear`` option includes this sensitive data.
* With the ``--edit`` option, beets attempts to open your config file for
  editing. It first tries the ``$EDITOR`` environment variable and then a
  fallback option depending on your platform: ``open`` on OS X, ``xdg-open``
  on Unix, and direct invocation on Windows.


.. _global-flags:

Global Flags
------------

Beets has a few "global" flags that affect all commands. These must appear
between the executable name (``beet``) and the command---for example, ``beet -v
import ...``.

* ``-l LIBPATH``: specify the library database file to use.
* ``-d DIRECTORY``: specify the library root directory.
* ``-v``: verbose mode; prints out a deluge of debugging information. Please use
  this flag when reporting bugs. You can use it twice, as in ``-vv``, to make
  beets even more verbose.
* ``-c FILE``: read a specified YAML :doc:`configuration file <config>`. This
  configuration works as an overlay: rather than replacing your normal
  configuration options entirely, the two are merged. Any individual options set
  in this config file will override the corresponding settings in your base
  configuration.
* ``-p plugins``: specify a comma-separated list of plugins to enable. If
  specified, the plugin list in your configuration is ignored. The long form
  of this argument also allows specifying no plugins, effectively disabling
  all plugins: ``--plugins=``.
* ``-P plugins``: specify a comma-separated list of plugins to disable in a
  specific beets run. This will overwrite ``-p`` if used with it. To disable all plugins, use
  ``--plugins=`` instead.

Beets also uses the ``BEETSDIR`` environment variable to look for
configuration and data.


.. _completion:

Shell Completion
----------------

Beets includes support for shell command completion. The command ``beet
completion`` prints out a `bash`_ 3.2 script; to enable completion put a line
like this into your ``.bashrc`` or similar file::

    eval "$(beet completion)"

Or, to avoid slowing down your shell startup time, you can pipe the ``beet
completion`` output to a file and source that instead.

You will also need to source the `bash-completion`_ script, which is probably
available via your package manager. On OS X, you can install it via Homebrew
with ``brew install bash-completion``; Homebrew will give you instructions for
sourcing the script.

.. _bash-completion: https://github.com/scop/bash-completion
.. _bash: https://www.gnu.org/software/bash/

The completion script suggests names of subcommands and (after typing
``-``) options of the given command. If you are using a command that
accepts a query, the script will also complete field names. ::

    beet list ar[TAB]
    # artist:  artist_credit:  artist_sort:  artpath:
    beet list artp[TAB]
    beet list artpath\:

(Don't worry about the slash in front of the colon: this is a escape
sequence for the shell and won't be seen by beets.)

Completion of plugin commands only works for those plugins
that were enabled when running ``beet completion``. If you add a plugin
later on you will want to re-generate the script.

zsh
```

If you use zsh, take a look at the included `completion script`_. The script
should be placed in a directory that is part of your ``fpath``, and `not`
sourced in your ``.zshrc``. Running ``echo $fpath`` will give you a list of
valid directories.

Another approach is to use zsh's bash completion compatibility. This snippet
defines some bash-specific functions to make this work without errors::

    autoload bashcompinit
    bashcompinit
    _get_comp_words_by_ref() { :; }
    compopt() { :; }
    _filedir() { :; }
    eval "$(beet completion)"

.. _completion script: https://github.com/beetbox/beets/blob/master/extra/_beet


.. only:: man

    See Also
    --------

    ``https://beets.readthedocs.org/``

    :manpage:`beetsconfig(5)`
