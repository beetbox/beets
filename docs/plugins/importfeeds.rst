ImportFeeds Plugin
==================

The ``importfeeds`` plugin helps you keep track of newly imported music in your library.

To use the plugin, just put ``importfeeds`` on the ``plugins`` line in your
:doc:`configuration file </reference/config>`. Then set a few options under the
``importfeeds:`` section in the config file.

The ``dir`` configuration option can be set to specify another folder
than the default library directory.

The ``relative_to`` configuration option can be set to make the m3u paths
relative to another folder than where the playlist is being written. If you're
using importfeeds to generate a playlist for MPD, you should set this to the
root of your music library.

The ``absolute_path`` configuration option can be set to use absolute paths
instead of relative paths. Some applications may need this to work properly.

Three different types of outputs coexist, specify the ones you want to use by
setting the ``formats`` parameter:

- ``m3u``: catalog the imports in a centralized playlist. By default, the playlist is named ``imported.m3u``. To use a different file, just set the ``m3u_name`` parameter inside the ``importfeeds`` config section.
- ``m3u_multi``: create a new playlist for each import (uniquely named by appending the date and track/album name).
- ``link``: create a symlink for each imported item. This is the recommended setting to propagate beets imports to your iTunes library: just drag and drop the ``dir`` folder on the iTunes dock icon.

Here's an example configuration for this plugin::

    importfeeds:
        formats: m3u link
        dir: ~/imports/
        relative_to: ~/Music/
        m3u_name: newfiles.m3u
