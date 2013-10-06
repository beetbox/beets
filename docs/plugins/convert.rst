Convert Plugin
==============

The ``convert`` plugin lets you convert parts of your collection to a
directory of your choice, transcoding audio and embedding album art along the
way. It can transcode to and from any format using a configurable command
line. It will skip files that are already present in the target directory.
Converted files follow the same path formats as your library.

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

These config options control the transcoding process:

* ``format`` is the name of the audio file format to transcode to. Files that
  are already in the format (and are below the maximum bitrate) will not be
  transcoded. The plugin includes default commands for the formats MP3, AAC,
  ALAC, FLAC, Opus, Vorbis, and Windows Media; the default is MP3. If you want
  to use a different format (or customize the transcoding options), use the
  options below.
* ``extension`` is the filename extension to be used for newly transcoded
  files. This is implied by the ``format`` option, but you can set it yourself
  if you're using a different format.
* ``command`` is the command line to use to transcode audio. A default
  command, usually using an FFmpeg invocation, is implied by the ``format``
  option. The tokens ``$source`` and ``$dest`` in the command are replaced
  with the paths to the existing and new file. For example, the command
  ``ffmpeg -i $source -y -aq 4 $dest`` transcodes to MP3 using FFmpeg at the
  V4 quality level.

Here's an example configuration::

    convert:
        embed: false
        format: aac
        max_bitrate: 200
        dest: /home/user/MusicForPhone
        threads: 4
        paths:
            default: $albumartist/$title

If you have several formats you want to switch between, you can list them
under the ``formats`` key and refer to them using the ``format`` option. Each
key under ``formats`` should contain values for ``command`` and ``extension``
as described above::

    convert:
        format: speex
        formats:
            speex:
                command: ffmpeg -i $source -y -acodec speex $dest
                extension: spx
            wav:
                command: ffmpeg -i $source -y -acodec pcm_s16le $dest
                extension: wav
