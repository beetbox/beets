AutoBPM Plugin
==============

The ``autobpm`` plugin uses the Librosa_ library to calculate the BPM of a track
from its audio data and store it in the ``bpm`` field of your database. It does
so automatically when importing music or through the ``beet autobpm [QUERY]``
command.

Install
-------

To use the ``autobpm`` plugin, first enable it in your configuration (see
:ref:`using-plugins`). Then, install ``beets`` with ``autobpm`` extra

.. code-block:: bash

    pip install "beets[autobpm]"

Configuration
-------------

To configure the plugin, make a ``autobpm:`` section in your configuration file.

Default
~~~~~~~

.. code-block:: yaml

    autobpm:
        auto: yes
        force: no
        beat_track_kwargs: {}
        quiet: no

.. conf:: auto
    :default: yes

    Analyze every file on import. Otherwise, you need to use the ``beet
    autobpm`` command explicitly.

.. conf:: force
    :default: no

    Calculate a BPM even for files that already have a ``bpm`` value. Can also be set
    using the ``-f`` or ``--force`` flag.

.. conf:: overwrite
    :default: no

    .. deprecated:: 2.9 Use ``force`` instead.

.. conf:: beat_track_kwargs
    :default: {}

    Any extra keyword arguments that you would like to provide to librosa's
    beat_track_ function call, for example:

    .. code-block:: yaml

        autobpm:
          beat_track_kwargs:
            start_bpm: 160

.. conf:: quiet
    :default: no

    Suppress the message indicating that a file already has a ``bpm`` value. Can also be
    set using the ``-q`` or ``--quiet`` flag.

.. _beat_track: https://librosa.org/doc/latest/generated/librosa.beat.beat_track.html

.. _librosa: https://github.com/librosa/librosa/
