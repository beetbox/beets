MusicBrainz Collection Plugin
=============================

The ``mbcollection`` plugin lets you submit your catalog to MusicBrainz to
maintain your `music collection`_ list there.

.. _music collection: http://musicbrainz.org/doc/Collections

To begin, just enable the ``mbcollection`` plugin (see :doc:`/plugins/index`).
Then, add your MusicBrainz username and password to your
:doc:`configuration file </reference/config>` under a ``musicbrainz`` section::

    musicbrainz:
        user: you
        pass: seekrit

Then, use the ``beet mbupdate`` command to send your albums to MusicBrainz. The
command automatically adds all of your albums to the first collection it finds.
If you don't have a MusicBrainz collection yet, you may need to add one to your
profile first.

Automatically Update on Import
------------------------------

You can also configure the plugin to automatically amend your MusicBrainz
collection whenever you import a new album. To do this, first enable the
plugin and add your MusicBrainz account as above.  Then, add ``mbcollection``
section and enable the enable ``auto`` flag therein::

    mbcollection:
        auto: yes

During future imports, your default collection will be updated with each
imported album.
