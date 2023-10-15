Advanced Rewrite Plugin
=======================

The ``advancedrewrite`` plugin lets you easily substitute values
in your templates and path formats, similarly to the :doc:`/plugins/rewrite`.
Please make sure to read the documentation of that plugin first.

The *advanced* rewrite plugin doesn't match the rewritten field itself,
but instead checks if the given item matches a :doc:`query </reference/query>`.
Only then, the field is replaced with the given value.

To use advanced field rewriting, first enable the ``advancedrewrite`` plugin
(see :ref:`using-plugins`).
Then, make a ``advancedrewrite:`` section in your config file to contain
your rewrite rules.

In contrast to the normal ``rewrite`` plugin, you need to provide a list
of replacement rule objects, each consisting of a query, a field name,
and the replacement value.

For example, to credit all songs of ODD EYE CIRCLE before 2023
to their original group name, you can use the following rule::

    advancedrewrite:
      - match: "mb_artistid:dec0f331-cb08-4c8e-9c9f-aeb1f0f6d88c year:..2022"
        field: artist
        replacement: "이달의 소녀 오드아이써클"

As a convenience, the plugin applies patterns for the ``artist`` field to the
``albumartist`` field as well. (Otherwise, you would probably want to duplicate
every rule for ``artist`` and ``albumartist``.)

A word of warning: This plugin theoretically only applies to templates and path
formats; it initially does not modify files' metadata tags or the values
tracked by beets' library database, but since it *rewrites all field lookups*,
it modifies the file's metadata anyway. See comments in issue :bug:`2786`.

As an alternative to this plugin the simpler :doc:`/plugins/rewrite` or
similar :doc:`/plugins/substitute` can be used.
