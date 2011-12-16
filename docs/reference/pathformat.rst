Path Formats
============

The ``[paths]`` section of the config file (see :doc:`config`) lets
you specify the directory and file naming scheme for your music library.
Templates substitute symbols like ``$title`` (any field value prefixed by ``$``)
with the appropriate value from the track's metadata. Beets adds the filename
extension automatically.

For example, consider this path format string:
``$albumartist/$album/$track $title``

Here are some paths this format will generate:

* ``Yeah Yeah Yeahs/It's Blitz!/01 Zero.mp3``

* ``Spank Rock/YoYoYoYoYo/11 Competition.mp3``

* ``The Magnetic Fields/Realism/01 You Must Be Out of Your Mind.mp3``

Because ``$`` is used to delineate a field reference, you can use ``$$`` to emit
a dollars sign. As with `Python template strings`_, ``${title}`` is equivalent
to ``$title``; you can use this if you need to separate the field name from the
following text.

.. _Python template strings: http://docs.python.org/library/string.html#template-strings


A Note About Artists
--------------------

Note that in path formats, you almost certainly want to use ``$albumartist`` and
not ``$artist``. The latter refers to the "track artist" when it is present,
which means that albums that have tracks from different artists on them (like
`Stop Making Sense`_, for example) will be placed into different folders!
Continuing with the Stop Making Sense example, you'll end up with most of the
tracks in a "Talking Heads" directory and one in a "Tom Tom Club" directory. You
probably don't want that! So use ``$albumartist``.

.. _Stop Making Sense:
    http://musicbrainz.org/release/798dcaab-0f1a-4f02-a9cb-61d5b0ddfd36.html

As a convenience, however, beets allows ``$albumartist`` to fall back to the value for ``$artist`` and vice-versa if one tag is present but the other is not.


Functions
---------

Beets path formats also support *function calls*, which can be used to transform
text and perform logical manipulations. The syntax for function calls is like
this: ``%func{arg,arg}``. For example, the ``upper`` function makes its argument
upper-case, so ``%upper{beets rocks}`` will be replaced with ``BEETS ROCKS``.
You can, of course, nest function calls and place variable references in
function arguments, so ``%upper{$artist}`` becomes the upper-case version of the
track's artists.

These functions are built in to beets:

* ``%lower{text}``: Convert ``text`` to lowercase. 
* ``%upper{text}``: Convert ``text`` to UPPERCASE.
* ``%title{text}``: Convert ``text`` to Title Case.
* ``%left{text,n}``: Return the first ``n`` characters of ``text``.
* ``%right{text,n}``: Return the last ``n`` characters of  ``text``.
* ``%if{condition,text}`` or ``%if{condition,truetext,falsetext}``: If
  ``condition`` is nonempty (or nonzero, if it's a number), then returns
  the second argument. Otherwise, returns the third argument if specified (or
  nothing if ``falsetext`` is left off).

Available Values
----------------

Here's a (comprehensive?) list of the different values available to path
formats. (I will try to keep it up to date, but I might forget. The current list
can be found definitively `in the source`_.)

.. _in the source: 
    http://code.google.com/p/beets/source/browse/beets/library.py#36 

Ordinary metadata:

* title
* artist
* album
* genre
* composer
* grouping
* year
* month
* day
* track
* tracktotal
* disc
* disctotal
* lyrics
* comments
* bpm
* comp

Audio information:

* length
* bitrate
* format

MusicBrainz IDs:

* mb_trackid
* mb_albumid
* mb_artistid
