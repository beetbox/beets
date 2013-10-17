Beatport Plugin
===============

.. warning::

  As of October 2013, Beatport has `closed their API`_. We've contacted them
  to attempt to gain access as a "partner." Until this happens, though, this
  plugin won't work.

The ``beatport`` plugin adds support for querying the `Beatport`_ catalogue
during the autotagging process. This can potentially be helpful for users
whose collection includes a lot of diverse electronic music releases, for which
both MusicBrainz and (to a lesser degree) Discogs show no matches.

.. _Beatport: http://beatport.com
.. _closed their API: http://api.beatport.com

Installation
------------

To see matches from the ``beatport`` plugin, you first have to enable it in
your configuration (see :doc:`/plugins/index`). Then, install the `requests`_
library (which we need for querying the Beatport API) by typing::

    pip install requests

And you're done. Matches from Beatport should now show up alongside matches
from MusicBrainz and other sources.

If you have a Beatport ID or a URL for a release or track you want to tag, you
can just enter one of the two at the "enter Id" prompt in the importer.

.. _requests: http://docs.python-requests.org/en/latest/
