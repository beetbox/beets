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

Auto Update Mode
----------------

You can now add each imported album to your MusicBrainz collection, without 
needing a separate ``beet mbupdate`` command.  To do this, first enable the 
plugin and add your MusicBrainz account using the instructions above.  Then, 
add a block for the ``mbcollection`` plugin to enable ``auto`` configuration::

    mbcollection:
        auto: yes

During future imports, your default collection will be updated with the
imported album.