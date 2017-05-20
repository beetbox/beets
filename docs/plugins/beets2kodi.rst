Beets2Kodi Plugin
=================

The plugin lets you create nfo files for Kodi music
library whenever you import an album into the library.
It only creates artist and album .nfos. As no documentation of track .nfo on Kodi wiki. 

To use ``Beets2Kodi`` plugin, enable it in your configuration
(see :ref:`using-plugins`).
Then, you'll want to configure the specifics of your Kodi host.
You can do that using a ``kodi:`` section and include audiodb.com api key in your ``config.yaml``,
which looks like this as per kodiupdate plugin::

    kodi:
        host: localhost
        port: 8080
        user: kodi
        pwd: kodi
        nfo_format: xml # (or mbid_url_only)
        library_name: music
    audiodb:
        key: secretkey or testkey '1'

The nfo_format key, tells plugin to produce XML type document or a text file with MBID url

To use the ``beets2kodi`` plugin you need  (requests, lxml, simplejson. base64) libraries

You'll also need to enable JSON-RPC in Kodi in order the use the plugin.
In Kodi's interface, navigate to System/Settings/Network/Services and choose "Allow control of Kodi via HTTP."

With that all in place, you can create nfo files for Kodi.


