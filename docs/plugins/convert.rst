Convert Plugin
==============

The ``convert`` plugin lets you convert parts of your collection to a
directory of your choice, transcoding audio and embedding album art along the
way. It can transcode to and from any format using a configurable command
line.


Installation
------------

Enable the ``convert`` plugin in your configuration (see
:doc:`/plugins/index`).  By default, the plugin depends on `FFmpeg`_ to
transcode the audio, so you might want to install it.

.. _FFmpeg: http://ffmpeg.org


Usage
-----

To convert a part of your collection, run ``beet convert QUERY``. The
command will transcode all the files matching the query to the
destination directory given by the ``-d`` (``--dest``) option or the
``dest`` configuration. The path layout mirrors that of your library,
but it may be customized through the ``paths`` configuration.

The plugin uses a command-line program to transcode the audio. With the
``-f`` (``--format``) option you can choose the transcoding command
and customize the available commands
:ref:`through the configuration <convert-format-config>`.

Unless the ``-y`` (``--yes``) flag is set, the command will list all
the items to be converted and ask for your confirmation.

The ``-a`` (or ``--album``) option causes the command
to match albums instead of tracks.

By default, the command places converted files into the destination directory
and leaves your library pristine. To instead back up your original files into
the destination directory and keep converted files in your library, use the
``-k`` (or ``--keep-new``) option.

To test your configuration without taking any actions, use the ``--pretend``
flag. The plugin will print out the commands it will run instead of executing
them.


Configuration
-------------

The plugin offers several configuration options, all of which live under the
``convert:`` section:

* ``dest`` sets the directory the files will be converted (or copied) to.
  A destination is required---you either have to provide it in the config file
  or on the command-line using the ``-d`` flag.
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
* ``never_convert_lossy_files`` means that lossy codecs, such as mp3, ogg vorbis,
  etc, are never converted, as converting lossy files to other lossy codecs will
  decrease quality further. If set to true, lossy files are always copied.
  Default: false
* ``paths`` lets you specify the directory structure and naming scheme for the
  converted files. Use the same format as the top-level ``paths`` section (see
  :ref:`path-format-config`). By default, the plugin reuses your top-level
  path format settings.
* Finally, ``threads`` determines the number of threads to use for parallel
  encoding. By default, the plugin will detect the number of processors
  available and use them all.

.. _convert-format-config:

Configuring the transcoding command
```````````````````````````````````

You can customize the transcoding command through the ``formats`` map
and select a command with the ``--format`` command-line option or the
``format`` configuration.::

    convert:
        format: speex
        formats:
            speex:
                command: ffmpeg -i $source -y -acodec speex $dest
                extension: spx
            wav: ffmpeg -i $source -y -acodec pcm_s16le $dest

In this example ``beet convert`` will use the *speex* command by
default. To convert the audio to `wav`, run ``beet convert -f wav``.
This will also use the format key (`wav`) as the file extension.

Each entry in the ``formats`` map consists of a key (the name of the
format) as well as the command and the possibly the file extension.
``extension`` is the filename extension to be used for newly transcoded
files.  If only the command is given as a string, the file extension
defaults to the format’s name. ``command`` is the command-line to use
to transcode audio. The tokens ``$source`` and ``$dest`` in the command
are replaced with the paths to the existing and new file.

The plugin in comes with default commands for the most common audio
formats: `mp3`, `alac`, `flac`, `aac`, `opus`, `ogg`, `wmv`. For
details have a look at the output of ``beet config -d``.

For a one-command-fits-all solution use the ``convert.command`` and
``convert.extension`` options. If these are set the formats are ignored
and the given command is used for all conversions.::

    convert:
        command: ffmpeg -i $source -y -vn -aq 2 $dest
        extension: mp3
