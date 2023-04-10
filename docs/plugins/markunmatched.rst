MarkUnmatched Plugin
==================

The ``markunmatched`` plugin is a simple plugin that adds a prompt choice when
beets fails to find accurate enough matches when importing a directory (see
:doc:`usage`). It also includes an option to notify you via a custom command
when an import has encountered a too weak recommendation.

To use the ``markunmatched`` plugin, enable it in your configuration (see
:ref:`using-plugins`).

Usage
-----

When importing many directories in a bulk, you may want to skip a directory but
mark yourself to take care of it later - for example add that album to
musicbrainz later, and not now during the bulk import.

The prompt looks like this::

    Apply, More candidates, Skip, Use as-is, as Tracks, Group albums,
    Enter search, enter Id, aBort, create a 'beets-unmatched' File and skip,
    Print tracks, eDit, edit Candidates?

The `beets-unmatched` file can be used to later to reiterate the unmatched
albums.

Configuration:
--------------

By default, no notification is made when a match is not found in an import
procedure. To configure such notification, use (e.g)::

    markunmatched:
        notify-command: "gotify push --title 'Beets Music importer' --priority 4"

Beets pipes to stdin of the above command the message mentioning the unmatched
paths.
