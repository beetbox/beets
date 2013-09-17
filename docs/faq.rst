FAQ
===

Here are some answers to frequently-asked questions from IRC and elsewhere.
Got a question that isn't answered? Try `IRC`_, the `mailing list`_, or
:ref:`filing an issue <bugs>` in the bug tracker.

.. _IRC: irc://irc.freenode.net/beets
.. _mailing list: http://groups.google.com/group/beets-users

.. contents::
    :local:
    :depth: 1

.. _nomatch:

Why can't beets find a match?
-----------------------------

Yes, this can happen. There are a number of possibilities:

-  First, make sure the album is in `the MusicBrainz
   database <http://musicbrainz.org/>`__ the MusicBrainz database. You
   can search on their site to make sure it's cataloged there. (If not,
   anyone can edit MusicBrainz---so consider adding the data yourself.)
-  If the album in question is a multi-disc release, see the relevant
   FAQ answer below.
-  The music files' metadata might be insufficient. Try using the "enter
   search" or "enter ID" options to help the matching process find the
   right MusicBrainz entry.
-  If you have a lot of files that are missing metadata, consider using
   :doc:`acoustic fingerprinting </plugins/chroma>` or
   :doc:`filename-based guesses </plugins/fromfilename>`
   for that music.

If none of these situations apply and you're still having trouble
tagging something, please :ref:`file a bug report <bugs>`.


.. _multidisc:

How does beets handle multi-disc albums?
----------------------------------------

As of 1.0b11, beets tags multi-disc albums as a *single unit*. To get a
good match, it needs to treat all of the album's parts together as a
single release.

To help with this, the importer uses a simple heuristic to guess when a
directory represents a multi-disc album that's been divided into
multiple subdirectories. When it finds a situation like this, it
collapses all of the items in the subdirectories into a single release
for tagging.

The heuristic works by looking at the names of directories. If multiple
subdirectories of a common parent directory follow the pattern "(title)
disc (number) (...)" and the *prefix* (everything up to the number) is
the same, the directories are collapsed together. One of the key words
"disc" or "CD" must be present to make this work.

If you have trouble tagging a multi-disc album, consider the ``--flat``
flag (which treats a whole tree as a single album) or just putting all
the tracks into a single directory to force them to be tagged together.


.. _mbid:

What is a MusicBrainz ID?
-------------------------

An MBID looks like one of these:

-  ``http://musicbrainz.org/release/ded77dcf-7279-457e-955d-625bd3801b87``
-  ``d569deba-8c6b-4d08-8c43-d0e5a1b8c7f3``

Beets can recognize either the hex-with-dashes UUID-style string or the
full URL that contains it (as of 1.0b11).

You can get these IDs by `searching on the MusicBrainz web
site <http://musicbrainz.org/>`__ and going to a *release* page (when
tagging full albums) or a *recording* page (when tagging singletons).
Then, copy the URL of the page and paste it into beets.

Note that MusicBrainz has both "releases" and "release groups," which
link together different versions of the same album. Use *release* IDs
here.


.. _plugins:

Why can't I use some of the included plugins?
---------------------------------------------

Please make sure you're using the latest version of beets---you might
be using a version earlier than the one that introduced the plugin. In
many cases, the plugin may be introduced in beets "trunk" (the latest
source version) and might not be released yet. Take a look at :doc:`the
changelog </changelog>`
to see which version added the plugin. (You can type ``beet version`` to
check which version of beets you have installed.)

If you want to live on the bleeding edge and use the latest source
version of beets, you can check out the source (see the next question).

To see the beets documentation for your version (and avoid confusion
with new features in trunk), select your version from the
left-hand sidebar (or the buttons at the bottom of the window).


.. _src:

How can I run the latest source version of beets?
-------------------------------------------------

Beets sees regular releases (about every six weeks or so), but sometimes
it's helpful to run on the "bleeding edge". To run the latest source:

1. Uninstall beets. If you installed using ``pip``, you can just run
   ``pip uninstall beets``.
2. Install from source. There are a few easy ways to do this:

   -  Use ``pip`` to install the latest snapshot tarball: just type
      ``pip install https://github.com/sampsyo/beets/tarball/master``.
   -  Grab the source using Mercurial
      (``hg clone https://bitbucket.org/adrian/beets``) or git
      (``git clone https://github.com/sampsyo/beets.git``). Then
      ``cd beets`` and type ``python setup.py install``.
   -  Use ``pip`` to install an "editable" version of beets based on an
      automatic source checkout. For example, run
      ``pip install -e hg+https://bitbucket.org/adrian/beets#egg=beets``
      to clone beets from BitBucket using Mercurial and install it,
      allowing you to modify the source in-place to try out changes.

More details about the beets source are available on the [[Hacking]]
page.


.. _bugs:

How do I report a bug in beets?
-------------------------------

We use the `issue tracker <https://github.com/sampsyo/beets/issues>`__
on GitHub. `Enter a new issue <https://github.com/sampsyo/beets/issues/new>`__
there to report a bug. Please follow these guidelines when reporting an issue:

-  Most importantly: if beets is crashing, please `include the
   traceback <http://imgur.com/jacoj>`__. Tracebacks can be more
   readable if you put them in a pastebin (e.g.,
   `Gist <https://gist.github.com/>`__ or
   `Hastebin <http://hastebin.com/>`__), especially when communicating
   over IRC or email.
-  Turn on beets' debug output (using the -v option: for example,
   ``beet -v import ...``) and include that with your bug report. Look
   through this verbose output for any red flags that might point to the
   problem.
-  If you can, try installing the latest beets source code to see if the
   bug is fixed in an unreleased version. You can also look at the
   :doc:`latest changelog entries </changelog>`
   for descriptions of the problem you're seeing.
-  Try to narrow your problem down to something specific. Is a
   particular plugin causing the problem? (You can disable plugins to
   see whether the problem goes away.) Is a some music file or a single
   album leading to the crash? (Try importing individual albums to
   determine which one is causing the problem.) Is some entry in your
   configuration file causing it? Et cetera.
-  If you do narrow the problem down to a particular audio file or
   album, include it with your bug report so the developers can run
   tests.

If you've never reported a bug before, Mozilla has some well-written
`general guidelines for good bug
reports <http://www.mozilla.org/bugs/>`__.


.. _kill:

Why doesn't control-C cancel a "beet import"?
---------------------------------------------

Typing a ^C (control-C) control sequence will not halt beets'
multithreaded importer while it is waiting at a prompt for user input.
Instead, hit "return" (dismissing the prompt) after typing ^C.
Alternatively, just type a "b" for "aBort" at most prompts. Typing ^C
*will* work if the importer interface is between prompts.

Also note that beets may take some time to quit after ^C is typed; it
tries to clean up after itself briefly even when canceled.

(For developers: this is because the UI thread is blocking on
``raw_input`` and cannot be interrupted by the main thread, which is
trying to close all pipeline stages in the exception handler by setting
a flag. There is no simple way to remedy this.)


.. _move:

How do I rename my files according to a new path format configuration?
----------------------------------------------------------------------

Just run the :ref:`move-cmd` command. Use a :doc:`query </reference/query>`
to rename a subset of your music or leave the query off to rename
everything.


.. _id3v24:

Why doesn't beets seem to update ID3 tags?
------------------------------------------

Beets writes `ID3v2.4 <http://www.id3.org/id3v2.4.0-structure>`__ tags.
Some software, including Windows (i.e., Windows Explorer and Windows
Media Player) and `id3lib/id3v2 <http://id3v2.sourceforge.net/>`__,
don't support v2.4 tags. When using 2.4-unaware software, it might look
like the tags are unmodified or missing completely.

This is due to `a limitation in the Mutagen
library <http://code.google.com/p/mutagen/wiki/FAQ>`__.


.. _upgrade:

How do I upgrade to the latest version of beets?
------------------------------------------------

Run a command like this::

    pip install -U beets

The ``-U`` flag tells `pip <http://www.pip-installer.org>`__ to upgrade
beets to the latest version. If you want a specific version, you can
specify with using ``==`` like so::

    pip install beets==1.0rc2


.. _invalid:

Why does beets complain that a file is "unreadable"?
----------------------------------------------------

Beets will log a message like "unreadable file: /path/to/music.mp3" when
it encounters files that *look* like music files (according to their
extension) but seem to be broken. Most of the time, this is because the
file is corrupted. To check whether the file is intact, try opening it
in another media player (e.g.,
`VLC <http://www.videolan.org/vlc/index.html>`__) to see whether it can
read the file. You can also use specialized programs for checking file
integrity---for example, type ``metaflac --list music.flac`` to check
FLAC files.

If beets still complains about a file that seems to be valid, `file a
bug <https://github.com/sampsyo/beets/issues/new>`__ and we'll look into
it. There's always a possibility that there's a bug "upstream" in the
`Mutagen <http://code.google.com/p/mutagen/>`__ library used by beets,
in which case we'll forward the bug to that project's tracker.


.. _asispostfacto:

How can I tell, after the fact, which albums I imported "as-is"?
----------------------------------------------------------------

Enable the :ref:`import log <import_log>`
to automatically record whenever you skip an album or accept one
"as-is".

Alternatively, you can find all the albums in your library that are
missing MBIDs using a command like this::

    beet ls -a mb_albumid::^$

Assuming your files didn't have MBIDs already, then this will roughly
correspond to those albums that didn't get autotagged.


.. _discdir:

Can I create "Disc N" directories for multi-disc albums?
--------------------------------------------------------

Use the :doc:`/plugins/inline` along
with the ``%if{}`` function to accomplish this::

    plugins: inline
    paths:
        default: $albumartist/$album%aunique{}/%if{$multidisc,Disc $disc/}$track $title
    item_fields:
        multidisc: 1 if disctotal > 1 else 0


.. _importhang:

Why does beets seem to "hang" after an import finishes?
-------------------------------------------------------

Probably not. Beets uses a *multithreaded importer* that overlaps many
different activities: it can prompt you for decisions while, in the
background, it talks to MusicBrainz and copies files. This means that,
even after you make your last decision, there may be a backlog of files
to be copied into place and tags to be written. (Plugin tasks, like
looking up lyrics and genres, also run at this time.) If beets pauses
after you see all the albums go by, have patience.


.. _replaceq:

Why do some of my filenames have underscores (\_s)?
---------------------------------------------------

When naming files, beets replaces certain characters to avoid causing
problems on the filesystem. For example, leading dots can confusingly
hide files on Unix and several non-alphanumeric characters are forbidden
on Windows.

The :ref:`replace` config option
controls which replacements are made. By default, beets makes filenames
safe for all known platforms by replacing several patterns with
underscores. This means that, even on Unix, filenames are made
Windows-safe so that network filesystems (such as SMB) can be used
safely.

Most notably, Windows forbids trailing dots, so a folder called "M.I.A."
will be rewritten to "M.I.A\_" by default. Change the ``replace`` config
if you don't want this behavior and don't need Windows-safe names.
