AutoBPM Plugin
==============

The `autobpm` plugin uses the `Librosa`_ library to calculate the BPM
of a track from its audio data and store it in the `bpm` field of your
database. It does so automatically when importing music or through
the ``beet autobpm [QUERY]`` command.

To use the ``autobpm`` plugin, enable it in your configuration (see
:ref:`using-plugins`).

Configuration
-------------

To configure the plugin, make a ``autobpm:`` section in your
configuration file. The available options are:

- **auto**: Analyze every file on import.
  Otherwise, you need to use the ``beet autobpm`` command explicitly.
  Default: ``yes``
- **overwrite**: Calculate a BPM even for files that already have a
  `bpm` value.
  Default: ``no``.

.. _Librosa: https://github.com/librosa/librosa/
