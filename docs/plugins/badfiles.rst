Bad Files Plugin
================

The ``badfiles`` plugin adds a ``beet bad`` command to check for missing and
corrupt files.

Configuring
-----------

First, enable the ``badfiles`` plugin (see :ref:`using-plugins`). Then, add a
``badfiles:`` section to your configuration file, like so::

    badfiles:
        commands: {}

This uses two default checkers: `mp3val`_ for MP3s and the ordinary `FLAC`_
command-line tools for those files. (You will need to install these yourself.)
You can also add custom commands for a specific extension, like this::

    badfiles:
        commands:
            ogg: myoggchecker --opt1 --opt2
            flac: flac --test --warnings-as-errors --silent

.. _mp3val: http://mp3val.sourceforge.net/
.. _flac: https://xiph.org/flac/

Using
-----

Type ``beet bad`` with a query according to beets' usual query syntax. For
instance, this will run a check on all songs containing the word "wolf"::

    beet bad wolf

This one will run checks on a specific album::

    beet bad album_id:1234

Here is an example where the FLAC decoder was signals a corrupt file::

    beet bad title::^$
    /tank/Music/__/00.flac: command exited with status 1
      00.flac: *** Got error code 2:FLAC__STREAM_DECODER_ERROR_STATUS_FRAME_CRC_MISMATCH
      00.flac: ERROR while decoding data
                 state = FLAC__STREAM_DECODER_READ_FRAME

Note that the default `mp3val` checker is a bit verbose and can output a lot
of "stream error" messages, even for files that play perfectly well.
Generally, if more than one stream error happens, or if a stream error happens
in the middle of a file, this is a bad sign.
