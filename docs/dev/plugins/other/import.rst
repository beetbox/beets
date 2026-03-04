.. _plugin-stage:

Add Import Pipeline Stages
==========================

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
-----------------------

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
