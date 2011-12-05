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
    to be ignored when importing. Defaults to ``.AppleDouble ._* *~ .DS_Store``.

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

You can also configure the directory hierarchy beets uses to store music. That
uses the ``[paths]`` section instead of the ``[beets]`` section. Each string is
a `Python template string`_ that can refer to metadata fields (see below for
examples). The extension is added automatically to the end. At the moment, you
can specify two special paths: ``default`` (for most releases) and ``comp`` (for
"various artist" releases with no dominant artist). You can also specify a
different path format for each `MusicBrainz release type`_. The defaults look
like this::

    [paths]
    default: $albumartist/$album/$track $title
    comp: Compilations/$album/$track title
    singleton: Non-Album/$artist/$title

Note the use of ``$albumartist`` instead of ``$artist``; this ensure that albums
will be well-organized. (For more about these format strings, see
:doc:`pathformat`.)

.. _Python template string:
    http://docs.python.org/library/string.html#template-strings 
.. _MusicBrainz release type:
    http://wiki.musicbrainz.org/ReleaseType 

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
    soundtrack: Soundtracks/$album/$track $title
    comp: $genre/$album/$track $title
    singleton: Singletons/$artist - $track

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
