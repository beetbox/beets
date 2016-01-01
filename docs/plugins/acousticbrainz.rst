AcousticBrainz Plugin
=====================

The ``acoustricbrainz`` plugin gets acoustic-analysis information from the
`AcousticBrainz`_ project. The spirit is similar to the
:doc:`/plugins/echonest`.

.. _AcousticBrainz: http://acousticbrainz.org/

Enable the ``acousticbrainz`` plugin in your configuration (see :ref:`using-plugins`) and run it by typing::

    $ beet acousticbrainz [QUERY]

For all tracks with a MusicBrainz recording ID, the plugin currently sets
these fields:

* ``danceable``: Predicts how easy the track is to dance to.
* ``mood_happy``: Predicts the probability this track will evoke happiness.
* ``mood_party``: Predicts the probability this track should be played at a
  party.

Automatic Tagging
-----------------

To automatically tag files using AcousticBrainz data during import, just
enable the ``acousticbrainz`` plugin (see :ref:`using-plugins`). When importing 
new files (with ``import.write`` turned on) or modifying files' tags with the 
``beet modify`` command, beets will query the AcousticBrainz API using MBID and
set the appropriate metadata.

Configuration
-------------

To configure the plugin, make a ``acousticbrainz:`` section in your
configuration file. There is one option:

- **auto**: Enable AcousticBrainz import during import.
  Default: ``yes``.
