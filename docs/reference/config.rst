Configuration
=============

Beets has an extensive configuration system that lets you customize nearly
every aspect of its operation. To configure beets, you'll edit a file called
``config.yaml``. The location of this file depends on your OS:

* On Unix-like OSes (including OS X), you want ``~/.config/beets/config.yaml``.
* On Windows, use ``%APPDATA%\beets\config.yaml``. This is usually in a
  directory like ``C:\Users\You\AppData\Roaming``.
* On OS X, you can also use ``~/Library/Application Support/beets/config.yaml``
  if you prefer that over the Unix-like ``~/.config``.
* If you prefer a different location, set the ``BEETSDIR`` environment variable
  to a path; beets will then look for a ``config.yaml`` in that directory.

The config file uses `YAML`_ syntax. You can use the full power of YAML, but
most configuration options are simple key/value pairs. This means your config
file will look like this::

    option: value
    another_option: foo
    bigger_option:
        key: value
        foo: bar

If you have questions about more sophisticated syntax, take a look at the
`YAML`_ documentation.

.. _YAML: http://yaml.org/

Global Options
--------------

These options control beets' global operation.

library
~~~~~~~

Path to the beets library file. By default, beets will use a file called
``beetsmusic.blb`` alongside your configuration file.

directory
~~~~~~~~~

The directory to which files will be copied/moved when adding them to the
library. Defaults to a folder called ``Music`` in your home directory.

plugins
~~~~~~~

A space-separated list of plugin module names to load. For instance, beets
includes the BPD plugin for playing music.

pluginpath
~~~~~~~~~~

A colon-separated list of directories to search for plugins.  These paths
are just added to ``sys.path`` before the plugins are loaded. The plugins
still have to be contained in a ``beetsplug`` namespace package.

ignore
~~~~~~

A space-separated list of glob patterns specifying file and directory names
to be ignored when importing. Defaults to ``.* *~`` (i.e., ignore
Unix-style hidden files and backup files).

.. _replace:

replace
~~~~~~~

A set of regular expression/replacement pairs to be applied to all filenames
created by beets. Typically, these replacements are used to avoid confusing
problems or errors with the filesystem (for example, leading dots, which hide
files on Unix, and trailing whitespace, which is illegal on Windows). To
override these substitutions, specify a mapping from regular expression to
replacement strings. For example, ``[xy]: z`` will make beets replace all
instances of the characters ``x`` or ``y`` with the character ``z``.

If you do change this value, be certain that you include at least enough
substitutions to avoid causing errors on your operating system. Here are
the default substitutions used by beets, which are sufficient to avoid
unexpected behavior on all popular platforms::

    replace:
        '[\\/]': _
        '^\.': _
        '[\x00-\x1f]': _
        '[<>:"\?\*\|]': _
        '\.$': _
        '\s+$': ''

These substitutions remove forward and back slashes, leading dots, and
control characters—all of which is a good idea on any OS. The fourth line
removes the Windows "reserved characters" (useful even on Unix for for
compatibility with Windows-influenced network filesystems like Samba).
Trailing dots and trailing whitespace, which can cause problems on Windows
clients, are also removed.

.. _art-filename:

art_filename
~~~~~~~~~~~~

When importing album art, the name of the file (without extension) where the
cover art image should be placed. This is a template string, so you can use any
of the syntax available to :doc:`/reference/pathformat`. Defaults to ``cover``
(i.e., images will be named ``cover.jpg`` or ``cover.png`` and placed in the
album's directory).

threaded
~~~~~~~~

Either ``yes`` or ``no``, indicating whether the autotagger should use
multiple threads. This makes things faster but may behave strangely.
Defaults to ``yes``.

color
~~~~~

Either ``yes`` or ``no``; whether to use color in console output (currently
only in the ``import`` command). Turn this off if your terminal doesn't
support ANSI colors.

timeout
~~~~~~~

The amount of time that the SQLite library should wait before raising an
exception when the database lock is contended. This should almost never need
to be changed except on very slow systems. Defaults to 5.0 (5 seconds).

.. _list_format_item:

list_format_item
~~~~~~~~~~~~~~~~

Format to use when listing *individual items* with the :ref:`list-cmd`
command and other commands that need to print out items. Defaults to
``$artist - $album - $title``. The ``-f`` command-line option overrides
this setting.

.. _list_format_album:

list_format_album
~~~~~~~~~~~~~~~~~

Format to use when listing *albums* with :ref:`list-cmd` and other
commands. Defaults to ``$albumartist - $album``. The ``-f`` command-line
option overrides this setting.

.. _per_disc_numbering:

per_disc_numbering
~~~~~~~~~~~~~~~~~~

A boolean controlling the track numbering style on multi-disc releases. By
default (``per_disc_numbering: no``), tracks are numbered per-release, so the
first track on the second disc has track number N+1 where N is the number of
tracks on the first disc. If this ``per_disc_numbering`` is enabled, then the
first track on each disc always has track number 1.

If you enable ``per_disc_numbering``, you will likely want to change your
:ref:`path-format-config` also to include ``$disc`` before ``$track`` to make
filenames sort correctly in album directories. For example, you might want to
use a path format like this::

    paths:
        default: $albumartist/$album%aunique{}/$disc-$track $title

Importer Options
----------------

The options that control the :ref:`import-cmd` command are indented under the
``import:`` key. For example, you might have a section in your configuration
file that looks like this::

    import:
        write: yes
        copy: yes
        resume: no

These options are available in this section:

write
~~~~~

Either ``yes`` or ``no``, controlling whether metadata (e.g., ID3) tags are
written to files when using ``beet import``. Defaults to ``yes``. The ``-w``
and ``-W`` command-line options override this setting.

copy
~~~~

Either ``yes`` or ``no``, indicating whether to **copy** files into the
library directory when using ``beet import``. Defaults to ``yes``.  Can be
overridden with the ``-c`` and ``-C`` command-line options.
    
The option is ignored if ``move`` is enabled (i.e., beets can move or
copy files but it doesn't make sense to do both).

move
~~~~

Either ``yes`` or ``no``, indicating whether to **move** files into the
library directory when using ``beet import``.
Defaults to ``no``. 

The effect is similar to the ``copy`` option but you end up with only
one copy of the imported file. ("Moving" works even across filesystems; if
necessary, beets will copy and then delete when a simple rename is
impossible.) Moving files can be risky—it's a good idea to keep a backup in
case beets doesn't do what you expect with your files.

This option *overrides* ``copy``, so enabling it will always move
(and not copy) files. The ``-c`` switch to the ``beet import`` command,
however, still takes precedence.

resume
~~~~~~

Either ``yes``, ``no``, or ``ask``. Controls whether interrupted imports
should be resumed. "Yes" means that imports are always resumed when
possible; "no" means resuming is disabled entirely; "ask" (the default)
means that the user should be prompted when resuming is possible. The ``-p``
and ``-P`` flags correspond to the "yes" and "no" settings and override this
option.

incremental
~~~~~~~~~~~

Either ``yes`` or ``no``, controlling whether imported directories are
recorded and whether these recorded directories are skipped.  This
corresponds to the ``-i`` flag to ``beet import``.

quiet_fallback
~~~~~~~~~~~~~~

Either ``skip`` (default) or ``asis``, specifying what should happen in
quiet mode (see the ``-q`` flag to ``import``, above) when there is no
strong recommendation.

timid
~~~~~

Either ``yes`` or ``no``, controlling whether the importer runs in *timid*
mode, in which it asks for confirmation on every autotagging match, even the
ones that seem very close. Defaults to ``no``. The ``-t`` command-line flag
controls the same setting.

log
~~~

Specifies a filename where the importer's log should be kept.  By default,
no log is written. This can be overridden with the ``-l`` flag to
``import``.

.. _path-format-config:

Path Format Configuration
-------------------------

You can also configure the directory hierarchy beets uses to store music.
These settings appear under the ``paths:`` key. Each string is a template
string that can refer to metadata fields like ``$artist`` or ``$title``. The
filename extension is added automatically. At the moment, you can specify three
special paths: ``default`` for most releases, ``comp`` for "various artist"
releases with no dominant artist, and ``singleton`` for non-album tracks. The
defaults look like this::

    paths:
        default: $albumartist/$album%aunique{}/$track $title
        singleton: Non-Album/$artist/$title
        comp: Compilations/$album%aunique{}/$track $title

Note the use of ``$albumartist`` instead of ``$artist``; this ensure that albums
will be well-organized. For more about these format strings, see
:doc:`pathformat`. The ``aunique{}`` function ensures that identically-named
albums are placed in different directories; see :ref:`aunique` for details.

In addition to ``default``, ``comp``, and ``singleton``, you can condition path
queries based on beets queries (see :doc:`/reference/query`). This means that a
config file like this::

    paths:
        albumtype:soundtrack: Soundtracks/$album/$track $title

will place soundtrack albums in a separate directory. The queries are tested in
the order they appear in the configuration file, meaning that if an item matches
multiple queries, beets will use the path format for the *first* matching query.

Note that the special ``singleton`` and ``comp`` path format conditions are, in
fact, just shorthand for the explicit queries ``singleton:true`` and
``comp:true``. In contrast, ``default`` is special and has no query equivalent:
the ``default`` format is only used if no queries match.

Example
-------

Here's an example file::

    library: /var/music.blb
    directory: /var/mp3
    path_format: $genre/$artist/$album/$track $title
    import:
        copy: yes
        write: yes
        resume: ask
        art: yes
        quiet_fallback: skip
        timid: no
        log: beetslog.txt
    ignore: .AppleDouble ._* *~ .DS_Store
    art_filename: albumart
    plugins: bpd
    pluginpath: ~/beets/myplugins
    threaded: yes
    color: yes

    paths:
        default: $genre/$albumartist/$album/$track $title
        singleton: Singletons/$artist - $title
        comp: $genre/$album/$track $title
        albumtype:soundtrack: Soundtracks/$album/$track $title

    bpd:
        host: 127.0.0.1
        port: 6600
        password: seekrit

(That ``[bpd]`` section configures the optional :doc:`BPD </plugins/bpd>`
plugin.)

.. only:: man

    See Also
    --------

    ``http://beets.readthedocs.org/``

    :manpage:`beet(1)`
