MusicBrainz Collection Plugin
=============================

The ``mbcollection`` plugin lets you submit your catalog to MusicBrainz to
maintain your `music collection`_ list there.

.. _music collection: http://musicbrainz.org/show/collection/

To begin, just enable the ``mbcollection`` plugin (see :doc:`/plugins/index`).
Then, add your MusicBrainz username and password to your
:doc:`/reference/config` in a ``musicbrainz`` section::

    [musicbrainz]
    user: USERNAME
    pass: PASSWORD

Then, use the ``beet mbupdate`` command to send your albums to MusicBrainz. The
command automatically adds all of your albums to the first collection it finds.
If you don't have a MusicBrainz collection yet, you may need to add one to your
profile first.
