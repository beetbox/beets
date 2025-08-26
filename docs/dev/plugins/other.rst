Further Reading
===============

.. contents:: Table of Contents
    :local:
    :depth: 2

Read Configuration Options
--------------------------

Plugins can configure themselves using the ``config.yaml`` file. You can read
configuration values in two ways. The first is to use `self.config` within your
plugin class. This gives you a view onto the configuration values in a section
with the same name as your plugin's module. For example, if your plugin is in
``greatplugin.py``, then `self.config` will refer to options under the
``greatplugin:`` section of the config file.

For example, if you have a configuration value called "foo", then users can put
this in their ``config.yaml``:

::

    greatplugin:
        foo: bar

To access this value, say ``self.config['foo'].get()`` at any point in your
plugin's code. The `self.config` object is a *view* as defined by the Confuse_
library.

.. _confuse: https://confuse.readthedocs.io/en/latest/

If you want to access configuration values *outside* of your plugin's section,
import the `config` object from the `beets` module. That is, just put ``from
beets import config`` at the top of your plugin and access values from there.

If your plugin provides configuration values for sensitive data (e.g.,
passwords, API keys, ...), you should add these to the config so they can be
redacted automatically when users dump their config. This can be done by setting
each value's `redact` flag, like so:

::

    self.config['password'].redact = True

Add Path Format Functions and Fields
------------------------------------

Beets supports *function calls* in its path format syntax (see
:doc:`/reference/pathformat`). Beets includes a few built-in functions, but
plugins can register new functions by adding them to the ``template_funcs``
dictionary.

Here's an example:

.. code-block:: python

    class MyPlugin(BeetsPlugin):
        def __init__(self):
            super().__init__()
            self.template_funcs["initial"] = _tmpl_initial


    def _tmpl_initial(text: str) -> str:
        if text:
            return text[0].upper()
        else:
            return ""

This plugin provides a function ``%initial`` to path templates where
``%initial{$artist}`` expands to the artist's initial (its capitalized first
character).

Plugins can also add template *fields*, which are computed values referenced as
``$name`` in templates. To add a new field, add a function that takes an
``Item`` object to the ``template_fields`` dictionary on the plugin object.
Here's an example that adds a ``$disc_and_track`` field:

.. code-block:: python

    class MyPlugin(BeetsPlugin):
        def __init__(self):
            super().__init__()
            self.template_fields["disc_and_track"] = _tmpl_disc_and_track


    def _tmpl_disc_and_track(item: Item) -> str:
        """Expand to the disc number and track number if this is a
        multi-disc release. Otherwise, just expands to the track
        number.
        """
        if item.disctotal > 1:
            return f"{item.disc:02d}.{item.track:02d}"
        else:
            return f"{item.track:02d}"

With this plugin enabled, templates can reference ``$disc_and_track`` as they
can any standard metadata field.

This field works for *item* templates. Similarly, you can register *album*
template fields by adding a function accepting an ``Album`` argument to the
``album_template_fields`` dict.

Extend MediaFile
----------------

MediaFile_ is the file tag abstraction layer that beets uses to make
cross-format metadata manipulation simple. Plugins can add fields to MediaFile
to extend the kinds of metadata that they can easily manage.

The ``MediaFile`` class uses ``MediaField`` descriptors to provide access to
file tags. If you have created a descriptor you can add it through your plugins
:py:meth:`beets.plugins.BeetsPlugin.add_media_field` method.

.. _mediafile: https://mediafile.readthedocs.io/en/latest/

Here's an example plugin that provides a meaningless new field "foo":

.. code-block:: python

    class FooPlugin(BeetsPlugin):
        def __init__(self):
            field = mediafile.MediaField(
                mediafile.MP3DescStorageStyle("foo"), mediafile.StorageStyle("foo")
            )
            self.add_media_field("foo", field)


    FooPlugin()
    item = Item.from_path("/path/to/foo/tag.mp3")
    assert item["foo"] == "spam"

    item["foo"] == "ham"
    item.write()
    # The "foo" tag of the file is now "ham"

.. _plugin-stage:

Add Import Pipeline Stages
--------------------------

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
``task``, which are ``ImportSession`` and ``ImportTask`` objects (both defined
in ``beets.importer``). Add such a function to the plugin's ``import_stages``
field to register it:

.. code-block:: python

    from beets.importer import ImportSession, ImportTask
    from beets.plugins import BeetsPlugin


    class ExamplePlugin(BeetsPlugin):

        def __init__(self):
            super().__init__()
            self.import_stages = [self.stage]

        def stage(self, session: ImportSession, task: ImportTask):
            print("Importing something!")

It is also possible to request your function to run early in the pipeline by
adding the function to the plugin's ``early_import_stages`` field instead:

.. code-block:: python

    self.early_import_stages = [self.stage]

.. _extend-query:

Extend the Query Syntax
~~~~~~~~~~~~~~~~~~~~~~~

You can add new kinds of queries to beets' :doc:`query syntax
</reference/query>`. There are two ways to add custom queries: using a prefix
and using a name. Prefix-based query extension can apply to *any* field, while
named queries are not associated with any field. For example, beets already
supports regular expression queries, which are indicated by a colon
prefix---plugins can do the same.

For either kind of query extension, define a subclass of the ``Query`` type from
the ``beets.dbcore.query`` module. Then:

- To define a prefix-based query, define a ``queries`` method in your plugin
  class. Return from this method a dictionary mapping prefix strings to query
  classes.
- To define a named query, defined dictionaries named either ``item_queries`` or
  ``album_queries``. These should map names to query types. So if you use ``{
  "foo": FooQuery }``, then the query ``foo:bar`` will construct a query like
  ``FooQuery("bar")``.

For prefix-based queries, you will want to extend ``FieldQuery``, which
implements string comparisons on fields. To use it, create a subclass inheriting
from that class and override the ``value_match`` class method. (Remember the
``@classmethod`` decorator!) The following example plugin declares a query using
the ``@`` prefix to delimit exact string matches. The plugin will be used if we
issue a command like ``beet ls @something`` or ``beet ls artist:@something``:

.. code-block:: python

    from beets.plugins import BeetsPlugin
    from beets.dbcore import FieldQuery


    class ExactMatchQuery(FieldQuery):
        @classmethod
        def value_match(self, pattern, val):
            return pattern == val


    class ExactMatchPlugin(BeetsPlugin):
        def queries(self):
            return {"@": ExactMatchQuery}

Flexible Field Types
--------------------

If your plugin uses flexible fields to store numbers or other non-string values,
you can specify the types of those fields. A rating plugin, for example, might
want to declare that the ``rating`` field should have an integer type:

.. code-block:: python

    from beets.plugins import BeetsPlugin
    from beets.dbcore import types


    class RatingPlugin(BeetsPlugin):
        item_types = {"rating": types.INTEGER}

        @property
        def album_types(self):
            return {"rating": types.INTEGER}

A plugin may define two attributes: ``item_types`` and ``album_types``. Each of
those attributes is a dictionary mapping a flexible field name to a type
instance. You can find the built-in types in the ``beets.dbcore.types`` and
``beets.library`` modules or implement your own type by inheriting from the
``Type`` class.

Specifying types has several advantages:

- Code that accesses the field like ``item['my_field']`` gets the right type
  (instead of just a string).
- You can use advanced queries (like :ref:`ranges <numericquery>`) from the
  command line.
- User input for flexible fields may be validated and converted.
- Items missing the given field can use an appropriate null value for querying
  and sorting purposes.

.. _plugin-logging:

Logging
-------

Each plugin object has a ``_log`` attribute, which is a ``Logger`` from the
`standard Python logging module`_. The logger is set up to `PEP 3101`_,
str.format-style string formatting. So you can write logging calls like this:

.. code-block:: python

    self._log.debug("Processing {0.title} by {0.artist}", item)

.. _pep 3101: https://www.python.org/dev/peps/pep-3101/

.. _standard python logging module: https://docs.python.org/2/library/logging.html

When beets is in verbose mode, plugin messages are prefixed with the plugin name
to make them easier to see.

Which messages will be logged depends on the logging level and the action
performed:

- Inside import stages and event handlers, the default is ``WARNING`` messages
  and above.
- Everywhere else, the default is ``INFO`` or above.

The verbosity can be increased with ``--verbose`` (``-v``) flags: each flags
lowers the level by a notch. That means that, with a single ``-v`` flag, event
handlers won't have their ``DEBUG`` messages displayed, but command functions
(for example) will. With ``-vv`` on the command line, ``DEBUG`` messages will be
displayed everywhere.

This addresses a common pattern where plugins need to use the same code for a
command and an import stage, but the command needs to print more messages than
the import stage. (For example, you'll want to log "found lyrics for this song"
when you're run explicitly as a command, but you don't want to noisily interrupt
the importer interface when running automatically.)

.. _append_prompt_choices:

Append Prompt Choices
---------------------

Plugins can also append choices to the prompt presented to the user during an
import session.

To do so, add a listener for the ``before_choose_candidate`` event, and return a
list of ``PromptChoices`` that represent the additional choices that your plugin
shall expose to the user:

.. code-block:: python

    from beets.plugins import BeetsPlugin
    from beets.ui.commands import PromptChoice


    class ExamplePlugin(BeetsPlugin):
        def __init__(self):
            super().__init__()
            self.register_listener(
                "before_choose_candidate", self.before_choose_candidate_event
            )

        def before_choose_candidate_event(self, session, task):
            return [
                PromptChoice("p", "Print foo", self.foo),
                PromptChoice("d", "Do bar", self.bar),
            ]

        def foo(self, session, task):
            print('User has chosen "Print foo"!')

        def bar(self, session, task):
            print('User has chosen "Do bar"!')

The previous example modifies the standard prompt:

.. code-block:: shell

    # selection (default 1), Skip, Use as-is, as Tracks, Group albums,
    Enter search, enter Id, aBort?

by appending two additional options (``Print foo`` and ``Do bar``):

.. code-block:: shell

    # selection (default 1), Skip, Use as-is, as Tracks, Group albums,
    Enter search, enter Id, aBort, Print foo, Do bar?

If the user selects a choice, the ``callback`` attribute of the corresponding
``PromptChoice`` will be called. It is the responsibility of the plugin to check
for the status of the import session and decide the choices to be appended: for
example, if a particular choice should only be presented if the album has no
candidates, the relevant checks against ``task.candidates`` should be performed
inside the plugin's ``before_choose_candidate_event`` accordingly.

Please make sure that the short letter for each of the choices provided by the
plugin is not already in use: the importer will emit a warning and discard all
but one of the choices using the same letter, giving priority to the core
importer prompt choices. As a reference, the following characters are used by
the choices on the core importer prompt, and hence should not be used: ``a``,
``s``, ``u``, ``t``, ``g``, ``e``, ``i``, ``b``.

Additionally, the callback function can optionally specify the next action to be
performed by returning a ``importer.Action`` value. It may also return a
``autotag.Proposal`` value to update the set of current proposals to be
considered.
