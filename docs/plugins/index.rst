Plugins
=======

Plugins can extend beets' core functionality. Plugins can add new commands to
the command-line interface, respond to events in beets, augment the autotagger,
or provide new path template functions.

Using Plugins
-------------

To use a plugin, you have two options:

* Make sure it's in the Python path (known as `sys.path` to developers). This
  just means the plugin has to be installed on your system (e.g., with a
  `setup.py` script or a command like `pip` or `easy_install`).

* Set the `pythonpath` config variable to point to the directory containing the
  plugin. (See :doc:`/reference/cli`.)

Then, set the `plugins` option in your `~/.beetsconfig` file, like so::

    [beets]
    plugins = mygreatplugin someotherplugin

The value for `plugins` should be a space-separated list of plugin module names.

.. _included-plugins:

Plugins Included With Beets
---------------------------

There are a few plugins that are included with the beets distribution. They're
disabled by default, but you can turn them on as described above:

.. toctree::
   :maxdepth: 1

   chroma
   lyrics
   bpd
   mpdupdate
   embedart
   web
   lastgenre
   replaygain
   inline
   scrub
   rewrite
   m3uupdate

.. _other-plugins:

Other Plugins
-------------

Here are a few of the plugins written by the beets community:

* `beetFs`_ is a FUSE filesystem for browsing the music in your beets library.
  (Might be out of date.)

* `Beet-MusicBrainz-Collection`_ lets you add albums from your library to your
  MusicBrainz `"music collection"`_.

* `A cmus plugin`_ integrates with the `cmus`_ console music player.

.. _beetFs: http://code.google.com/p/beetfs/
.. _Beet-MusicBrainz-Collection:
    https://github.com/jeffayle/Beet-MusicBrainz-Collection/
.. _"music collection": http://musicbrainz.org/show/collection/
.. _A cmus plugin:
    https://github.com/coolkehon/beets/blob/master/beetsplug/cmus.py
.. _cmus: http://cmus.sourceforge.net/

Writing Plugins
---------------

If you know a little Python, you can write your own plugin to do almost anything
you can imagine with your music collection. See the :doc:`guide to writing beets
plugins </plugins/writing>`.

.. toctree::
    :hidden:
    
    writing
