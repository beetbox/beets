Acousticbrainz Plugin
=====================

The ``acoustricbrainz`` plugin provides a command that traverses through a library and tags tracks with valid MusicBrainz IDs with additional metadata such as

* ``danceable``
    + Predicts how easy the track is danceable to
* ``mood_happy``
    + Predicts the probability this track is played to invoke happiness
* ``mood_party``
    + Predicts the probability this track is played in a party environment

Enable the ``acousticbrainz`` plugin in your configuration (see :ref:`using-plugins`) and run with:

    $ beet acousticbrainz

Additional command-line options coming soon.
