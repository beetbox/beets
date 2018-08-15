Gmusic Plugin
=============

The ``gmusic`` plugin lets you upload songs to Google Play Music and query
songs in your library.


Installation
------------

The plugin requires `gmusicapi`_. You can install it using `pip`::

    pip install gmusicapi

.. _gmusicapi: https://github.com/simon-weber/gmusicapi/

Then, you can enable the ``gmusic`` plugin in your configuration (see
:ref:`using-plugins`).


Usage
-----
Configuration is required before use. Below is an example configuration::

    gmusic:
        email: user@example.com
        password: seekrit
        auto: yes
        uploader_id: 00:11:22:33:AA:BB
        device_id: 00112233AABB
        oauth_file: ~/.config/beets/oauth.cred


To upload tracks to Google Play Music, use the ``gmusic-upload`` command::

    beet gmusic-upload [QUERY]

If you don't include a query, the plugin will upload your entire collection.

To list your music collection, use the ``gmusic-songs`` command::

    beet gmusic-songs [-at] [ARGS]

Use the ``-a`` option to search by artist and ``-t`` to search by track. For
example::

    beet gmusic-songs -a John Frusciante
    beet gmusic-songs -t Black Hole Sun

For a list of all songs in your library, run ``beet gmusic-songs`` without any
arguments.


Configuration
-------------
To configure the plugin, make a ``gmusic:`` section in your configuration file.
The available options are:

- **email**: Your Google account email address.  
  Default: none.
- **password**: Password to your Google account. Required to query songs in
  your collection.  
  For accounts with 2-step-verification, an
  `app password <https://support.google.com/accounts/answer/185833?hl=en>`__
  will need to be generated. An app password for an account without
  2-step-verification is not required but is recommended.  
  Default: none.
- **auto**: Set to ``yes`` to automatically upload new imports to Google Play
  Music.  
  Default: ``no``
- **uploader_id**: Unique id as a MAC address, eg ``00:11:22:33:AA:BB``.
  This option should be set before the maximum number of authorized devices is
  reached.  
  If provided, use the same id for all future runs on this, and other, beets
  installations as to not reach the maximum number of authorized devices.  
  Default: device's MAC address.
- **device_id**: Unique device ID for authorized devices. It is usually
  the same as your MAC address with the colons removed, eg ``00112233AABB``.  
  This option only needs to be set if you receive an `InvalidDeviceId`
  exception. Below the exception will be a list of valid device IDs.  
  Default: none.
- **oauth_file**: Filepath for oauth credentials file.  
  Default: `{user_data_dir} <https://pypi.org/project/appdirs/>`__/gmusicapi/oauth.cred

Refer to the `Google Play Music Help
<https://support.google.com/googleplaymusic/answer/3139562?hl=en>`__
page for more details on authorized devices.
