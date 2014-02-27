Configuration
=============

Beets has an extensive configuration system that lets you customize nearly
every aspect of its operation. To configure beets, you'll edit a file called
``config.yaml``. The location of this file depends on your OS:

* On Unix-like OSes, you want ``~/.config/beets/config.yaml``.
* On Windows, use ``%APPDATA%\beets\config.yaml``. This is usually in a
  directory like ``C:\Users\You\AppData\Roaming``.
* On OS X, you can use either the Unix location or ``~/Library/Application
  Support/beets/config.yaml``.

It is also possible to customize the location of the configuration file and
even use multiple layers of configuration. See `Configuration Location`_,
below.

The config file uses `YAML`_ syntax. You can use the full power of YAML, but
most configuration options are simple key/value pairs. This means your config
file will look like this::

    option: value
    another_option: foo
    bigger_option:
        key: value
        foo: bar

In YAML, you will need to use spaces (not tabs!) to indent some lines. If you
have questions about more sophisticated syntax, take a look at the `YAML`_
documentation.

.. _YAML: http://yaml.org/

The rest of this page enumerates the dizzying litany of configuration options
available in beets. You might also want to see an
:ref:`example <config-example>`.

.. contents::
    :local:
    :depth: 2

Global Options
--------------

These options control beets' global operation.

library
~~~~~~~

Path to the beets library file. By default, beets will use a file called
``library.db`` alongside your configuration file.

directory
~~~~~~~~~

The directory to which files will be copied/moved when adding them to the
library. Defaults to a folder called ``Music`` in your home directory.

plugins
~~~~~~~

A space-separated list of plugin module names to load. See
:ref:`using-plugins`.

pluginpath
~~~~~~~~~~

Directories to search for plugins.  Each Python file or directory in a plugin
path represents a plugin and should define a subclass of :class:`BeetsPlugin`.
A plugin can then be loaded by adding the filename to the `plugins` configuration.
The plugin path can either be a single string or a list of strings---so, if you
have multiple paths, format them as a YAML list like so::

    pluginpath:
        - /path/one
        - /path/two

ignore
~~~~~~

A list of glob patterns specifying file and directory names to be ignored when
importing. By default, this consists of ``.*``,  ``*~``, and ``System Volume
Information`` (i.e., beets ignores Unix-style hidden files, backup files, and
a directory that appears at the root of some Windows filesystems).

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

.. _original_date:

original_date
~~~~~~~~~~~~~

Either ``yes`` or ``no``, indicating whether matched albums should have their
``year``, ``month``, and ``day`` fields set to the release date of the
*original* version of an album rather than the selected version of the release.
That is, if this option is turned on, then ``year`` will always equal
``original_year`` and so on. Default: ``no``.

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

.. _terminal_encoding:

terminal_encoding
~~~~~~~~~~~~~~~~~

The text encoding, as `known to Python`_, to use for messages printed to the
standard output. By default, this is determined automatically from the locale
environment variables.

.. _known to python: http://docs.python.org/2/library/codecs.html#standard-encodings

.. _clutter:

clutter
~~~~~~~

When beets imports all the files in a directory, it tries to remove the
directory if it's empty. A directory is considered empty if it only contains
files whose names match the glob patterns in `clutter`, which should be a list
of strings. The default list consists of "Thumbs.DB" and ".DS_Store".

.. _max_filename_length:

max_filename_length
~~~~~~~~~~~~~~~~~~~

Set the maximum number of characters in a filename, after which names will be
truncated. By default, beets tries to ask the filesystem for the correct
maximum.

.. _id3v23:

id3v23
~~~~~~

By default, beets writes MP3 tags using the ID3v2.4 standard, the latest
version of ID3. Enable this option to instead use the older ID3v2.3 standard,
which is preferred by certain older software such as Windows Media Player.


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

.. _none_rec_action:

none_rec_action
~~~~~~~~~~~~~~~

Either ``ask`` (default), ``asis`` or ``skip``. Specifies what should happen
during an interactive import session when there is no recommendation. Useful
when you are only interested in processing medium and strong recommendations
interactively.

timid
~~~~~

Either ``yes`` or ``no``, controlling whether the importer runs in *timid*
mode, in which it asks for confirmation on every autotagging match, even the
ones that seem very close. Defaults to ``no``. The ``-t`` command-line flag
controls the same setting.

.. _import_log:

log
~~~

Specifies a filename where the importer's log should be kept.  By default,
no log is written. This can be overridden with the ``-l`` flag to
``import``.

.. _default_action:

default_action
~~~~~~~~~~~~~~

One of ``apply``, ``skip``, ``asis``, or ``none``, indicating which option
should be the *default* when selecting an action for a given match. This is the
action that will be taken when you type return without an option letter. The
default is ``apply``.

.. _languages:

languages
~~~~~~~~~

A list of locale names to search for preferred aliases. For example, setting
this to "en" uses the transliterated artist name "Pyotr Ilyich Tchaikovsky"
instead of the Cyrillic script for the composer's name when tagging from
MusicBrainz. Defaults to an empty list, meaning that no language is preferred.

.. _detail:

detail
~~~~~~

Whether the importer UI should show detailed information about each match it
finds. When enabled, this mode prints out the title of every track, regardless
of whether it matches the original metadata. (The default behavior only shows
changes.) Default: ``no``.

.. _group_albums:

group_albums
~~~~~~~~~~~~

By default, the beets importer groups tracks into albums based on the
directories they reside in. This option instead uses files' metadata to
partition albums. Enable this option if you have directories that contain
tracks from many albums mixed together.

The ``--group-albums`` or ``-g`` option to the :ref:`import-cmd` command is
equivalent, and the *G* interactive option invokes the same workflow.

Default: ``no``.


.. _musicbrainz-config:

MusicBrainz Options
-------------------

If you run your own `MusicBrainz`_ server, you can instruct beets to use it
instead of the main server. Use the ``host`` and ``ratelimit`` options under a
``musicbrainz:`` header, like so::

    musicbrainz:
        host: localhost:5000
        ratelimit: 100

The ``host`` key, of course, controls the Web server hostname (and port,
optionally) that will be contacted by beets (default: musicbrainz.org). The
``ratelimit`` option, an integer, controls the number of Web service requests
per second (default: 1). **Do not change the rate limit setting** if you're
using the main MusicBrainz server---on this public server, you're `limited`_
to one request per second.

.. _limited: http://musicbrainz.org/doc/XML_Web_Service/Rate_Limiting
.. _MusicBrainz: http://musicbrainz.org/

.. _match-config:

Autotagger Matching Options
---------------------------

You can configure some aspects of the logic beets uses when automatically
matching MusicBrainz results under the ``match:`` section. To control how
*tolerant* the autotagger is of differences, use the ``strong_rec_thresh``
option, which reflects the distance threshold below which beets will make a
"strong recommendation" that the metadata be used. Strong recommendations
are accepted automatically (except in "timid" mode), so you can use this to
make beets ask your opinion more or less often.

The threshold is a *distance* value between 0.0 and 1.0, so you can think of it
as the opposite of a *similarity* value. For example, if you want to
automatically accept any matches above 90% similarity, use::

    match:
        strong_rec_thresh: 0.10

The default strong recommendation threshold is 0.04.

The ``medium_rec_thresh`` and ``rec_gap_thresh`` options work similarly. When a
match is above the *medium* recommendation threshold or the distance between it
and the next-best match is above the *gap* threshold, the importer will suggest
that match but not automatically confirm it. Otherwise, you'll see a list of
options to choose from.

.. _max_rec:

max_rec
~~~~~~~

As mentioned above, autotagger matches have *recommendations* that control how
the UI behaves for a certain quality of match. The recommendation for a certain
match is based on the overall distance calculation. But you can also control
the recommendation when a specific distance penalty is applied by defining
*maximum* recommendations for each field:

To define maxima, use keys under ``max_rec:`` in the ``match`` section. The
defaults are "medium" for missing and unmatched tracks and "strong" (i.e., no
maximum) for everything else::

    match:
        max_rec:
            missing_tracks: medium
            unmatched_tracks: medium

If a recommendation is higher than the configured maximum and the indicated
penalty is applied, the recommendation is downgraded. The setting for
each field can be one of ``none``, ``low``, ``medium`` or ``strong``. When the
maximum recommendation is ``strong``, no "downgrading" occurs. The available
penalty names here are:

* source
* artist
* album
* media
* mediums
* year
* country
* label
* catalognum
* albumdisambig
* album_id
* tracks
* missing_tracks
* unmatched_tracks
* track_title
* track_artist
* track_index
* track_length
* track_id

.. _preferred:

preferred
~~~~~~~~~

In addition to comparing the tagged metadata with the match metadata for
similarity, you can also specify an ordered list of preferred countries and
media types.

A distance penalty will be applied if the country or media type from the match
metadata doesn't match. The specified values are preferred in descending order
(i.e., the first item will be most preferred). Each item may be a regular
expression, and will be matched case insensitively. The number of media will
be stripped when matching preferred media (e.g. "2x" in "2xCD").

You can also tell the autotagger to prefer matches that have a release year
closest to the original year for an album.

Here's an example::

    match:
        preferred:
            countries: ['US', 'GB|UK']
            media: ['CD', 'Digital Media|File']
            original_year: yes

By default, none of these options are enabled.

.. _ignored:

ignored
~~~~~~~

You can completely avoid matches that have certain penalties applied by adding
the penalty name to the ``ignored`` setting::

    match:
        ignored: missing_tracks unmatched_tracks

The available penalties are the same as those for the :ref:`max_rec` setting.

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


Configuration Location
----------------------

The beets configuration file is usually located in a standard location that
depends on your OS, but there are a couple of ways you can tell beets where to
look.

Environment Variable
~~~~~~~~~~~~~~~~~~~~

First, you can set the ``BEETSDIR`` environment variable to a directory
containing a ``config.yaml`` file. This replaces your configuration in the
default location. This also affects where auxiliary files, like the library
database, are stored by default (that's where relative paths are resolved to).
This environment variable is useful if you need to manage multiple beets
libraries with separate configurations.

Command-Line Option
~~~~~~~~~~~~~~~~~~~

Alternatively, you can use the ``--config`` command-line option to indicate a
YAML file containing options that will then be merged with your existing
options (from ``BEETSDIR`` or the default locations). This is useful if you
want to keep your configuration mostly the same but modify a few options as a
batch. For example, you might have different strategies for importing files,
each with a different set of importer options.

Default Location
~~~~~~~~~~~~~~~~

In the absence of a ``BEETSDIR`` variable, beets searches a few places for
your configuration, depending on the platform:

- On Unix platforms, including OS X:``~/.config/beets`` and then
  ``$XDG_CONFIG_DIR/beets``, if the environment variable is set.
- On OS X, we also search ``~/Library/Application Support/beets`` before the
  Unixy locations.
- On Windows: ``~\AppData\Roaming\beets``, and then ``%APPDATA%\beets``, if
  the environment variable is set.

Beets uses the first directory in your platform's list that contains
``config.yaml``. If no config file exists, the last path in the list is used.


.. _config-example:

Example
-------

Here's an example file::

    library: /var/music.blb
    directory: /var/mp3
    import:
        copy: yes
        write: yes
        resume: ask
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

.. only:: man

    See Also
    --------

    ``http://beets.readthedocs.org/``

    :manpage:`beet(1)`
