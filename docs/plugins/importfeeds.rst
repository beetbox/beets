ImportFeeds Plugin
==================

The ``importfeeds`` plugin helps you keep track of newly imported music in your library.

To use the plugin, enable it in your configuration (see :ref:`using-plugins`).

Configuration
-------------

- ``absolute_path`` option can be set to use absolute paths instead of relative paths. Some applications may need this to work properly.. Default: ``no``
- ``dir`` option can be set to specify another output folder than the default library directory. Default: ``None``
- ``formats`` option can be set to select desired output type(s):
    - ``m3u``: catalog the imports in a centralized playlist.
    - ``m3u_multi``: create a new playlist for each import (uniquely named by appending the date and track/album name).
    - ``link``: create a symlink for each imported item. This is the recommended setting to propagate beets imports to your iTunes library: just drag and drop the ``dir`` folder on the iTunes dock icon.
    - ``echo``: do not write a playlist file at all, but echo a list of new file paths to the terminal.
Default: ``[]``
- ``m3u_name``: playlist name used by ``m3u`` format. Default: ``imported.m3u``.
- ``relative_to`` option can be set to make the m3u paths relative to another folder than where the playlist is being written. If you're using importfeeds to generate a playlist for MPD, you should set this to the
root of your music library. Default: ``None``

Here's an example configuration for this plugin::

    importfeeds:
        formats: m3u link
        dir: ~/imports/
        relative_to: ~/Music/
        m3u_name: newfiles.m3u
