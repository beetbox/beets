Scrub Plugin
============

The ``scrub`` plugin lets you remove extraneous metadata from files' tags. If
you'd prefer never to see crufty tags that come from other tools, the plugin can
automatically remove all non-beets-tracked tags whenever a file's metadata is
written to disk by removing the tag entirely before writing new data. The plugin
also provides a command that lets you manually remove files' tags.

Automatic Scrubbing
-------------------

To automatically remove files' tags before writing new ones, enable ``scrub``
plugin in your configuration (see :ref:`using-plugins`) and install ``beets``
with ``scrub`` extra

.. code-block:: bash

    pip install "beets[scrub]"

When importing new files (with ``import.write`` turned on) or modifying files'
tags with the ``beet modify`` command, beets will first strip all types of tags
entirely and then write the database-tracked metadata to the file.

This behavior can be disabled with the ``auto`` config option (see below).

Manual Scrubbing
----------------

The ``scrub`` command provided by this plugin removes tags from files and then
rewrites their database-tracked metadata. To run it, just type ``beet scrub
QUERY`` where ``QUERY`` matches the tracks to be scrubbed. Use this command with
caution, however, because any information in the tags that is out of sync with
the database will be lost.

The ``-W`` (or ``--nowrite``) option causes the command to just remove tags but
not restore any information. This will leave the files with no metadata other
than the tags listed in ``keep_tags``.

Configuration
-------------

To configure the plugin, make a ``scrub:`` section in your configuration file.
The available options are:

- **auto**: Enable metadata stripping during import. Default: ``yes``.
- **keep_tags**: A list of tags to leave in place when scrubbing, such as custom
  tags written by other tools. Default: ``[]``.

Tags are named as they are stored in the file, not by beets field names, and are
matched case-insensitively. A name such as ``SUBBOX_ID`` matches the tag with
that name in Vorbis comments (FLAC, Ogg, Opus), APEv2 (Monkey's Audio, WavPack,
Musepack) and ASF (WMA) files, the ``TXXX:SUBBOX_ID`` frame in ID3 (MP3) files
and the ``----:com.apple.iTunes:SUBBOX_ID`` atom in MP4 files. For ID3 frames
and MP4 atoms, you can also give the full key or the part of it before a ``:``,
such as ``COMM`` to keep all comment frames. For example:

.. code-block:: yaml

    scrub:
        keep_tags:
            - SUBBOX_ID
            - SERATO_PLAYCOUNT

A kept tag that beets also writes still gets its value from the database.
