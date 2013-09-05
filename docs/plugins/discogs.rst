Discogs Plugin
==============

The ``discogs`` plugin extends the autotagger's search capabilities to
include matches from the `Discogs`_ database.

.. _Discogs: http://discogs.com

Installation
------------

First, enable the ``discogs`` plugin (see :doc:`/plugins/index`). Then,
install the `discogs-client`_ library by typing::

    pip install discogs-client

That's it! Matches from Discogs will now show up during import alongside
matches from MusicBrainz.

If you have a Discogs ID for an album you want to tag, you can also enter it
at the "enter Id" prompt in the importer.

.. _discogs-client: https://github.com/discogs/discogs_client
