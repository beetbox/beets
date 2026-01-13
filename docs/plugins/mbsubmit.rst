MusicBrainz Submit Plugin
=========================

The ``mbsubmit`` plugin provides extra prompt choices when an import session
fails to find a good enough match for a release. Additionally, it provides an
``mbsubmit`` command that prints the tracks of the current album in a format
that is parseable by MusicBrainz's `track parser`_. The prompt choices are:

- Print the tracks to stdout in a format suitable for MusicBrainz's `track
  parser`_.
- Open the program Picard_ with the unmatched folder as an input, allowing you
  to start submitting the unmatched release to MusicBrainz with many input
  fields already filled in, thanks to Picard reading the preexisting tags of the
  files.

For the last option, Picard_ is assumed to be installed and available on the
machine including a ``picard`` executable. Picard developers list `download
options`_. `other GNU/Linux distributions`_ may distribute Picard via their
package manager as well.

.. _download options: https://picard.musicbrainz.org/downloads/

.. _other gnu/linux distributions: https://repology.org/project/picard-tagger/versions

.. _picard: https://picard.musicbrainz.org/

.. _track parser: https://wiki.musicbrainz.org/History:How_To_Parse_Track_Listings

Usage
-----

Enable the ``mbsubmit`` plugin in your configuration (see :ref:`using-plugins`)
and select one of the options mentioned above. Here the option ``Print tracks``
choice is demonstrated:

::

    No matching release found for 3 tracks.
    For help, see: https://beets.readthedocs.org/en/latest/faq.html#nomatch
    [U]se as-is, as Tracks, Group albums, Skip, Enter search, enter Id, aBort,
    Print tracks, Open files with Picard? p
    01. An Obscure Track - An Obscure Artist (3:37)
    02. Another Obscure Track - An Obscure Artist (2:05)
    03. The Third Track - Another Obscure Artist (3:02)

    No matching release found for 3 tracks.
    For help, see: https://beets.readthedocs.org/en/latest/faq.html#nomatch
    [U]se as-is, as Tracks, Group albums, Skip, Enter search, enter Id, aBort,
    Print tracks?

You can also run ``beet mbsubmit QUERY`` to print the track information for any
album:

::

    $ beet mbsubmit album:"An Obscure Album"
    01. An Obscure Track - An Obscure Artist (3:37)
    02. Another Obscure Track - An Obscure Artist (2:05)
    03. The Third Track - Another Obscure Artist (3:02)

As MusicBrainz currently does not support submitting albums programmatically,
the recommended workflow is to copy the output of the ``Print tracks`` choice
and paste it into the parser that can be found by clicking on the "Track Parser"
button on MusicBrainz "Tracklist" tab.

Configuration
-------------

To configure the plugin, make a ``mbsubmit:`` section in your configuration
file. The following options are available:

- **format**: The format used for printing the tracks, defined using the same
  template syntax as beets’ :doc:`path formats </reference/pathformat>`.
  Default: ``$track. $title - $artist ($length)``.
- **threshold**: The minimum strength of the autotagger recommendation that will
  cause the ``Print tracks`` choice to be displayed on the prompt. Default:
  ``medium`` (causing the choice to be displayed for all albums that have a
  recommendation of medium strength or lower). Valid values: ``none``, ``low``,
  ``medium``, ``strong``.
- **picard_path**: The path to the ``picard`` executable. Could be an absolute
  path, and if not, ``$PATH`` is consulted. The default value is simply
  ``picard``. Windows users will have to find and specify the absolute path to
  their ``picard.exe``. That would probably be: ``C:\Program Files\MusicBrainz
  Picard\picard.exe``.

Please note that some values of the ``threshold`` configuration option might
require other ``beets`` command line switches to be enabled in order to work as
intended. In particular, setting a threshold of ``strong`` will only display the
prompt if ``timid`` mode is enabled. You can find more information about how the
recommendation system works at :ref:`match-config`.
