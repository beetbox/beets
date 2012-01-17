Beets is the media library management system for obsessive-compulsive music
geeks.

The purpose of beets is to get your music collection right once and for all.
It catalogs your collection, automatically improving its metadata as it goes.
It then provides a bouquet of tools for manipulating and accessing your music.

Here's an example of beets' brainy tag corrector doing its thing::

  $ beet import ~/music/ladytron
  Tagging: Ladytron - Witching Hour
  (Similarity: 98.4%)
   * Last One Standing -> The Last One Standing
   * Beauty -> Beauty*2
   * White Light Generation -> Whitelightgenerator
   * All the Way -> All the Way...

Because beets is designed as a library, it can do almost anything you can
imagine for your music collection. Via `plugins`_, beets becomes a panacea:

- Embed and extract album art from files' metadata.
- Listen to your library with a music player that speaks the `MPD`_ protocol
  and works with a staggering variety of interfaces.
- Fetch lyrics for all your songs from databases on the Web.
- Manage your `MusicBrainz music collection`_.
- Analyze music files' metadata from the command line.
- Clean up crufty tags left behind by other, less-awesome tools.
- Browse your music library graphically through a Web browser and play it in any
  browser that supports `HTML5 Audio`_.

If beets doesn't do what you want yet, `writing your own plugin`_ is
shockingly simple if you know a little Python.

.. _plugins: http://readthedocs.org/docs/beets/-/plugins/
.. _MPD: http://mpd.wikia.com/
.. _MusicBrainz music collection: http://musicbrainz.org/show/collection/
.. _writing your own plugin:
    http://readthedocs.org/docs/beets/-/plugins/#writing-plugins
.. _HTML5 Audio:
    http://www.w3.org/TR/html-markup/audio.html

Read More
---------

Learn more about beets at `its Web site`_. Follow `@b33ts`_ on Twitter for
news and updates.

Check out the `Getting Started`_ guide to learn about installing and using
beets.

.. _its Web site: http://beets.radbox.org/
.. _Getting Started: http://readthedocs.org/docs/beets/-/guides/main.html
.. _@b33ts: http://twitter.com/b33ts/

Authors
-------

Beets is by `Adrian Sampson`_.

.. _Adrian Sampson: mailto:adrian@radbox.org

