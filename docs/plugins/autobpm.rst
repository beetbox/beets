AutoBPM Plugin
==============

The ``autobpm`` plugin uses the Librosa_ library to calculate the BPM of a track
from its audio data and store it in the ``bpm`` field of your database. It does
so automatically when importing music or through the ``beet autobpm [-l LIMIT]
[-b START_BPM] [-m MIN_BPM] [-M MAX_BPM] [QUERY]`` command.

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
        min_bpm: null
        max_bpm: null
        beat_track_kwargs: {}
        quiet: no

.. conf:: auto
    :default: yes

    Analyze every file on import. Otherwise, you need to use the ``beet
    autobpm`` command explicitly.

.. conf:: force
    :default: no

    Calculate a BPM even for files that already have a ``bpm`` value. Can also
    be set using the ``-f`` or ``--force`` flag. Use ``-l``/``--limit`` to cap
    the matched tracks before calculating BPM.

.. conf:: overwrite
    :default: no

    .. deprecated:: 2.9 Use ``force`` instead.

.. conf:: min_bpm
    :default: none

    Lowest BPM that may be detected. If unset while ``max_bpm`` is set, it
    defaults to 30. Can also be set using the ``-m`` or ``--min-bpm`` flag. See
    :ref:`autobpm-range`.

.. conf:: max_bpm
    :default: none

    Highest BPM that may be detected. If unset while ``min_bpm`` is set, it
    defaults to 320. Can also be set using the ``-M`` or ``--max-bpm`` flag.
    See :ref:`autobpm-range`.

.. conf:: beat_track_kwargs
    :default: {}

    Any extra keyword arguments that you would like to provide to librosa's
    beat_track_ function call, for example:

    .. code-block:: yaml

        autobpm:
          beat_track_kwargs:
            start_bpm: 160

    The ``start_bpm`` value can also be set for a single run using the ``-b``
    or ``--start-bpm`` flag, which takes precedence over the configuration.

    ``start_bpm`` only centers a soft preference around a tempo, so it often
    does not stop wrong results. Of the other keyword arguments, ``tightness``,
    ``trim`` and ``bpm`` do not help either, since they do not influence
    the detected tempo. Use ``min_bpm`` and ``max_bpm`` to restrict the result.

.. conf:: quiet
    :default: no

    Suppress the message indicating that a file already has a ``bpm`` value. Can also be
    set using the ``-q`` or ``--quiet`` flag.

.. _autobpm-range:

Restricting the BPM range
~~~~~~~~~~~~~~~~~~~~~~~~~

Beat detection can lock onto a related but wrong periodicity, for example
reporting about 108 BPM for a 160 BPM breakbeat because of its syncopated drum
pattern. If you know which tempos to expect, set ``min_bpm`` and ``max_bpm`` to
make the detection consider only that range:

.. code-block:: yaml

    autobpm:
        min_bpm: 140
        max_bpm: 190

or for a single run:

.. code-block:: bash

    beet autobpm -f -m 140 -M 190 genre:breakbeat

You can set just one bound. A missing ``min_bpm`` then means 30 and a missing
``max_bpm`` means 320, so ``-m 140`` alone allows 140 to 320 BPM. If neither is
set, no range is applied. Both bounds must satisfy ``min_bpm < max_bpm``. The
range is passed to librosa as a uniform ``prior``, so ``start_bpm`` has no
effect when a range is set. Use ``--force`` to recalculate tracks that already
have a ``bpm`` value.

.. _beat_track: https://librosa.org/doc/latest/api/generated/librosa.beat.beat_track.html

.. _librosa: https://github.com/librosa/librosa/
