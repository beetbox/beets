Getting Started
===============

Welcome to `beets`_! This guide will help you begin using it to make your music
collection better.

.. _beets: http://beets.radbox.org/

Installing
----------

You will need Python. (Beets is written for `Python 2.7`_, but it works with
2.5 and 2.6 as well. Python 3.x is not yet supported.)

.. _Python 2.7: http://www.python.org/download/releases/2.7.1/

* **Mac OS X** v10.7 (Lion) includes Python 2.7 out of the box; Snow Leopard
  ships with Python 2.6.

* On **Ubuntu**, you can get everything you need by running:
  ``apt-get install python-dev python-setuptools python-pip``

* For **Arch Linux**, try getting `beets from AUR`_. (There's also a `dev
  package`_, which is likely broken.) If you don't want to use the AUR build,
  this suffices to get the dependencies: ``pacman -S base-devel python2-pip``

* If you're on **CentOS** 5, you have Python 2.4. To get 2.6,
  `try this yum repository`_.

.. _try this yum repository:
    http://chrislea.com/2009/09/09/easy-python-2-6-django-on-centos-5/
.. _beets from AUR: http://aur.archlinux.org/packages.php?ID=39577
.. _dev package: http://aur.archlinux.org/packages.php?ID=48617


If you have `pip`_, just say ``pip install beets`` (you might need ``sudo`` in
front of that). Otherwise, head over to the `Downloads`_ area, download the most
recent source distribution, and run ``python setup.py install`` in the directory
therein.

.. _pip: http://pip.openplans.org/
.. _Downloads: http://code.google.com/p/beets/downloads/list

The best way to upgrade beets to a new version is by running ``pip install -U
beets``. You may want to follow `@b33ts`_ on Twitter to hear about progress on
new versions.

.. _@b33ts: http://twitter.com/b33ts

Installing on Windows
^^^^^^^^^^^^^^^^^^^^^

Installing beets on Windows can be tricky. Following these steps might help you
get it right:

1. If you don't have it, `install Python`_ (you want Python 2.7).

.. _install Python: http://python.org/download/

2. Install `Setuptools`_ from PyPI. To do this, scroll to the bottom of that
   page and download the Windows installer (``.exe``, not ``.egg``) for your
   Python version (for example: ``setuptools-0.6c11.win32-py2.7.exe``).

.. _Setuptools: http://pypi.python.org/pypi/setuptools

3. If you haven't done so already, set your ``PATH`` environment variable to
   include Python and its scripts. To do so, you have to get the "Properties"
   window for "My Computer", then choose the "Advanced" tab, then hit the
   "Environment Variables" button, and then look for the ``PATH`` variable in
   the table. Add the following to the end of the variable's value:
   ``;C:\Python27;C:\Python27\Scripts``.

4. Open a command prompt and install pip by running: ``easy_install pip``

5. Now install beets by running: ``pip install beets``

6. You're all set! Type ``beet`` at the command prompt to make sure everything's
   in order.

Because I don't use Windows myself, I may have missed something. If you have
trouble or you have more detail to contribute here, please `let me know`_.

.. _let me know: mailto:adrian@radbox.org

Configuring
-----------

You'll want to set a few basic options before you start using beets. The
configuration is stored in a text file: on Unix-like OSes, the config file is at
``~/.beetsconfig``; on Windows, it's at ``%APPDATA%\beetsconfig.ini``. Create
and edit the appropriate file with your favorite text editor. This file will
start out empty, but here's good place to start::

    [beets]
    directory: ~/music
    library: ~/data/musiclibrary.blb

Change that first path to a directory where you'd like to keep your music. Then,
for ``library``, choose a good place to keep a database file that keeps an index
of your music.

Here, you can also change a few more options: you can leave files in place
instead of copying everything to your library folder; you can customize the
library's directory structure and naming scheme; you can also choose not to
write updated tags to files you import. If you're curious,
see :doc:`/reference/config`.

Importing Your Library
----------------------

There are two good ways to bring your existing library into beets. You can
either: (a) quickly bring all your files with all their current metadata into
beets' database, or (b) use beets' highly-refined autotagger to find canonical
metadata for every album you import. Option (a) is really fast, but option (b)
makes sure all your songs' tags are exactly right from the get-go. The point
about speed bears repeating: using the autotagger on a large library can take a
very long time, and it's an interactive process. So set aside a good chunk of
time if you're going to go that route. (I'm working on improving the
autotagger's performance and automation.) For more information on the
interactive tagging process, see :doc:`tagger`.

If you've got time and want to tag all your music right once and for all, do
this::

    $ beet import /path/to/my/music

(Note that by default, this command will *copy music into the directory you
specified above*. If you want to use your current directory structure, set the
``import_copy`` config option.) To take the fast,
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

By default, the ``import`` command will try to find and download album art for
every album it finds. It will store the art in a file called ``cover.jpg``
alongside the songs. If you don't like that, you can disable it with the ``-R``
switch or by setting a value in the :doc:`configuration file
</reference/config>`.

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

    $ ./beet stats
    Tracks: 13019
    Total time: 4.9 weeks
    Total size: 71.1 GB
    Artists: 548
    Albums: 1094

Playing Music
-------------

Beets is primarily intended as a music organizer, not a player. It's designed to
be used in conjunction with other players (consider `Decibel`_ or `cmus`_;
there's even :ref:`a cmus plugin for beets <other-plugins>`). However, it does
include a simple music player---it doesn't have a ton of features, but it gets
the job done.

.. _Decibel: http://decibel.silent-blade.org/
.. _cmus: http://cmus.sourceforge.net/

The player, called BPD, is a clone of an excellent music player called `MPD`_.
Like MPD, it runs as a daemon (i.e., without a user interface). Another program,
called an MPD client, controls the player and provides the user with an
interface. You'll need to enable the BPD plugin before you can use it. Check out
:doc:`/plugins/bpd`.

.. _MPD: http://mpd.wikia.com/

You can, of course, use the bona fide MPD server with your beets library. MPD is
a great player and has more features than BPD. BPD just provides a convenient,
built-in player that integrates tightly with your beets database.

Keep Playing
------------

The :doc:`/reference/cli` page has more detailed description of all of beets'
functionality.  (Like deleting music! That's important.) Start exploring!

Also, check out :ref:`included-plugins` as well as :ref:`other-plugins`.  The
real power of beets is in its extensibility---with plugins, beets can do almost
anything for your music collection.

You can always get help using the ``beet help`` command. The plain ``beet help``
command lists all the available commands; then, for example, ``beet help
import`` gives more specific help about the ``import`` command.

Please let me know what you think of beets via `email`_ or `Twitter`_.

.. _email: mailto:adrian@radbox.org
.. _twitter: http://twitter.com/b33ts
