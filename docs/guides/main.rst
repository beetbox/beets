Getting Started
===============

Welcome to `beets`_! This guide will help you begin using it to make your music
collection better.

.. _beets: http://beets.io/

Installing
----------

You will need Python. (Beets is written for `Python 2.7`_. 2.6 support has been
dropped, and Python 3.x is not yet supported.)

.. _Python 2.7: http://www.python.org/download/

* **Mac OS X** v10.7 (Lion) and later include Python 2.7 out of the box.

* On **Debian or Ubuntu**, depending on the version, beets is available as an
  official package (`Debian details`_, `Ubuntu details`_), so try typing:
  ``apt-get install beets``. But the version in the repositories might lag
  behind, so make sure you read the right version of these docs. If you want
  the latest version, you can get everything you need to install with pip
  as described below by running:
  ``apt-get install python-dev python-pip``

* On **Arch Linux**, `beets is in [community]`_, so just run ``pacman -S
  beets``. (There's also a bleeding-edge `dev package`_ in the AUR, which will
  probably set your computer on fire.)

* For **Gentoo Linux**, beets is in Portage as ``media-sound/beets``. Just run
  ``emerge beets`` to install. There are several USE flags available for
  optional plugin dependencies.

* On **FreeBSD**, there's a `beets port`_ at ``audio/beets``.

* On **OpenBSD**, beets can be installed with ``pkg_add beets``.

* For **Slackware**, there's a `SlackBuild`_ available.

* On **Fedora** 22 or later, there is a `DNF package`_ (or three)::

      $ sudo dnf install beets beets-plugins beets-doc

.. _copr: https://copr.fedoraproject.org/coprs/afreof/beets/
.. _dnf package: https://apps.fedoraproject.org/packages/beets
.. _SlackBuild: http://slackbuilds.org/repository/14.1/multimedia/beets/
.. _beets port: http://portsmon.freebsd.org/portoverview.py?category=audio&portname=beets
.. _beets from AUR: https://aur.archlinux.org/packages/beets-git/
.. _dev package: https://aur.archlinux.org/packages/beets-git/
.. _Debian details: http://packages.qa.debian.org/b/beets.html
.. _Ubuntu details: https://launchpad.net/ubuntu/+source/beets
.. _beets is in [community]: https://www.archlinux.org/packages/community/any/beets/

If you have `pip`_, just say ``pip install beets`` (you might need ``sudo`` in
front of that). On Arch, you'll need to use ``pip2`` instead of ``pip``.

To install without pip, download beets from `its PyPI page`_ and run ``python
setup.py install`` in the directory therein.

.. _its PyPI page: http://pypi.python.org/pypi/beets#downloads
.. _pip: http://pip.openplans.org/

The best way to upgrade beets to a new version is by running ``pip install -U
beets``. You may want to follow `@b33ts`_ on Twitter to hear about progress on
new versions.

.. _@b33ts: http://twitter.com/b33ts

Installing on Windows
^^^^^^^^^^^^^^^^^^^^^

Installing beets on Windows can be tricky. Following these steps might help you
get it right:

1. If you don't have it, `install Python`_ (you want Python 2.7).

2. If you haven't done so already, set your ``PATH`` environment variable to
   include Python and its scripts. To do so, you have to get the "Properties"
   window for "My Computer", then choose the "Advanced" tab, then hit the
   "Environment Variables" button, and then look for the ``PATH`` variable in
   the table. Add the following to the end of the variable's value:
   ``;C:\Python27;C:\Python27\Scripts``.

3. Next, `install pip`_ (if you don't have it already) by downloading and
   running the `get-pip.py`_ script.

4. Now install beets by running: ``pip install beets``

5. You're all set! Type ``beet`` at the command prompt to make sure everything's
   in order.

Windows users may also want to install a context menu item for importing files
into beets. Just download and open `beets.reg`_ to add the necessary keys to the
registry. You can then right-click a directory and choose "Import with beets".
If Python is in a nonstandard location on your system, you may have to edit the
command path manually.

Because I don't use Windows myself, I may have missed something. If you have
trouble or you have more detail to contribute here, please direct it to
`the mailing list`_.

.. _install Python: http://python.org/download/
.. _beets.reg: https://github.com/beetbox/beets/blob/master/extra/beets.reg
.. _install pip: http://www.pip-installer.org/en/latest/installing.html#install-pip
.. _get-pip.py: https://raw.github.com/pypa/pip/master/contrib/get-pip.py


Configuring
-----------

You'll want to set a few basic options before you start using beets. The
:doc:`configuration </reference/config>` is stored in a text file. You
can show its location by running ``beet config -p``, though it may not
exist yet. Run ``beet config -e`` to edit the configuration in your
favorite text editor. The file will start out empty, but here's good
place to start::

    directory: ~/music
    library: ~/data/musiclibrary.blb

Change that first path to a directory where you'd like to keep your music. Then,
for ``library``, choose a good place to keep a database file that keeps an index
of your music. (The config's format is `YAML`_. You'll want to configure your
text editor to use spaces, not real tabs, for indentation.)


The default configuration assumes you want to start a new organized music folder
(that ``directory`` above) and that you'll *copy* cleaned-up music into that
empty folder using beets' ``import`` command (see below). But you can configure
beets to behave many other ways:

* Start with a new empty directory, but *move* new music in instead of copying
  it (saving disk space). Put this in your config file::

        import:
            move: yes

* Keep your current directory structure; importing should never move or copy
  files but instead just correct the tags on music. Put the line ``copy: no``
  under the ``import:`` heading in your config file to disable any copying or
  renaming. Make sure to point ``directory`` at the place where your music is
  currently stored.

* Keep your current directory structure and *do not* correct files' tags: leave
  files completely unmodified on your disk. (Corrected tags will still be stored
  in beets' database, and you can use them to do renaming or tag changes later.)
  Put this in your config file::

        import:
            copy: no
            write: no

  to disable renaming and tag-writing.

There are approximately six million other configuration options you can set
here, including the directory and file naming scheme. See
:doc:`/reference/config` for a full reference.

.. _YAML: http://yaml.org/

Importing Your Library
----------------------

There are two good ways to bring your existing library into beets. You can
either: (a) quickly bring all your files with all their current metadata into
beets' database, or (b) use beets' highly-refined autotagger to find canonical
metadata for every album you import. Option (a) is really fast, but option (b)
makes sure all your songs' tags are exactly right from the get-go. The point
about speed bears repeating: using the autotagger on a large library can take a
very long time, and it's an interactive process. So set aside a good chunk of
time if you're going to go that route. For more on the interactive
tagging process, see :doc:`tagger`.

If you've got time and want to tag all your music right once and for all, do
this::

    $ beet import /path/to/my/music

(Note that by default, this command will *copy music into the directory you
specified above*. If you want to use your current directory structure, set the
``import.copy`` config option.) To take the fast,
un-autotagged path, just say::

    $ beet import -A /my/huge/mp3/library

Note that you just need to add ``-A`` for "don't autotag".

Adding More Music
-----------------

If you've ripped or... otherwise obtained some new music, you can add it with
the ``beet import`` command, the same way you imported your library. Like so::

    $ beet import ~/some_great_album

This will attempt to autotag the new album (interactively) and add it to your
library. There are, of course, more options for this command---just type ``beet
help import`` to see what's available.

Seeing Your Music
-----------------

If you want to query your music library, the ``beet list`` (shortened to ``beet
ls``) command is for you. You give it a :doc:`query string </reference/query>`,
which is formatted something like a Google search, and it gives you a list of
songs.  Thus::

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

As you can see, search terms by default search all attributes of songs. (They're
also implicitly joined by ANDs: a track must match *all* criteria in order to
match the query.) To narrow a search term to a particular metadata field, just
put the field before the term, separated by a : character. So ``album:bird``
only looks for ``bird`` in the "album" field of your songs. (Need to know more?
:doc:`/reference/query/` will answer all your questions.)

The ``beet list`` command has another useful option worth mentioning, ``-a``,
which searches for albums instead of songs::

    $ beet ls -a forever
    Bon Iver - For Emma, Forever Ago
    Freezepop - Freezepop Forever

So handy!

Beets also has a ``stats`` command, just in case you want to see how much music
you have::

    $ beet stats
    Tracks: 13019
    Total time: 4.9 weeks
    Total size: 71.1 GB
    Artists: 548
    Albums: 1094

Keep Playing
------------

This is only the beginning of your long and prosperous journey with beets. To
keep learning, take a look at :doc:`advanced` for a sampling of what else
is possible. You'll also want to glance over the :doc:`/reference/cli` page
for a more detailed description of all of beets' functionality.  (Like
deleting music! That's important.)

Also, check out :doc:`beets' plugins </plugins/index>`.  The
real power of beets is in its extensibility---with plugins, beets can do almost
anything for your music collection.

You can always get help using the ``beet help`` command. The plain ``beet help``
command lists all the available commands; then, for example, ``beet help
import`` gives more specific help about the ``import`` command.

Please let me know what you think of beets via `the mailing list`_ or
`Twitter`_.

.. _the mailing list: http://groups.google.com/group/beets-users
.. _twitter: http://twitter.com/b33ts
