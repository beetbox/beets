MusicBrainz Submit Plugin
=========================

The ``mbsubmit`` plugin provides an extra prompt choice during an import
session that prints the tracks of the current album in a format that is
parseable by MusicBrainz's `track parser`_.

.. _track parser: http://wiki.musicbrainz.org/History:How_To_Parse_Track_Listings

Usage
-----

Enable the ``mbsubmit`` plugin in your configuration (see :ref:`using-plugins`)
and select the ``Print tracks`` choice which is by default displayed when no
strong recommendations are found for the album::

    No matching release found for 3 tracks.
    For help, see: http://beets.readthedocs.org/en/latest/faq.html#nomatch
    [U]se as-is, as Tracks, Group albums, Skip, Enter search, enter Id, aBort,
    Print tracks? p
    01. An Obscure Track - An Obscure Artist (3:37)
    02. Another Obscure Track - An Obscure Artist (2:05)
    03. The Third Track - Another Obscure Artist (3:02)

    No matching release found for 3 tracks.
    For help, see: http://beets.readthedocs.org/en/latest/faq.html#nomatch
    [U]se as-is, as Tracks, Group albums, Skip, Enter search, enter Id, aBort,
    Print tracks?

As MusicBrainz currently does not support submitting albums programmatically,
the recommended workflow is to copy the output of the ``Print tracks`` choice
and paste it into the parser that can be found by clicking on the
"Track Parser" button on MusicBrainz "Tracklist" tab.

Configuration
-------------

To configure the plugin, make a ``mbsubmit:`` section in your configuration
file. The following options are available:

- **format**: The format used for printing the tracks, defined using the
  same template syntax as beets’ :doc:`path formats </reference/pathformat>`.
  Default: ``$track. $title - $artist ($length)``.
- **threshold**: The minimum strength of the autotagger recommendation that
  will cause the ``Print tracks`` choice to be displayed on the prompt.
  Default: ``medium`` (causing the choice to be displayed for all albums that
  have a recommendation of medium strength or lower). Valid values: ``none``,
  ``low``, ``medium``, ``strong``.

Please note that some values of the ``threshold`` configuration option might
require other ``beets`` command line switches to be enabled in order to work as
intended. In particular, setting a threshold of ``strong`` will only display
the prompt if ``timid`` mode is enabled. You can find more information about
how the recommendation system works at :ref:`match-config`.
