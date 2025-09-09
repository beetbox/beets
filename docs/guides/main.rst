Getting Started
===============

Welcome to beets_! This guide will help you begin using it to make your music
collection better.

.. _beets: https://beets.io/

Installing
----------

Beets requires Python 3.9 or later, you will need to install that first.
Depending on your operating system, you may also be able to install beets from a
package manager, or you can install it with pipx_ or pip_.

Using ``pipx``
~~~~~~~~~~~~~~

To use the most recent version of beets, we recommend installing it with pipx_.
If you don't have pipx_ installed, you can follow the instructions on the `pipx
installation page`_ to get it set up.

.. code-block:: console

    pipx install beets

Using ``pip``
~~~~~~~~~~~~~

If you prefer to use pip_, you can install beets with the following command:

.. code-block:: console

    pip install beets
    # or, to install for the current user only:
    pip install --user beets

.. _pip: https://pip.pypa.io/en/

.. _pipx: https://pipx.pypa.io/stable

.. _pipx installation page: https://pipx.pypa.io/stable/installation/

Using a Package Manager
~~~~~~~~~~~~~~~~~~~~~~~

Depending on your operating system, you may be able to install beets using a
package manager. Here are some common options:

.. attention::

    Package manager installations may not provide the latest version of beets.

    Release cycles for package managers vary, and they may not always have the
    most recent version of beets. If you want the latest features and fixes,
    consider using pipx_ or pip_ as described above.

    Additionally, installing external beets plugins may be surprisingly
    difficult when using a package manager.

- On **Debian or Ubuntu**, depending on the version, beets is available as an
  official package (`Debian details`_, `Ubuntu details`_), so try typing:
  ``apt-get install beets``. But the version in the repositories might lag
  behind, so make sure you read the right version of these docs. If you want the
  latest version, you can get everything you need to install with pip as
  described below by running: ``apt-get install python-dev python-pip``
- On **Arch Linux**, `beets is in [extra] <arch extra_>`_, so just run ``pacman
  -S beets``. (There's also a bleeding-edge `dev package <aur_>`_ in the AUR,
  which will probably set your computer on fire.)
- On **Alpine Linux**, `beets is in the community repository <alpine package_>`_
  and can be installed with ``apk add beets``.
- On **Void Linux**, `beets is in the official repository <void package_>`_ and
  can be installed with ``xbps-install -S beets``.
- For **Gentoo Linux**, beets is in Portage as ``media-sound/beets``. Just run
  ``emerge beets`` to install. There are several USE flags available for
  optional plugin dependencies.
- On **FreeBSD**, there's a `beets port <freebsd_>`_ at ``audio/beets``.
- On **OpenBSD**, there's a `beets port <openbsd_>`_ can be installed with
  ``pkg_add beets``.
- On **Fedora** 22 or later, there's a `DNF package`_ you can install with
  ``sudo dnf install beets beets-plugins beets-doc``.
- On **Solus**, run ``eopkg install beets``.
- On **NixOS**, there's a `package <nixos_>`_ you can install with ``nix-env -i
  beets``.
- Using **MacPorts**, run ``port install beets`` or ``port install beets-full``
  to include many third-party plugins.

.. _alpine package: https://pkgs.alpinelinux.org/package/edge/community/x86_64/beets

.. _arch extra: https://archlinux.org/packages/extra/any/beets/

.. _aur: https://aur.archlinux.org/packages/beets-git/

.. _debian details: https://tracker.debian.org/pkg/beets

.. _dnf package: https://packages.fedoraproject.org/pkgs/beets/

.. _freebsd: http://portsmon.freebsd.org/portoverview.py?category=audio&portname=beets

.. _nixos: https://github.com/NixOS/nixpkgs/tree/master/pkgs/tools/audio/beets

.. _openbsd: http://openports.se/audio/beets

.. _ubuntu details: https://launchpad.net/ubuntu/+source/beets

.. _void package: https://github.com/void-linux/void-packages/tree/master/srcpkgs/beets

Installing on Windows
+++++++++++++++++++++

Installing beets on Windows can be tricky. Following these steps might help you
get it right:

1. If you don't have it, `install Python`_ (you want at least Python 3.9). The
   installer should give you the option to "add Python to PATH." Check this box.
   If you do that, you can skip the next step.
2. If you haven't done so already, set your ``PATH`` environment variable to
   include Python and its scripts. To do so, open the "Settings" application,
   then access the "System" screen, then access the "About" tab, and then hit
   "Advanced system settings" located on the right side of the screen. This
   should open the "System Properties" screen, then select the "Advanced" tab,
   then hit the "Environmental Variables..." button, and then look for the PATH
   variable in the table. Add the following to the end of the variable's value:
   ``;C:\Python39;C:\Python39\Scripts``. You may need to adjust these paths to
   point to your Python installation.
3. Now install beets by running: ``pip install beets``
4. You're all set! Type ``beet`` at the command prompt to make sure everything's
   in order.

Windows users may also want to install a context menu item for importing files
into beets. Download the beets.reg_ file and open it in a text file to make sure
the paths to Python match your system. Then double-click the file add the
necessary keys to your registry. You can then right-click a directory and choose
"Import with beets".

If you have trouble or you have more detail to contribute here, please direct it
to `the discussion board`_.

.. _beets.reg: https://github.com/beetbox/beets/blob/master/extra/beets.reg

.. _get-pip.py: https://bootstrap.pypa.io/get-pip.py

.. _install pip: https://pip.pypa.io/en/stable/installing/

.. _install python: https://python.org/download/

Installing on ARM (Raspberry Pi and similar)
++++++++++++++++++++++++++++++++++++++++++++

Beets on ARM devices is not recommended for Linux novices. If you are
comfortable with light troubleshooting in tools like ``pip``, ``make``, and
beets' command-line binary dependencies (e.g. ``ffmpeg`` and ``ImageMagick``),
you will probably be okay on ARM devices like the Raspberry Pi. We have `notes
for ARM`_ and an `older ARM reference`_. Beets is generally developed on x86-64
based devices, and most plugins target that platform as well.

.. _notes for arm: https://github.com/beetbox/beets/discussions/4910

.. _older arm reference: https://discourse.beets.io/t/diary-of-beets-on-arm-odroid-hc4-armbian/1993

Configuring
-----------

You'll want to set a few basic options before you start using beets. The
:doc:`configuration </reference/config>` is stored in a text file. You can show
its location by running ``beet config -p``, though it may not exist yet. Run
``beet config -e`` to edit the configuration in your favorite text editor. The
file will start out empty, but here's good place to start:

::

    directory: ~/music
    library: ~/data/musiclibrary.db

Change that first path to a directory where you'd like to keep your music. Then,
for ``library``, choose a good place to keep a database file that keeps an index
of your music. (The config's format is YAML_. You'll want to configure your text
editor to use spaces, not real tabs, for indentation. Also, ``~`` means your
home directory in these paths, even on Windows.)

The default configuration assumes you want to start a new organized music folder
(that ``directory`` above) and that you'll *copy* cleaned-up music into that
empty folder using beets' ``import`` command (see below). But you can configure
beets to behave many other ways:

- Start with a new empty directory, but *move* new music in instead of copying
  it (saving disk space). Put this in your config file:

  ::

      import:
          move: yes

- Keep your current directory structure; importing should never move or copy
  files but instead just correct the tags on music. Put the line ``copy: no``
  under the ``import:`` heading in your config file to disable any copying or
  renaming. Make sure to point ``directory`` at the place where your music is
  currently stored.
- Keep your current directory structure and *do not* correct files' tags: leave
  files completely unmodified on your disk. (Corrected tags will still be stored
  in beets' database, and you can use them to do renaming or tag changes later.)
  Put this in your config file:

  ::

      import:
          copy: no
          write: no

  to disable renaming and tag-writing.

There are other configuration options you can set here, including the directory
and file naming scheme. See :doc:`/reference/config` for a full reference.

.. _yaml: https://yaml.org/

To check that you've set up your configuration how you want it, you can type
``beet version`` to see a list of enabled plugins or ``beet config`` to get a
complete listing of your current configuration.

Importing Your Library
----------------------

The next step is to import your music files into the beets library database.
Because this can involve modifying files and moving them around, data loss is
always a possibility, so now would be a good time to make sure you have a recent
backup of all your music. We'll wait.

There are two good ways to bring your existing library into beets. You can
either: (a) quickly bring all your files with all their current metadata into
beets' database, or (b) use beets' highly-refined autotagger to find canonical
metadata for every album you import. Option (a) is really fast, but option (b)
makes sure all your songs' tags are exactly right from the get-go. The point
about speed bears repeating: using the autotagger on a large library can take a
very long time, and it's an interactive process. So set aside a good chunk of
time if you're going to go that route. For more on the interactive tagging
process, see :doc:`tagger`.

If you've got time and want to tag all your music right once and for all, do
this:

::

    $ beet import /path/to/my/music

(Note that by default, this command will *copy music into the directory you
specified above*. If you want to use your current directory structure, set the
``import.copy`` config option.) To take the fast, un-autotagged path, just say:

::

    $ beet import -A /my/huge/mp3/library

Note that you just need to add ``-A`` for "don't autotag".

Adding More Music
-----------------

If you've ripped or... otherwise obtained some new music, you can add it with
the ``beet import`` command, the same way you imported your library. Like so:

::

    $ beet import ~/some_great_album

This will attempt to autotag the new album (interactively) and add it to your
library. There are, of course, more options for this command---just type ``beet
help import`` to see what's available.

Seeing Your Music
-----------------

If you want to query your music library, the ``beet list`` (shortened to ``beet
ls``) command is for you. You give it a :doc:`query string </reference/query>`,
which is formatted something like a Google search, and it gives you a list of
songs. Thus:

::

    $ beet ls the magnetic fields
    The Magnetic Fields - Distortion - Three-Way
    The Magnetic Fields - Distortion - California Girls
    The Magnetic Fields - Distortion - Old Fools
    $ beet ls hissing gronlandic
    of Montreal - Hissing Fauna, Are You the Destroyer? - Gronlandic Edit
    $ beet ls bird
    The Knife - The Knife - Bird
    The Mae Shi - Terrorbird - Revelation Six
    $ beet ls album:bird
    The Mae Shi - Terrorbird - Revelation Six

By default, a search term will match any of a handful of :ref:`common attributes
<keywordquery>` of songs. (They're also implicitly joined by ANDs: a track must
match *all* criteria in order to match the query.) To narrow a search term to a
particular metadata field, just put the field before the term, separated by a :
character. So ``album:bird`` only looks for ``bird`` in the "album" field of
your songs. (Need to know more? :doc:`/reference/query/` will answer all your
questions.)

The ``beet list`` command also has an ``-a`` option, which searches for albums
instead of songs:

::

    $ beet ls -a forever
    Bon Iver - For Emma, Forever Ago
    Freezepop - Freezepop Forever

There's also an ``-f`` option (for *format*) that lets you specify what gets
displayed in the results of a search:

::

    $ beet ls -a forever -f "[$format] $album ($year) - $artist - $title"
    [MP3] For Emma, Forever Ago (2009) - Bon Iver - Flume
    [AAC] Freezepop Forever (2011) - Freezepop - Harebrained Scheme

In the format option, field references like ``$format`` and ``$year`` are filled
in with data from each result. You can see a full list of available fields by
running ``beet fields``.

Beets also has a ``stats`` command, just in case you want to see how much music
you have:

::

    $ beet stats
    Tracks: 13019
    Total time: 4.9 weeks
    Total size: 71.1 GB
    Artists: 548
    Albums: 1094

Keep Playing
------------

This is only the beginning of your long and prosperous journey with beets. To
keep learning, take a look at :doc:`advanced` for a sampling of what else is
possible. You'll also want to glance over the :doc:`/reference/cli` page for a
more detailed description of all of beets' functionality. (Like deleting music!
That's important.)

Also, check out :doc:`beets' plugins </plugins/index>`. The real power of beets
is in its extensibility---with plugins, beets can do almost anything for your
music collection.

You can always get help using the ``beet help`` command. The plain ``beet help``
command lists all the available commands; then, for example, ``beet help
import`` gives more specific help about the ``import`` command.

If you need more of a walkthrough, you can read an illustrated one `on the beets
blog <https://beets.io/blog/walkthrough.html>`_.

Please let us know what you think of beets via `the discussion board`_ or
Mastodon_.

.. _mastodon: https://fosstodon.org/@beets

.. _the discussion board: https://github.com/beetbox/beets/discussions
