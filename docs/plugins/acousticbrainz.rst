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

These three fields are all numbers between 0.0 and 1.0.
