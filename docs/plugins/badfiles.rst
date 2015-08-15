Bad Files Plugin
================

Adds a `beet bad` command to check for missing, and optionally corrupt files.

Configuration
-------------

Here is a very basic configuration that uses the default commands for MP3 and
FLAC files, requiring the `mp3val`_ and
packages to be installed::

    badfiles:
      commands: {}
    plugins: ... badfiles

Note that the *mp3val* checker is a bit verbose and can output a lot of "stream
error" messages, even for files that play perfectly well. Generally if more
than one stream error happens, or if a stream error happens in the middle of a
file, this is a bad sign.

.. _mp3val: http://mp3val.sourceforge.net/
.. _flac: https://xiph.org/flac/

You can also add custom commands for a specific extension, e.g.::

    badfiles:
      commands:
        ogg: myoggchecker --opt1 --opt2
        flac: flac --test --warnings-as-errors --silent
    plugins: ... badfiles

Running
-------

To run Badfiles, just use the ``beet bad`` command with Beets' usual query syntax.

For instance, this will run a check on all songs containing the word "wolf"::

    beet bad wolf

This one will run checks on a specific album::

    beet bad album_id:1234

Here is an example from my library where the FLAC decoder was signaling a
corrupt file::

    beet bad title::^$
    /tank/Music/__/00.flac: command exited with status 1
      00.flac: *** Got error code 2:FLAC__STREAM_DECODER_ERROR_STATUS_FRAME_CRC_MISMATCH
      00.flac: ERROR while decoding data
                 state = FLAC__STREAM_DECODER_READ_FRAME
