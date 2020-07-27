MusicBrainz Collection Plugin
=============================

The ``mbcollection`` plugin lets you submit your catalog to MusicBrainz to
maintain your `music collection`_ list there.

.. _music collection: https://musicbrainz.org/doc/Collections

To begin, just enable the ``mbcollection`` plugin in your
configuration (see :ref:`using-plugins`).
Then, add your MusicBrainz username and password to your
:doc:`configuration file </reference/config>` under a ``musicbrainz`` section::

    musicbrainz:
        user: you
        pass: seekrit

Then, use the ``beet mbupdate`` command to send your albums to MusicBrainz. The
command automatically adds all of your albums to the first collection it finds.
If you don't have a MusicBrainz collection yet, you may need to add one to your
profile first.

The command has one command-line option:

* To remove albums from the collection which are no longer present in
  the beets database, use the ``-r`` (``--remove``) flag.


Configuration
-------------

To configure the plugin, make a ``mbcollection:`` section in your
configuration file. There is one option available:

- **auto**: Automatically amend your MusicBrainz collection whenever you
  import a new album.
  Default: ``no``.
- **collection**: The MBID of which MusicBrainz collection to update.
  Default: ``None``.
- **remove**: Remove albums from collections which are no longer
  present in the beets database.
  Default: ``no``.
