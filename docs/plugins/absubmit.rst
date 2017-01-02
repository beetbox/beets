AcousticBrainz Submit Plugin
============================

The `absubmit` plugin uses the `streaming_extractor_music`_ program to analyze an audio file and calculate different acoustic properties of the audio. The plugin then uploads this metadata to the AcousticBrainz server. The plugin does this when calling the ``beet absumbit [QUERY]`` command or on importing if the `auto` configuration option is set to ``yes``.

Installation
------------

The `absubmit` plugin requires the `streaming_extractor_music`_ program to run. Its source can be found on `GitHub`_, and while it is possible to compile the extractor from source, AcousticBrainz would prefer if you used their binary (see the AcousticBrainz `FAQ`_).

The `absubmit` also plugin requires `requests`_, which you can install using `pip_` by typing:

    pip install requests

After installing both the extractor binary and requests you can enable the plugin ``absubmit`` in your configuration (see :ref:`using-plugins`).

Configuration
-------------

To configure the plugin, make a ``absubmit:`` section in your configuration file. The available options are:

- **auto**: Analyze every file on import. Otherwise, you need to use the ``beet absubmit`` command explicitly.
  Default: ``no``
- **extractor**: The absolute path to the `streaming_extractor_music`_ binary.
  Default: search for the program in your ``$PATH``

Notes
-----
MusicBrainz track id is needed to use AcousticBrainz. Check the `streaming_extractor_music`_ download page for more information.

.. _streaming_extractor_music: http://acousticbrainz.org/download
.. _FAQ: http://acousticbrainz.org/faq
.. _pip: http://www.pip-installer.org/
.. _requests: http://docs.python-requests.org/en/master/
.. _github: https://github.com/MTG/essentia
