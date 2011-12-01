Using the Auto-Tagger
=====================

Beets' automatic metadata correcter is sophisticated but complicated and
cryptic. This is a guide to help you through its myriad inputs and options.

An Apology and a Brief Interlude
--------------------------------

I would like to sincerely apologize that the autotagger in beets is so fussy. It
asks you a *lot* of complicated questions, insecurely asking that you verify
nearly every assumption it makes. This means importing and correcting the tags
for a large library can be an endless, tedious process. I'm sorry for this.

Maybe it will help to think of it as a tradeoff. By carefully examining every
album you own, you get to become more familiar with your library, its extent,
its variation, and its quirks. People used to spend hours lovingly sorting and
resorting their shelves of LPs. In the iTunes age, many of us toss our music
into a heap and forget about it. This is great for some people. But there's
value in intimate, complete familiarity with your collection. So instead of a
chore, try thinking of correcting tags as quality time with your music
collection. That's what I do.

One practical piece of advice: because beets' importer runs in multiple threads,
it queues up work in the background while it's waiting for you to respond. So if
you find yourself waiting for beets for a few seconds between every question it
asks you, try walking away from the computer for a while, making some tea, and
coming back. Beets will have a chance to catch up with you and will ask you
questions much more quickly.

Back to the guide.

Overview
--------

Beets' tagger is invoked using the ``beet import`` command. Point it at a
directory and it imports the files into your library, tagging them as it goes
(unless you pass ``--noautotag``, of course). There are several assumptions
beets currently makes about the music you import. In time, we'd like to remove
all of these limitations.

* Your music should be organized by album into directories. That is, the tagger
  assumes that each album is in a single directory. These directories can be
  arbitrarily deep (like ``music/2010/hiphop/seattle/freshespresso/glamour``),
  but any directory with music files in it is interpreted as a separate album.
  This means that your flat directory of six thousand uncategorized MP3s won't
  currently be autotaggable. (This will change eventually.)

  There is one exception to this rule: directories that look like separate parts
  of a *multi-disc album* are tagged together as a single release. This
  situation is detected by looking at the names of directories. If one directory
  has sub-directories with, for example, "disc 1" and "disc 2" in their names,
  they get lumped together as a single album. The marker words for this feature
  are "part", "volume", "vol.", "disc", and "CD".

* The music may have bad tags, but it's not completely untagged. (This is
  actually not a hard-and-fast rule: using the *E* option described below, it's
  entirely possible to search for a release to tag a given album.) This is
  because beets by default infers tags based on existing metadata. The
  :doc:`Acoustid plugin </plugins/chroma>` extends the autotagger to use
  acoustic fingerprinting to find information for arbitrary audio. Install that
  plugin if you're willing to spend a little more CPU power to get tags for
  unidentified albums.

* Currently MP3, AAC, FLAC, Ogg Vorbis, Monkey's Audio, WavPack, and Musepack
  files are supported. (Do you use some other format?
  `Let me know!`_

.. _Let me know!: mailto:adrian@radbox.org

Now that that's out of the way, let's tag some music.

Options
-------

To import music, just say ``beet import MUSICDIR``. There are, of course, a few
command-line options you should know:

* ``beet import -A``: don't try to autotag anything; just import files (this
  goes much faster than with autotagging enabled)

* ``beet import -W``: when autotagging, don't write new tags to the files
  themselves (just keep the new metadata in beets' database)

* ``beet import -C``: don't copy imported files to your music directory; leave
  them where they are

* ``beet import -R``: don't fetch album art.

* ``beet import -l LOGFILE``: write a message to ``LOGFILE`` every time you skip
  an album or choose to take its tags "as-is" (see below) or the album is
  skipped as a duplicate; this lets you come back later and reexamine albums
  that weren't tagged successfully

* ``beet import -q``: quiet mode. Never prompt for input and, instead,
  conservatively skip any albums that need your opinion. The ``-ql`` combination
  is recommended.

* ``beet import -t``: timid mode, which is sort of the opposite of "quiet." The
  importer will ask your permission for everything it does, confirming even very
  good matches with a prompt.

* ``beet import -p``: automatically resume an interrupted import. The importer
  keeps track of imports that don't finish completely (either due to a crash or
  because you stop them halfway through) and, by default, prompts you to decide
  whether to resume them. The ``-p`` flag automatically says "yes" to this
  question. Relatedly, ``-P`` flag automatically says "no."

* ``beet import -s``: run in *singleton* mode, tagging individual tracks instead
  of whole albums at a time. See the "as Tracks" choice below.  This means you
  can use ``beet import -AC`` to quickly add a bunch of files to your library
  without doing anything to them.

Similarity
----------

So you import an album into your beets library. It goes like this::

    $ beet imp witchinghour
    Tagging: Ladytron - Witching Hour
    (Similarity: 98.4%)
    * Last One Standing -> The Last One Standing
    * Beauty -> Beauty*2
    * White Light Generation -> Whitelightgenerator
    * All the Way -> All the Way...

Here, beets gives you a preview of the album match it has found. It shows you
which track titles will be changed if the match is applied. In this case, beets
has found a match and thinks it's a good enough match to proceed without asking
your permission. It has reported the *similarity* for the match it's found.
Similarity is a measure of how well-matched beets thinks a tagging option is.
100% similarity means a perfect match 0% indicates a truly horrible match.

In this case, beets has proceeded automatically because it found an option with
very high similarity (98.4%). But, as you'll notice, if the similarity isn't
quite so high, beets will ask you to confirm changes. This is because beets
can't be very confident about more dissimilar matches, and you (as a human) are
better at making the call than a computer. So it occasionally asks for help.

Choices
-------

When beets needs your input about a match, it says something like this::

    Tagging: Beirut - Lon Gisland
    (Similarity: 94.4%)
    * Scenic World (Second Version) -> Scenic World
    [A]pply, More candidates, Skip, Use as-is, as Tracks, Enter search, or aBort?

When beets asks you this question, it wants you to enter one of the capital letters: A, M, S, U, T, E, or B. That is, you can choose one of the following:

* *A*: Apply the suggested changes shown and move on.

* *M*: Show more options. (See the Candidates section, below.)

* *S*: Skip this album entirely and move on to the next one.

* *U*: Import the album without changing any tags. This is a good option for
  albums that aren't in the MusicBrainz database, like your friend's operatic
  faux-goth solo record that's only on two CD-Rs in the universe.

* *T*: Import the directory as *singleton* tracks, not as an album. Choose this
  if the tracks don't form a real release---you just have one or more loner
  tracks that aren't a full album. This will temporarily flip the tagger into
  *singleton* mode, which attempts to match each track individually.

* *E*: Enter an artist and album to use as a search in the database. Use this
  option if beets hasn't found any good options because the album is mistagged
  or untagged.

* *B*: Cancel this import task altogether. No further albums will be tagged;
  beets shuts down immediately. The next time you attempt to import the same
  directory, though, beets will ask you if you want to resume tagging where you
  left off.

Note that the option with ``[B]rackets`` is the default---so if you want to
apply the changes, you can just hit return without entering anything.

Candidates
----------

If you choose the M option, or if beets isn't very confident about any of the
choices it found, it will present you with a list of choices (called
candidates), like so::

    Finding tags for "Panther - Panther".
    Candidates:
    1. Panther - Yourself (66.8%)
    2. Tav Falco's Panther Burns - Return of the Blue Panther (30.4%)
    # selection (default 1), Skip, Use as-is, or Enter search, or aBort? 

Here, you have many of the same options as before, but you can also enter a
number to choose one of the options that beets has found. Don't worry about
guessing---beets will show you the proposed changes and ask you to confirm
them, just like the earlier example. As the prompt suggests, you can just hit
return to select the first candidate.

Fingerprinting
--------------

You may have noticed by now that beets' autotagger works pretty well for most
files, but can get confused when files don't have any metadata (or have wildly
incorrect metadata). In this case, you need *acoustic fingerprinting*, a
technology that identifies songs from the audio itself. With fingerprinting,
beets can autotag files that have very bad or missing tags. The :doc:`"chroma"
plugin </plugins/chroma>`, distributed with beets, uses the `Chromaprint`_ open-source fingerprinting technology, but it's disabled by default. That's because
it's sort of tricky to install. See the :doc:`/plugins/chroma` page for a guide
to getting it set up.

.. _Chromaprint: http://acoustid.org/chromaprint

Missing Albums?
---------------

If you're having trouble tagging a particular album with beets, you might want to check the following possibilities:

* Is the album present in `the MusicBrainz database`_?  You can search on their
  site to make sure it's cataloged there. If not, anyone can edit
  MusicBrainz---so consider adding the data yourself.

* Beets won't show you possibilities from MusicBrainz that have *fewer* tracks
  than the current album. In other words, if you have extra tracks that aren't
  included on the release, that candidate won't be displayed. (The tagger
  should, on the other hand, show you candidates that have *more* tracks than
  you do in the case that you're missing some of the album's songs. Beets will
  warn you when any candidate is a partial match.)

.. _the MusicBrainz database: http://musicbrainz.org/

If neither of these situations apply and you're still having trouble tagging
something, please `file a bug report`_.

.. _file a bug report: http://code.google.com/p/beets/issues/entry

I Hope That Makes Sense
-----------------------

I haven't made the process clear, please `drop me an email`_ and I'll try to
improve this guide.

.. _drop me an email: mailto:adrian@radbox.org
