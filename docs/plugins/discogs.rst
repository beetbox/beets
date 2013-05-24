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

Matches from Discogs will now show up during import alongside matches from
MusicBrainz.

.. _discogs-client: https://github.com/discogs/discogs_client

Configuration
-------------

You can use the :ref:`max_rec` setting to define a maximum recommendation level
for matches from Discogs::

    match:
        max_rec:
            discogs: medium

This example would prevent the auto-tagger from automatically applying a
strong match from Discogs, and give you a chance to confirm the changes. The
default is ``strong``.
