Beatport Plugin
===============

The ``beatport`` plugin adds support for querying the `Beatport`_ catalogue
during the autotagging process. This can potentially be helpful for users
whose collection includes a lot of diverse electronic music releases, for which
both MusicBrainz and (to a lesser degree) `Discogs`_ show no matches.

.. _Discogs: https://discogs.com

Installation
------------

To use the ``beatport`` plugin, first enable it in your configuration (see
:ref:`using-plugins`). Then, install the `requests`_ library
(which we need for querying the Beatport API) by typing::

    pip install requests

You will also need to register for a `Beatport`_ account. The first time you
run the :ref:`import-cmd` command after enabling the plugin, it will ask you
to provide the Beatport API access token to authorize beets to query
the Beatport API. User OAuth token structure looks like this:

.. code-block:: json

    {
      "access_token": "XXX",
      "expires_in": 36000,
      "token_type": "Bearer",
      "scope": "XXX",
      "refresh_token": "XXX"
    }

Copy the whole JSON and paste it into the terminal (or directly into
``beatport_token.json`` file in the directory next to your beets config).
This will store the authentication data for subsequent runs,
but after the token expires, you will have to repeat the above.

Usage
-----

Matches from Beatport should now show up alongside matches
from MusicBrainz and other sources.

If you have a Beatport ID or a URL for a release or track you want to tag, you
can just enter one of the two at the "enter Id" prompt in the importer. You can
also search for an id like so::

    beet import path/to/music/library --search-id id

Configuration
-------------
This plugin can be configured like other metadata source
plugins as described in :ref:`metadata-source-plugin-configuration`.

.. _requests: https://requests.readthedocs.io/en/master/
.. _Beatport: https://www.beatport.com/
