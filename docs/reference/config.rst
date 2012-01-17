.beetsconfig
============

The ``beet`` command reads configuration information from ``~/.beetsconfig`` on
Unix-like OSes (inluding Mac OS X) and ``%APPDATA%\beetsconfig.ini`` on Windows.
The file is in INI format.

Options
-------

These options are available, all of which must appear under the ``[beets]``
section header:

``library``
    Path to the beets library file. Defaults to ``~/.beetsmusic.blb`` on Unix
    and ``%APPDATA\beetsmusic.blb`` on Windows.

``directory``
    The directory to which files will be copied/moved when adding them to the
    library. Defaults to ``~/Music``.

``import_copy``
    Either ``yes`` or ``no``, indicating whether to copy files into the library
    directory when using ``beet import``. Defaults to ``yes``.  Can be
    overridden with the ``-c`` and ``-C`` command-line options.

``import_write``
    Either ``yes`` or ``no``, controlling whether metadata (e.g., ID3) tags are
    written to files when using ``beet import``. Defaults to ``yes``. The ``-w``
    and ``-W`` command-line options override this setting.

``import_delete``
    Either ``yes`` or ``no``. When enabled in conjunction with ``import_copy``,
    deletes original files after they are copied into your library. This might
    be useful, for example, if you're low on disk space -- but it's risky!
    Defaults to ``no``.

``import_resume``
    Either ``yes``, ``no``, or ``ask``. Controls whether interrupted imports
    should be resumed. "Yes" means that imports are always resumed when
    possible; "no" means resuming is disabled entirely; "ask" (the default)
    means that the user should be prompted when resuming is possible. The ``-p``
    and ``-P`` flags correspond to the "yes" and "no" settings and override this
    option.

``import_incremental``
    Either ``yes`` or ``no``, controlling whether imported directories are
    recorded and whether these recorded directories are skipped.  This
    corresponds to the ``-i`` flag to ``beet import``.

``import_art``
    Either ``yes`` or ``no``, indicating whether the autotagger should attempt
    to find and download album cover art for the files it imports.  Defaults to
    ``yes``. The ``-r`` and ``-R`` command-line options override this setting.

``import_quiet_fallback``
    Either ``skip`` (default) or ``asis``, specifying what should happen in
    quiet mode (see the ``-q`` flag to ``import``, above) when there is no
    strong recommendation.

``import_timid``
    Either ``yes`` or ``no``, controlling whether the importer runs in *timid*
    mode, in which it asks for confirmation on every autotagging match, even the
    ones that seem very close. Defaults to ``no``. The ``-t`` command-line flag
    controls the same setting.

``import_log``
    Specifies a filename where the importer's log should be kept.  By default,
    no log is written. This can be overridden with the ``-l`` flag to
    ``import``.

``ignore``
    A space-separated list of glob patterns specifying file and directory names
    to be ignored when importing. Defaults to ``.* *~`` (i.e., ignore
    Unix-style hidden files and backup files).

``replace``
    A set of regular expression/replacement pairs to be applied to all filenames
    created by beets. Typically, these replacements are used to avoid confusing
    problems or errors with the filesystem (for example, leading ``.``
    characters are replaced on Unix and the ``*<>|`` characters are removed on
    Windows). To override these substitutions, specify a sequence of
    whitespace-separated terms; the first term is a regular expression and the
    second is a string that should replace anything matching that regex. For
    example, ``replace = [xy] z`` will make beets replace all instances of the
    characters ``x`` or ``y`` with the character ``z``.

    If you do change this value, be certain that you include at least enough
    substitutions to avoid causing errors on your operating system. Here are
    some recommended base replacements for Unix-like OSes::

        replace = [\\/\?"]|^\.' _
                  : -

    And, on Windows::

        replace = [\\/\?"]|^\.' _
                  ["\*<>\|]|^\.|\.$|\s+$ _
                  : -

    Note that the above examples are, in fact, the default substitutions used by
    beets.

``art_filename``
    When importing album art, the name of the file (without extension) where the
    cover art image should be placed. Defaults to ``cover`` (i.e., images will
    be named ``cover.jpg`` or ``cover.png`` and placed in the album's
    directory).

``plugins``
    A space-separated list of plugin module names to load. For instance, beets
    includes the BPD plugin for playing music.

``pluginpath``
    A colon-separated list of directories to search for plugins.  These paths
    are just added to ``sys.path`` before the plugins are loaded. The plugins
    still have to be contained in a ``beetsplug`` namespace package.

``threaded``
    Either ``yes`` or ``no``, indicating whether the autotagger should use
    multiple threads. This makes things faster but may behave strangely.
    Defaults to ``yes``.

``color``
    Either ``yes`` or ``no``; whether to use color in console output (currently
    only in the ``import`` command). Turn this off if your terminal doesn't
    support ANSI colors.

``timeout``
    The amount of time that the SQLite library should wait before raising an
    exception when the database lock is contended. This should almost never need
    to be changed except on very slow systems. Defaults to 5.0 (5 seconds).

.. _path-format-config:

Path Format Configuration
-------------------------

You can also configure the directory hierarchy beets uses to store music.  These
settings appear under the ``[paths]`` section (rather than the main ``[beets]``
section we used above).  Each string is a template string that can refer to
metadata fields like ``$artist`` or ``$title``. The filename extension is added
automatically. At the moment, you can specify three special paths: ``default``
for most releases, ``comp`` for "various artist" releases with no dominant
artist, and ``singleton`` for non-album tracks. The defaults look like this::

    [paths]
    default: $albumartist/$album/$track $title
    singleton: Non-Album/$artist/$title
    comp: Compilations/$album/$track title

Note the use of ``$albumartist`` instead of ``$artist``; this ensure that albums
will be well-organized. For more about these format strings, see
:doc:`pathformat`.

In addition to ``default``, ``comp``, and ``singleton``, you can condition path
queries based on beets queries (see :doc:`/reference/query`). There's one catch:
because the ``:`` character is reserved for separating the query from the
template string, the ``_`` character is substituted for ``:`` in these queries.
This means that a config file like this::

    [paths]
    albumtype_soundtrack: Soundtracks/$album/$track title

will place soundtrack albums in a separate directory. The queries are tested in
the order they appear in the configuration file, meaning that if an item matches
multiple queries, beets will use the path format for the *first* matching query.

Note that the special ``singleton`` and ``comp`` path format conditions are, in
fact, just shorthand for the explicit queries ``singleton_true`` and
``comp_true``. In contrast, ``default`` is special and has no query equivalent:
the ``default`` format is only used if no queries match.

Example
-------

Here's an example file::

    [beets]
    library: /var/music.blb
    directory: /var/mp3
    path_format: $genre/$artist/$album/$track $title
    import_copy: yes
    import_write: yes
    import_resume: ask
    import_art: yes
    import_quiet_fallback: skip
    import_timid: no
    import_log: beetslog.txt
    ignore: .AppleDouble ._* *~ .DS_Store
    art_filename: albumart
    plugins: bpd
    pluginpath: ~/beets/myplugins
    threaded: yes
    color: yes

    [paths]
    default: $genre/$albumartist/$album/$track $title
    singleton: Singletons/$artist - $title
    comp: $genre/$album/$track $title
    albumtype_soundtrack: Soundtracks/$album/$track $title

    [bpd]
    host: 127.0.0.1
    port: 6600
    password: seekrit

(That ``[bpd]`` section configures the optional :doc:`BPD </plugins/bpd>`
plugin.)

Location
--------

The configuration file is typically located at ``$HOME/.beetsconfig``. If you
want to store your ``.beetsconfig`` file somewhere else for whatever reason, you
can specify its path by setting the ``BEETSCONFIG`` environment variable.

.. only:: man

    See Also
    --------

    ``http://beets.readthedocs.org/``

    :manpage:`beet(1)`
