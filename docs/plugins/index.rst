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
   bpd
   mpdupdate
   embedart
   web
   lastgenre
   replaygain
   inline
   scrub
   rewrite

.. _other-plugins:

Other Plugins
-------------

Here are a few of the plugins written by the beets community:

* `beets-lyrics`_ searches Web repositories for song lyrics and adds them to your files.

* `beetFs`_ is a FUSE filesystem for browsing the music in your beets library.
  (Might be out of date.)

* `Beet-MusicBrainz-Collection`_ lets you add albums from your library to your
  MusicBrainz `"music collection"`_.

* `A cmus plugin`_ integrates with the `cmus`_ console music player.

.. _beets-replaygain: https://github.com/Lugoues/beets-replaygain/
.. _beets-lyrics: https://github.com/Lugoues/beets-lyrics/
.. _beetFs: http://code.google.com/p/beetfs/
.. _Beet-MusicBrainz-Collection:
    https://github.com/jeffayle/Beet-MusicBrainz-Collection/
.. _"music collection": http://musicbrainz.org/show/collection/
.. _A cmus plugin:
    https://github.com/coolkehon/beets/blob/master/beetsplug/cmus.py
.. _cmus: http://cmus.sourceforge.net/

.. _writing-plugins:

Writing Plugins
---------------

A beets plugin is just a Python module inside the ``beetsplug`` namespace
package. (Check out this `Stack Overflow question about namespace packages`_ if
you haven't heard of them.) So, to make one, create a directory called
``beetsplug`` and put two files in it: one called ``__init__.py`` and one called
``myawesomeplugin.py`` (but don't actually call it that). Your directory
structure should look like this::

    beetsplug/
        __init__.py
        myawesomeplugin.py

.. _Stack Overflow question about namespace packages:
    http://stackoverflow.com/questions/1675734/how-do-i-create-a-namespace-package-in-python/1676069#1676069

Then, you'll need to put this stuff in ``__init__.py`` to make ``beetsplug`` a
namespace package::

    from pkgutil import extend_path
    __path__ = extend_path(__path__, __name__)

That's all for ``__init__.py``; you can can leave it alone. The meat of your
plugin goes in ``myawesomeplugin.py``. There, you'll have to import the
``beets.plugins`` module and define a subclass of the ``BeetsPlugin`` class
found therein. Here's a skeleton of a plugin file::

    from beets.plugins import BeetsPlugin

    class MyPlugin(BeetsPlugin):
        pass

Once you have your ``BeetsPlugin`` subclass, there's a variety of things your
plugin can do. (Read on!)

To use your new plugin, make sure your ``beetsplug`` directory is in the Python
path (using ``PYTHONPATH`` or by installing in a `virtualenv`_, for example).
Then, as described above, edit your ``.beetsconfig`` to include
``plugins=myawesomeplugin`` (substituting the name of the Python module
containing your plugin).

.. _virtualenv: http://pypi.python.org/pypi/virtualenv

Add Commands to the CLI
^^^^^^^^^^^^^^^^^^^^^^^

Plugins can add new subcommands to the ``beet`` command-line interface. Define
the plugin class' ``commands()`` method to return a list of ``Subcommand``
objects. (The ``Subcommand`` class is defined in the ``beets.ui`` module.)
Here's an example plugin that adds a simple command::

    from beets.plugins import BeetsPlugin
    from beets.ui import Subcommand

    my_super_command = Subcommand('super', help='do something super')
    def say_hi(lib, config, opts, args):
        print "Hello everybody! I'm a plugin!"
    my_super_command.func = say_hi

    class SuperPlug(BeetsPlugin):
        def commands(self):
            return [my_super_command]

To make a subcommand, invoke the constructor like so: ``Subcommand(name, parser,
help, aliases)``. The ``name`` parameter is the only required one and should
just be the name of your command. ``parser`` can be an `OptionParser instance`_,
but it defaults to an empty parser (you can extend it later). ``help`` is a
description of your command, and ``aliases`` is a list of shorthand versions of
your command name.

.. _OptionParser instance: http://docs.python.org/library/optparse.html

You'll need to add a function to your command by saying ``mycommand.func =
myfunction``. This function should take the following parameters: ``lib`` (a
beets ``Library`` object), ``config`` (a `ConfigParser object`_ containing the
configuration values), and ``opts`` and ``args`` (command-line options and
arguments as returned by `OptionParser.parse_args`_).

.. _ConfigParser object: http://docs.python.org/library/configparser.html
.. _OptionParser.parse_args:
    http://docs.python.org/library/optparse.html#parsing-arguments

The function should use any of the utility functions defined in ``beets.ui``.
Try running ``pydoc beets.ui`` to see what's available.

You can add command-line options to your new command using the ``parser`` member
of the ``Subcommand`` class, which is an ``OptionParser`` instance. Just use it
like you would a normal ``OptionParser`` in an independent script.

Listen for Events
^^^^^^^^^^^^^^^^^

Event handlers allow plugins to run code whenever something happens in beets'
operation. For instance, a plugin could write a log message every time an album
is successfully autotagged or update MPD's index whenever the database is
changed.

You can "listen" for events using the ``BeetsPlugin.listen`` decorator. Here's
an example::

    from beets.plugins import BeetsPlugin

    class SomePlugin(BeetsPlugin):
        pass

    @SomePlugin.listen('pluginload')
    def loaded():
        print 'Plugin loaded!'

Pass the name of the event in question to the ``listen`` decorator. The events
currently available are:

* *pluginload*: called after all the plugins have been loaded after the ``beet``
  command starts

* *save*: called whenever the library is changed and written to disk (the
  ``lib`` keyword argument is the Library object that was written)

* *import*: called after a ``beet import`` command fishes (the ``lib`` keyword
  argument is a Library object; ``paths`` is a list of paths (strings) that were
  imported)

* *album_imported*: called with an ``Album`` object every time the ``import``
  command finishes adding an album to the library. Parameters: ``lib``,
  ``album``, ``config``

* *item_imported*: called with an ``Item`` object every time the importer adds a
  singleton to the library (not called for full-album imports). Parameters:
  ``lib``, ``item``, ``config``

* *write*: called with an ``Item`` and a ``MediaFile`` object just before a
  file's metadata is written to disk.

The included ``mpdupdate`` plugin provides an example use case for event listeners.

Extend the Autotagger
^^^^^^^^^^^^^^^^^^^^^

Plugins in can also enhance the functionality of the autotagger. For a
comprehensive example, try looking at the ``chroma`` plugin, which is included
with beets.

A plugin can extend three parts of the autotagger's process: the track distance
function, the album distance function, and the initial MusicBrainz search. The
distance functions determine how "good" a match is at the track and album
levels; the initial search controls which candidates are presented to the
matching algorithm. Plugins implement these extensions by implementing three
methods on the plugin class:

* ``track_distance(self, item, info)``: adds a component to the distance
  function (i.e., the similarity metric) for individual tracks. ``item`` is the
  track to be matched (and Item object) and ``info`` is the MusicBrainz track
  entry that is proposed as a match. Should return a ``(dist, dist_max)`` pair
  of floats indicating the distance.

* ``album_distance(self, items, info)``: like the above, but compares a list of
  items (representing an album) to an album-level MusicBrainz entry. Should
  only consider album-level metadata (e.g., the artist name and album title) and
  should not duplicate the factors considered by ``track_distance``.

* ``candidates(self, items)``: given a list of items comprised by an album to be
  matched, return a list of ``AlbumInfo`` objects for candidate albums to be
  compared and matched.

* ``item_candidates(self, item)``: given a *singleton* item, return a list of
  ``TrackInfo`` objects for candidate tracks to be compared and matched.

When implementing these functions, it will probably be very necessary to use the
functions from the ``beets.autotag`` and ``beets.autotag.mb`` modules, both of
which have somewhat helpful docstrings.

Read Configuration Options
^^^^^^^^^^^^^^^^^^^^^^^^^^

Plugins can configure themselves using the ``.beetsconfig`` file. Define a
``configure`` method on your plugin that takes an ``OptionParser`` object as an
argument. Then use the ``beets.ui.config_val`` convenience function to access
values from the config file. Like so::

    class MyPlugin(BeetsPlugin):
        def configure(self, config):
            number_of_goats = beets.ui.config_val(config, 'myplug', 'goats', '42')

Try looking at the ``mpdupdate`` plugin (included with beets) for an example of
real-world use of this API.

Add Path Format Functions and Fields
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Beets supports *function calls* in its path format syntax (see
:doc:`/reference/pathformat`). Beets includes a few built-in functions, but
plugins can add new functions using the ``template_func`` decorator. To use it,
decorate a function with ``MyPlugin.template_func("name")`` where ``name`` is
the name of the function as it should appear in template strings.

Here's an example::

    class MyPlugin(BeetsPlugin):
        pass
    @MyPlugin.template_func('initial')
    def _tmpl_initial(text):
        if text:
            return text[0].upper()
        else:
            return u''

This plugin provides a function ``%initial`` to path templates where
``%initial{$artist}`` expands to the artist's initial (its capitalized first
character).

Plugins can also add template *fields*, which are computed values referenced as
``$name`` in templates. To add a new field, decorate a function taking a single
parameter, ``item``, with ``MyPlugin.template_field("name")``. Here's an example
that adds a ``$disc_and_track`` field::

    @MyPlugin.template_field('disc_and_track')
    def _tmpl_disc_and_track(item):
        """Expand to the disc number and track number if this is a
        multi-disc release. Otherwise, just exapnds to the track
        number.
        """
        if item.disctotal > 1:
            return u'%02i.%02i' % (item.disc, item.track)
        else:
            return u'%02i' % (item.track)

With this plugin enabled, templates can reference ``$disc_and_track`` as they
can any standard metadata field.
