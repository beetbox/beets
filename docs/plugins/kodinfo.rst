KodiNfo Plugin
=================

The plugin lets you create nfo files for Kodi music
library and update it whenever you import an album into the library. 
The plugin relies on the information provided by beets library and the audiodb
(TADB). It only uses MusicBrainz album IDs, empty ID fields or discogs ID 
are ignored.

Configuration
______________

To use ``kodinfo`` plugin, enable it in your configuration
(see :ref:`using-plugins`).
Then, you'll want to configure the specifics of your Kodi host.
You can do that using a ``kodi:`` section in your ``config.yaml``,
which will look like this::

    kodi:
        host: localhost
        port: 8080
        user: kodi
        pwd: kodi
        nfo_format: xml

    
For the nfo_format key, choices are 'xml' or 'mbid_only_text'.
The choice 'xml' produces XML type document, while the 'mbid_only_text'
produces a text file containing the MusicBrainz url of the artist or album.

To use the ``kodinfo`` plugin you need  (requests, urllib.request, lxml, 
simplejson, base64) modules.

You'll also need to enable JSON-RPC in Kodi in order the use the plugin.
In Kodi's interface, navigate to System/Settings/Network/Services and choose 
"Allow control of Kodi via HTTP."

With that all in place, you can create nfo/xml files for Kodi and update it's 
library after import.
