Advanced Rewrite Plugin
=======================

The ``advancedrewrite`` plugin lets you easily substitute values in your
templates and path formats, similarly to the :doc:`/plugins/rewrite`. It's
recommended to read the documentation of that plugin first.

The *advanced* rewrite plugin does not only support the simple rule format of
the ``rewrite`` plugin, but also an advanced format: there, the plugin doesn't
consider the value of the rewritten field, but instead checks if the given item
matches a :doc:`query </reference/query>`. Only then, the field is replaced with
the given value. It's also possible to replace multiple fields at once, and even
supports multi-valued fields.

To use advanced field rewriting, first enable the ``advancedrewrite`` plugin
(see :ref:`using-plugins`). Then, make a ``advancedrewrite:`` section in your
config file to contain your rewrite rules.

In contrast to the normal ``rewrite`` plugin, you need to provide a list of
replacement rule objects, which can have a different syntax depending on the
rule complexity.

The simple syntax is the same as the one of the rewrite plugin and allows to
replace a single field:

::

    advancedrewrite:
      - artist ODD EYE CIRCLE: 이달의 소녀 오드아이써클

The advanced syntax consists of a query to match against, as well as a map of
replacements to apply. For example, to credit all songs of ODD EYE CIRCLE before
2023 to their original group name, you can use the following rule:

::

    advancedrewrite:
      - match: "mb_artistid:dec0f331-cb08-4c8e-9c9f-aeb1f0f6d88c year:..2022"
        replacements:
          artist: 이달의 소녀 오드아이써클
          artist_sort: LOONA / ODD EYE CIRCLE

Note how the sort name is also rewritten within the same rule. You can specify
as many fields as you'd like in the replacements map.

If you need to work with multi-valued fields, you can use the following syntax:

::

    advancedrewrite:
      - match: "artist:배유빈 feat. 김미현"
        replacements:
          artists:
            - 유빈
            - 미미

As a convenience, the plugin applies patterns for the ``artist`` field to the
``albumartist`` field as well. (Otherwise, you would probably want to duplicate
every rule for ``artist`` and ``albumartist``.)

Make sure to properly quote your query strings if they contain spaces, otherwise
they might not do what you expect, or even cause beets to crash.

Take the following example:

::

    advancedrewrite:
      # BAD, DON'T DO THIS!
      - match: album:THE ALBUM
        replacements:
          artist: New artist

On the first sight, this might look sane, and replace the artist of the album
*THE ALBUM* with *New artist*. However, due to the space and missing quotes,
this query will evaluate to ``album:THE`` and match ``ALBUM`` on any field,
including ``artist``. As ``artist`` is the field being replaced, this query will
result in infinite recursion and ultimately crash beets.

Instead, you should use the following rule:

::

    advancedrewrite:
      # Note the quotes around the query string!
      - match: album:"THE ALBUM"
        replacements:
          artist: New artist

A word of warning: This plugin theoretically only applies to templates and path
formats; it initially does not modify files' metadata tags or the values tracked
by beets' library database, but since it *rewrites all field lookups*, it
modifies the file's metadata anyway. See comments in issue :bug:`2786`.

As an alternative to this plugin the simpler but less powerful
:doc:`/plugins/rewrite` can be used. If you don't want to modify the item's
metadata and only replace values in file paths, you can check out the
:doc:`/plugins/substitute`.
