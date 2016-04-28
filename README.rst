.. image:: http://img.shields.io/pypi/v/beets.svg
    :target: https://pypi.python.org/pypi/beets

.. image:: https://img.shields.io/pypi/dw/beets.svg
    :target: https://pypi.python.org/pypi/beets#downloads

.. image:: http://img.shields.io/codecov/c/github/beetbox/beets.svg
    :target: https://codecov.io/github/beetbox/beets

.. image:: https://travis-ci.org/beetbox/beets.svg?branch=master
    :target: https://travis-ci.org/beetbox/beets


Beets is the media library management system for obsessive-compulsive music
geeks.

The purpose of beets is to get your music collection right once and for all.
It catalogs your collection, automatically improving its metadata as it goes.
It then provides a bouquet of tools for manipulating and accessing your music.

Here's an example of beets' brainy tag corrector doing its thing::

  $ beet import ~/music/ladytron
  Tagging:
      Ladytron - Witching Hour
  (Similarity: 98.4%)
   * Last One Standing      -> The Last One Standing
   * Beauty                 -> Beauty*2
   * White Light Generation -> Whitelightgenerator
   * All the Way            -> All the Way...

Because beets is designed as a library, it can do almost anything you can
imagine for your music collection. Via `plugins`_, beets becomes a panacea:

- Fetch or calculate all the metadata you could possibly need: `album art`_,
  `lyrics`_, `genres`_, `tempos`_, `ReplayGain`_ levels, or `acoustic
  fingerprints`_.
- Get metadata from `MusicBrainz`_ or `Discogs`_. Or guess
  metadata using songs' filenames or their acoustic fingerprints.
- `Transcode audio`_ to any format you like.
- Check your library for `duplicate tracks and albums`_ or for `albums that
  are missing tracks`_.
- Clean up crufty tags left behind by other, less-awesome tools.
- Embed and extract album art from files' metadata.
- Browse your music library graphically through a Web browser and play it in any
  browser that supports `HTML5 Audio`_.
- Analyze music files' metadata from the command line.
- Listen to your library with a music player that speaks the `MPD`_ protocol
  and works with a staggering variety of interfaces.

If beets doesn't do what you want yet, `writing your own plugin`_ is
shockingly simple if you know a little Python.

.. _plugins: http://beets.readthedocs.org/page/plugins/
.. _MPD: http://www.musicpd.org/
.. _MusicBrainz music collection: http://musicbrainz.org/doc/Collections/
.. _writing your own plugin:
    http://beets.readthedocs.org/page/dev/plugins.html
.. _HTML5 Audio:
    http://www.w3.org/TR/html-markup/audio.html
.. _albums that are missing tracks:
    http://beets.readthedocs.org/page/plugins/missing.html
.. _duplicate tracks and albums:
    http://beets.readthedocs.org/page/plugins/duplicates.html
.. _Transcode audio:
    http://beets.readthedocs.org/page/plugins/convert.html
.. _Discogs: http://www.discogs.com/
.. _acoustic fingerprints:
    http://beets.readthedocs.org/page/plugins/chroma.html
.. _ReplayGain: http://beets.readthedocs.org/page/plugins/replaygain.html
.. _tempos: http://beets.readthedocs.org/page/plugins/echonest.html
.. _genres: http://beets.readthedocs.org/page/plugins/lastgenre.html
.. _album art: http://beets.readthedocs.org/page/plugins/fetchart.html
.. _lyrics: http://beets.readthedocs.org/page/plugins/lyrics.html
.. _MusicBrainz: http://musicbrainz.org/

Read More
---------

Learn more about beets at `its Web site`_. Follow `@b33ts`_ on Twitter for
news and updates.

You can install beets by typing ``pip install beets``. Then check out the
`Getting Started`_ guide.

.. _its Web site: http://beets.io/
.. _Getting Started: http://beets.readthedocs.org/page/guides/main.html
.. _@b33ts: http://twitter.com/b33ts/

Authors
-------

Beets is by `Adrian Sampson`_ with a supporting cast of thousands. For help,
please contact the `mailing list`_.

.. _mailing list: https://groups.google.com/forum/#!forum/beets-users
.. _Adrian Sampson: http://homes.cs.washington.edu/~asampson/
