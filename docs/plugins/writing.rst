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
Then, as described above, edit your ``config.yaml`` to include
``plugins: myawesomeplugin`` (substituting the name of the Python module
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
    def say_hi(lib, opts, args):
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
beets ``Library`` object) and ``opts`` and ``args`` (command-line options and
arguments as returned by `OptionParser.parse_args`_).

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

* *import*: called after a ``beet import`` command fishes (the ``lib`` keyword
  argument is a Library object; ``paths`` is a list of paths (strings) that were
  imported)

* *album_imported*: called with an ``Album`` object every time the ``import``
  command finishes adding an album to the library. Parameters: ``lib``,
  ``album``

* *item_imported*: called with an ``Item`` object every time the importer adds a
  singleton to the library (not called for full-album imports). Parameters:
  ``lib``, ``item``

* *write*: called with an ``Item`` object just before a file's metadata is
  written to disk (i.e., just before the file on disk is opened).

* *import_task_start*: called when before an import task begins processing.
  Parameters: ``task`` (an `ImportTask`) and ``session`` (an `ImportSession`).

* *import_task_apply*: called after metadata changes have been applied in an
  import task. Parameters: ``task`` and ``session``.

* *import_task_choice*: called after a decision has been made about an import
  task. This event can be used to initiate further interaction with the user.
  Use ``task.choice_flag`` to determine the action to be taken. Parameters:
  ``task`` and ``session``.

* *import_task_files*: called after an import task finishes manipulating the
  filesystem (copying and moving files, writing metadata tags). Parameters:
  ``task`` and ``session``.

* *library_opened*: called after beets starts up and initializes the main
  Library object. Parameter: ``lib``.

* *database_change*: a modification has been made to the library database. The
  change might not be committed yet. Parameter: ``lib``.

* *cli_exit*: called just before the ``beet`` command-line program exits.
  Parameter: ``lib``.

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
  track to be matched (an Item object) and ``info`` is the TrackInfo object
  that is proposed as a match. Should return a ``(dist, dist_max)`` pair
  of floats indicating the distance.

* ``album_distance(self, items, album_info, mapping)``: like the above, but
  compares a list of items (representing an album) to an album-level MusicBrainz
  entry. ``items`` is a list of Item objects; ``album_info`` is an AlbumInfo
  object; and ``mapping`` is a dictionary that maps Items to their corresponding
  TrackInfo objects.

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

Plugins can configure themselves using the ``config.yaml`` file. You can read
configuration values in two ways. The first is to use `self.config` within
your plugin class. This gives you a view onto the configuration values in a
section with the same name as your plugin's module. For example, if your plugin
is in ``greatplugin.py``, then `self.config` will refer to options under the
``greatplugin:`` section of the config file.

For example, if you have a configuration value called "foo", then users can put
this in their ``config.yaml``::

    greatplugin:
        foo: bar

To access this value, say ``self.config['foo'].get()`` at any point in your
plugin's code. The `self.config` object is a *view* as defined by the `Confit`_
library.

.. _Confit: http://confit.readthedocs.org/

If you want to access configuration values *outside* of your plugin's section,
import the `config` object from the `beets` module. That is, just put ``from
beets import config`` at the top of your plugin and access values from there.

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

Extend MediaFile
^^^^^^^^^^^^^^^^

`MediaFile`_ is the file tag abstraction layer that beets uses to make
cross-format metadata manipulation simple. Plugins can add fields to MediaFile
to extend the kinds of metadata that they can easily manage.

The ``item_fields`` method on plugins should be overridden to return a
dictionary whose keys are field names and whose values are descriptor objects
that provide the field in question. The descriptors should probably be
``MediaField`` instances (defined in ``beets.mediafile``). Here's an example
plugin that provides a meaningless new field "foo"::

    from beets import mediafile, plugins, ui
    class FooPlugin(plugins.BeetsPlugin):
        def item_fields(self):
            return {
                'foo': mediafile.MediaField(
                    mp3 = mediafile.StorageStyle(
                        'TXXX', id3_desc=u'Foo Field'),
                    mp4 = mediafile.StorageStyle(
                        '----:com.apple.iTunes:Foo Field'),
                    etc = mediafile.StorageStyle('FOO FIELD')
                ),
            }

Later, the plugin can manipulate this new field by saying something like
``mf.foo = 'bar'`` where ``mf`` is a ``MediaFile`` instance.

Note that, currently, these additional fields are *only* applied to
``MediaFile`` itself. The beets library database schema and the ``Item`` class
are not extended, so the fields are second-class citizens. This may change
eventually.

.. _MediaFile: https://github.com/sampsyo/beets/wiki/MediaFile

Add Import Pipeline Stages
^^^^^^^^^^^^^^^^^^^^^^^^^^

Many plugins need to add high-latency operations to the import workflow. For
example, a plugin that fetches lyrics from the Web would, ideally, not block the
progress of the rest of the importer. Beets allows plugins to add stages to the
parallel import pipeline.

Each stage is run in its own thread. Plugin stages run after metadata changes
have been applied to a unit of music (album or track) and before file
manipulation has occurred (copying and moving files, writing tags to disk).
Multiple stages run in parallel but each stage processes only one task at a time
and each task is processed by only one stage at a time.

Plugins provide stages as functions that take two arguments: ``config`` and
``task``, which are ``ImportConfig`` and ``ImportTask`` objects (both defined in
``beets.importer``). Add such a function to the plugin's ``import_stages`` field
to register it::

    from beets.plugins import BeetsPlugin
    class ExamplePlugin(BeetsPlugin):
        def __init__(self):
            super(ExamplePlugin, self).__init__()
            self.import_stages = [self.stage]
        def stage(self, config, task):
            print('Importing something!')
