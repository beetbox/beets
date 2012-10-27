Convert Plugin
==============

The ``convert`` plugin lets you convert parts of your collection to a directory
of your choice. Currently only converting from MP3 or FLAC to MP3 is supported.
It will skip files that are already present in the target directory. Converted
files follow the same path formats as your library.

Installation
------------

First, enable the ``convert`` plugin (see :doc:`/plugins/index`).

To transcode music, this plugin requires the ``flac`` and ``lame`` command-line
tools. If those executables are in your path, they will be found automatically
by the plugin. Otherwise, configure the plugin to locate the executables::

    [convert]
    flac: /usr/bin/flac
    lame: /usr/bin/lame

Usage
-----

To convert a part of your collection, run ``beet convert QUERY``. This
will display all items matching ``QUERY`` and ask you for confirmation before
starting the conversion. The ``-a`` (or ``--album``) option causes the command
to match albums instead of tracks.

The ``-t`` (``--threads``) and ``-d`` (``--dest``) options allow you to specify
or overwrite the respective configuration options.

Configuration
-------------

The plugin offers several configuration options, all of which live under the
``[convert]`` section:

* ``dest`` sets the directory the files will be converted (or copied) to.
  A destination is required---you either have to provide it in the config file
  or on the command line using the ``-d`` flag.
* ``embed`` indicates whether or not to embed album art in converted items.
  Default: true.
* If you set ``max_bitrate``, all MP3 files with a higher bitrate will be
  transcoded and those with a lower bitrate will simply be copied. Note that
  this does not guarantee that all converted files will have a lower
  bitrate---that depends on the encoder and its configuration. By default, FLAC
  files will be converted and all MP3s will be copied without transcoding.
* ``opts`` are the encoding options that are passed to ``lame``. Default: 
  "-V2". Please refer to the LAME documentation for possible options.
* Finally, ``threads`` determines the number of threads to use for parallel
  encoding. By default, the plugin will detect the number of processors
  available and use them all.

Here's an example configuration::

    [convert]
    embed: false
    max_bitrate: 200
    opts: -V4
    dest: /home/user/MusicForPhone
    threads: 4
