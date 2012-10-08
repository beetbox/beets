Convert Plugin
==============

The ``convert`` plugin lets you convert parts of your collection to a directory
of your choice. Currently only converting from MP3 or FLAC to MP3 is supported.
It will skip files that are already present in the target directory. It uses
the same directory structure as your library.

Installation
------------

This plugin requires ``flac`` and ``lame``. If thoses executables are in your
path, they will be found automatically by the plugin, otherwise you have to set
their respective config options. Of course you will have to enable the plugin
as well (see :doc:`/plugins/index`)::

    [convert]
    flac:/usr/bin/flac
    lame:/usr/bin/lame

Usage
-----

To convert a part of your collection simply run ``beet convert QUERY``. This
will display all items matching ``QUERY`` and ask you for confirmation before
starting the conversion. The ``-a`` (or ``--album``) option causes the command
to match albums instead of tracks.

The ``-t`` (``--threads``) and ``-d`` (``--dest``) options allow you to specify
or overwrite the respective configuration options.

Configuration
-------------

This plugin offers a couple of configuration options: If you want to disable
that album art is embedded in your converted items (enabled by default), you
will have to set the ``embed`` option to false. If you set ``max_bitrate``, all
MP3 files with a higher bitrate will be converted and thoses with a lower
bitrate will simply be copied. Be aware that this doesn't mean that your
converted files will have a lower bitrate since that depends on the specified
encoding options. By default only FLAC files will be converted (and all MP3s
will be copied). ``opts`` are the encoding options that are passed to ``lame``
(defaults to "-V2"). Please refer to the ``lame`` docs for possible options.

The ``dest`` sets the directory the files will be converted (or copied) to.
Finally ``threads`` lets you determine the number of threads to use for
encoding (default: 2). An example configuration::

    [convert]
    embed:false
    max_bitrate:200
    opts:-V4
    dest:/home/user/MusicForPhone
    threads:4
