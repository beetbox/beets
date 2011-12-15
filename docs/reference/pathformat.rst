Path Formats
============

The ``[paths]`` section of the config file (see :doc:`config`) lets
you specify the directory and file naming scheme for your music library. You
specify templates using Python template string notation---that is, prefixing
names with ``$`` characters---and beets fills in the appropriate values.

For example, consider this path format string: ``$albumartist/$album/$track
$title``

Here are some paths this format will generate:

* ``Yeah Yeah Yeahs/It's Blitz!/01 Zero.mp3``

* ``Spank Rock/YoYoYoYoYo/11 Competition.mp3``

* ``The Magnetic Fields/Realism/01 You Must Be Out of Your Mind.mp3``

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

Upgrading from 1.0b6
--------------------

Versions of beets prior to 1.0b7 didn't use a ``[paths]`` section. Instead, they
used a single ``path_format`` setting for all music. To support old
configuration files, this setting is still respected and overrides the default
path formats. However, the setting is deprecated and, if you want to use
flexible path formats, you need to remove the ``path_format`` setting and use a
``[paths]`` section instead.

Possible Values
---------------

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
