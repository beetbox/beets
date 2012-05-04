Queries
=======

Many of beets' :doc:`commands <cli>` are built around **query strings:**
searches that select tracks and albums from your library. This page explains the
query string syntax, which is meant to vaguely resemble the syntax used by Web
search engines.

Keyword
-------

This command::

    $ beet list love

will show all tracks matching the query string ``love``. Any unadorned word like this matches *anywhere* in a track's metadata, so you'll see all the tracks with "love" in their title, in their album name, in the artist, and so on.

For example, this is what I might see when I run the command above::

    Against Me! - Reinventing Axl Rose - I Still Love You Julie
    Air - Love 2 - Do the Joy
    Bag Raiders - Turbo Love - Shooting Stars
    Bat for Lashes - Two Suns - Good Love
    ...

Combining Keywords
------------------

Multiple keywords are implicitly joined with a Boolean "and." That is, if a
query has two keywords, it only matches tracks that contain *both* keywords. For
example, this command::

    $ beet ls magnetic tomorrow

matches songs from the album "The House of Tomorrow" by The Magnetic Fields in
my library. It *doesn't* match other songs by the Magnetic Fields, nor does it
match "Tomorrowland" by Walter Meego---those songs only have *one* of the two
keywords I specified.

Specific Fields
---------------

Sometimes, a broad keyword match isn't enough. Beets supports a syntax that lets
you query a specific field---only the artist, only the track title, and so on.
Just say ``field:value``, where ``field`` is the name of the thing you're trying
to match (such as ``artist``, ``album``, or ``title``) and ``value`` is the
keyword you're searching for.

For example, while this query::

    $ beet list dream

matches a lot of songs in my library, this more-specific query::

    $ beet list artist:dream

only matches songs by the artist The-Dream. One query I especially appreciate is
one that matches albums by year::

    $ beet list -a year:2012

Recall that ``-a`` makes the ``list`` command show albums instead of individual
tracks, so this command shows me all the releases I have from this year.

Phrases
-------

You can query for strings with spaces in them by quoting or escaping them using
your shell's argument syntax. For example, this command::

    $ beet list the rebel

shows several tracks in my library, but these (equivalent) commands::

    $ beet list "the rebel"
    $ beet list the\ rebel

only match the track "The Rebel" by Buck 65. Note that the quotes and
backslashes are not part of beets' syntax; I'm just using the escaping
functionality of my shell (bash or zsh, for instance) to pass ``the rebel`` as a
single argument instead of two.

.. _regex:

Regular Expressions
-------------------

While ordinary keywords perform simple substring matches, beets also supports
regular expression matching for more advanced queries. To run a regex query, use
an additional ``:`` between the field name and the expression::

    $ beet list 'artist::Ann(a|ie)'

That query finds songs by Anna Calvi and Annie but not Annuals. Similarly, this
query prints the path to any file in my library that's missing a track title::

    $ beet list -p title::^$

To search *all* fields using a regular expression, just prefix the expression
with a single ``:``, like so::

    $ beet list :Ho[pm]eless

Regular expressions are case-sensitive and build on `Python's built-in
implementation`_. See Python's documentation for specifics on regex syntax.

.. _Python's built-in implementation: http://docs.python.org/library/re.html


Path Queries
------------

Sometimes it's useful to find all the items in your library that are
(recursively) inside a certain directory. Use the ``path:`` field to do this::

    $ beet list path:/my/music/directory

In fact, beets automatically recognizes any query term containing a path
separator (``/`` on POSIX systems) as a path query, so this command is
equivalent::

    $ beet list /my/music/directory

Note that this only matches items that are *already in your library*, so a path
query won't necessarily find *all* the audio files in a directory---just the
ones you've already added to your beets library.
