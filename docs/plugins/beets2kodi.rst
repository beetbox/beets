Beets2Kodi Plugin
=================

The plugin lets you create nfo files for Kodi music
library whenever you import an album into the library. The plugin relies on the
information provided by beets library and the audiodb (TADB). It only uses 
MusicBrainz IDs, empty ID fields or discogs ID are ignored.

Configuration

To use ``beets2kodi`` plugin, enable it in your configuration
(see :ref:`using-plugins`).
Then, you'll want to configure the specifics of your Kodi host.
You can do that using a ``kodi:`` section and include audiodb.com api key in 
your ``config.yaml``,
which looks like this as per kodiupdate plugin::

    kodi:
        host: localhost
        port: 8080
        user: kodi
        pwd: kodi
        music_lib_name: music
        nfo_format: xml

    audiodb:
        key: secretkey or testkey '1'

The music_lib_name key is the name you given to your music library when 
importing/scanning your music to Kodi.
The nfo_format: Choices are 'xml' or 'mbid_only_text'.

To use the ``beets2kodi`` plugin you need  (urllib.request, lxml, simplejson, 
base64) modules.

You'll also need to enable JSON-RPC in Kodi in order the use the plugin.
In Kodi's interface, navigate to System/Settings/Network/Services and choose 
"Allow control of Kodi via HTTP."

With that all in place, you can create nfo/xml files for Kodi.


