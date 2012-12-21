ImportFeeds Plugin
==================

The ``importfeeds`` plugin helps you keep track of newly imported music in your library.

To use the plugin, just put ``importfeeds`` on the ``plugins`` line in your
:doc:`configuration file </reference/config>`. Then set a few options under the
``importfeeds:`` section in the config file.

The ``feeds_dir`` configuration option can be set to specify another folder
than the default library directory. Three different types of outputs coexist,
specify the ones you want to use by setting the ``feeds_formats`` parameter: 

- ``m3u``: catalog the imports in a centralized playlist. By default, the playlist is named ``imported.m3u``. To use a different file, just set the ``m3u_name`` parameter inside the ``importfeeds`` config section.
- ``m3u_multi``: create a new playlist for each import (uniquely named by appending the date and track/album name). 
- ``link``: create a symlink for each imported item. This is the recommended setting to propagate beets imports to your iTunes library: just drag and drop the ``feeds_dir`` folder on the iTunes dock icon.

Here's an example configuration for this plugin::

    importfeeds:
        feeds_formats: m3u link
        feeds_dir: ~/imports/
        m3u_name: newfiles.m3u
