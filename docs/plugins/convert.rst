Convert Plugin
==============

The ``convert`` plugin lets you convert parts of your collection to a directory
of your choice. It converts all input formats supported by `FFmpeg`_ to MP3.
It will skip files that are already present in the target directory. Converted
files follow the same path formats as your library.

.. _FFmpeg: http://ffmpeg.org

Installation
------------

First, enable the ``convert`` plugin (see :doc:`/plugins/index`).

To transcode music, this plugin requires the ``ffmpeg`` command-line
tool. If its executable is in your path, it  will be found automatically
by the plugin. Otherwise, configure the plugin to locate the executable::

    convert:
        ffmpeg: /usr/bin/ffmpeg

Usage
-----

To convert a part of your collection, run ``beet convert QUERY``. This
will display all items matching ``QUERY`` and ask you for confirmation before
starting the conversion. The ``-a`` (or ``--album``) option causes the command
to match albums instead of tracks.

The ``-t`` (``--threads``) and ``-d`` (``--dest``) options allow you to specify
or overwrite the respective configuration options.

By default, the command places converted files into the destination directory
and leaves your library pristine. To instead back up your original files into
the destination directory and keep converted files in your library, use the
``-k`` (or ``--keep-new``) option.


Configuration
-------------

The plugin offers several configuration options, all of which live under the
``convert:`` section:

* ``dest`` sets the directory the files will be converted (or copied) to.
  A destination is required---you either have to provide it in the config file
  or on the command line using the ``-d`` flag.
* ``embed`` indicates whether or not to embed album art in converted items.
  Default: true.
* If you set ``max_bitrate``, all lossy files with a higher bitrate will be
  transcoded and those with a lower bitrate will simply be copied. Note that
  this does not guarantee that all converted files will have a lower
  bitrate---that depends on the encoder and its configuration.
* ``format`` specify which format preset you would like to use. Default: mp3.
* ``formats`` lets you specify additional formats to convert to. Presets for
  AAC, ALAC, FLAC, MP3, Opus, Vorbis and Windows Meda are provided, however
  support may vary depending on your ffmpeg library. Each format is defined as
  a command and a file extension.
* ``auto`` gives you the option to import transcoded versions of your files
  automatically during the ``import`` command. With this option enabled, the
  importer will transcode all non-MP3 files over the maximum bitrate before
  adding them to your library.
* ``quiet`` mode prevents the plugin from announcing every file it processes.
  Default: false.
* ``paths`` lets you specify the directory structure and naming scheme for the
  converted files. Use the same format as the top-level ``paths`` section (see
  :ref:`path-format-config`). By default, the plugin reuses your top-level
  path format settings.
* Finally, ``threads`` determines the number of threads to use for parallel
  encoding. By default, the plugin will detect the number of processors
  available and use them all.

Here's an example configuration::

    convert:
        embed: false
        format: aac
        max_bitrate: 200
        dest: /home/user/MusicForPhone
        threads: 4
        paths:
            default: $albumartist/$title

Here's how formats are configured::

    convert:
        format: mp3_high
        formats:
            mp3_high:
                command: ffmpeg -i $source -y -aq 4 $dest
                extension: mp3

The ``$source`` and ``$dest`` tokens are automatically replaced with the paths
to each file. Because ``$`` is used to delineate a field reference, you can
use ``$$`` to emit a dollars sign.

In this example ``-aq <num>`` is equivalent to the LAME option ``-V num``. If
you want to specify a bitrate, use ``-ab <bitrate>``. Refer to the `FFmpeg`_
documentation for more details.