LastGenre Plugin
================

The MusicBrainz database `does not contain genre information`_. Therefore, when
importing and autotagging music, beets does not assign a genre.  The
``lastgenre`` plugin fetches *tags* from `Last.fm`_ and assigns them as genres
to your albums and items. The plugin is included with beets as of version
1.0b11.

.. _does not contain genre information:
    http://musicbrainz.org/doc/General_FAQ#Why_does_MusicBrainz_not_support_genre_information.3F
.. _Last.fm: http://last.fm/

The plugin requires `pylast`_, which you can install using `pip`_ by typing::

    pip install pylast

After you have pylast installed, enable the plugin by putting ``lastgenre`` on
your ``plugins`` line in :doc:`/reference/config`, like so::

    [beets]
    plugins: lastgenre

For the time being, the genre-selection algorithm is pretty dumb: the most
popular tag is treated as the genre. This could be enhanced by using a "white
list" of known genre names. (This would be a great project for someone looking
to contribute to the beets project!)

.. _pip: http://www.pip-installer.org/
.. _pylast: http://code.google.com/p/pylast/
