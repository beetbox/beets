Discogs Plugin
==============

The ``discogs`` plugin extends the autotagger's search capabilities to
include matches from the `Discogs`_ database.

.. _Discogs: http://discogs.com

Installation
------------

To use the ``discogs`` plugin, first enable it in your configuration (see
:ref:`using-plugins`). Then, install the `discogs-client`_ library by typing::

    pip install discogs-client

You will also need to register for a `Discogs`_ account. The first time you
run the :ref:`import-cmd` command after enabling the plugin, it will ask you
to authorize with Discogs by visiting the site in a browser. Subsequent runs
will not require re-authorization.

Matches from Discogs will now show up during import alongside matches from
MusicBrainz.

If you have a Discogs ID for an album you want to tag, you can also enter it
at the "enter Id" prompt in the importer.

Troubleshooting
---------------

Several issues have been encountered with the Discogs API. If you have one,
please start by searching for `a similar issue on the repo
<https://github.com/beetbox/beets/issues?utf8=%E2%9C%93&q=is%3Aissue+discogs>`_.

Here are two things you can try:

* Try deleting the token file (``~/.config/beets/discogs_token.json`` by
  default) to force re-authorization.
* Make sure that your system clock is accurate. The Discogs servers can reject
  your request if your clock is too out of sync.

.. _discogs-client: https://github.com/discogs/discogs_client
