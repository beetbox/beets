KodiNfo Plugin
=================

The plugin lets you create local `.nfo`_ files for `Kodi`_ music
library whenever you import an album into the library. The .nfo files can either be in `XML file format`_ or a `text file`_ containing the link to MusicBrainz release or artist page. These .nfo files contain information about your music library and may include album/artist rating, reviews, biographies and extra images. The local .nfo is also used by Kodi to point scrapers to relevant URLs and or data contained in the XML format file.
The plugin relies on the information provided by beets library and `The AudioDB`_
(TADB). It uses MusicBrainz IDs to look up metadata.

.. _.nfo: http://kodi.wiki/view/NFO_files
.. _Kodi: http://www.kodi.tv
.. _The AudioDB: http://www.theaudiodb.com
.. _XML file format: http://kodi.wiki/view/NFO_files/music#Music_.nfo_Files_containing_XML_data
.. _text file: http://kodi.wiki/view/NFO_files/music#Music_.nfo_files_containing_an_URL

Installation
______________

The plugin requires `lxml`_ module to generate XML format , which you can install using `pip`_ by typing:

``pip install lxml``

After you have lxml installed, enable the ``kodinfo`` plugin in your configuration (see :ref:`using-plugins`).

.. _lxml: http://lxml.de/
.. _pip: http://www.pip-installer.org/

Configuration
______________
To configure the plugin, create a ``kodi:`` section in your ``config.yaml``,
to look like this::

    kodi:
        host: localhost
        port: 8080
        user: kodi
        pwd: kodi
        nfo_format: xml

**host:** The host of your kodi library (either the IP address or server name of your kodi installed computer).

**port:** The host's port where Kodi is running, ussually ``8080``

**user:** Kodi's user, default is ``kodi``

**pwd:** Kodi user's password, default is ``kodi``

**nfo_format:** The user's preffered .nfo format, either ``xml`` for XML format type .nfo, or ``text`` for a text file containg URL to Musicbrainz release or artist page.

    
Yoyu also need to enable JSON-RPC in Kodi in order the use the plugin.

In Kodi's interface, navigate to System/Settings/Network/Services and choose 
"Allow control of Kodi via HTTP."

With that all in place, you can create nfo/xml files for Kodi music library after import.
