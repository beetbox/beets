Lyrics Plugin
=============

The ``lyrics`` plugin fetches and stores song lyrics from databases on the Web.
Namely, the current version of the plugin uses `Lyric Wiki`_ and `Lyrics.com`_.

.. _Lyric Wiki: http://lyrics.wikia.com/
.. _Lyrics.com: http://www.lyrics.com/

Fetch Lyrics During Import
--------------------------

To automatically fetch lyrics for songs you import, just enable the plugin by
putting ``lyrics`` on your config file's ``plugins`` line (see
:doc:`/plugins/index`).  When importing new files, beets will now fetch lyrics
for files that don't already have them. The lyrics will be stored in the beets
database. If the ``import_write`` config option is on, then the lyrics will also
be written to the files' tags.

This behavior can be disabled with the ``autofetch`` config option (see below).

Fetching Lyrics Manually
------------------------

The ``lyrics`` command provided by this plugin fetches lyrics for items that
match a query (see :doc:`/reference/query`). For example, ``beet lyrics magnetic
fields absolutely cuckoo`` will get the lyrics for the appropriate Magnetic
Fields song, ``beet lyrics magnetic fields`` will get lyrics for all my tracks
by that band, and ``beet lyrics`` will get lyrics for my entire library. The
lyrics will be added to the beets database and, if ``import_write`` is on,
embedded into files' metadata.

The ``-p`` option to the ``lyrics`` command makes it print lyrics out to the
console so you can view the fetched (or previously-stored) lyrics.

Configuring
-----------

The plugin has one configuration option, ``autofetch``, which lets you disable
automatic lyrics fetching during import. To do so, add this to your
``~/.beetsconfig``::

    [lyrics]
    autofetch: no
