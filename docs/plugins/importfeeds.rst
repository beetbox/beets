ImportFeeds Plugin
==================

This plugin helps you keep track of newly imported music in your library.

To use the ``importfeeds`` plugin, enable it in your configuration
(see :ref:`using-plugins`).

Configuration
-------------

To configure the plugin, make an ``importfeeds:`` section in your
configuration file. The available options are:

- **absolute_path**: Use absolute paths instead of relative paths. Some
  applications may need this to work properly.
  Default: ``no``.
- **dir**: The output directory.
  Default: Your beets library directory.
- **formats**: Select the kind of output. Use one or more of:

   - **m3u**: Catalog the imports in a centralized playlist.
   - **m3u_multi**: Create a new playlist for each import (uniquely named by
     appending the date and track/album name).
   - **link**: Create a symlink for each imported item. This is the
     recommended setting to propagate beets imports to your iTunes library:
     just drag and drop the ``dir`` folder on the iTunes dock icon.
   - **echo**: Do not write a playlist file at all, but echo a list of new
     file paths to the terminal.

  Default: None.
- **m3u_name**: Playlist name used by the ``m3u`` format.
  Default: ``imported.m3u``.
- **relative_to**: Make the m3u paths relative to another
  folder than where the playlist is being written. If you're using importfeeds
  to generate a playlist for MPD, you should set this to the root of your music
  library.
  Default: None.

Here's an example configuration for this plugin::

    importfeeds:
        formats: m3u link
        dir: ~/imports/
        relative_to: ~/Music/
        m3u_name: newfiles.m3u
