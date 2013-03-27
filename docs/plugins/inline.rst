Inline Plugin
=============

The ``inline`` plugin lets you use Python to customize your path formats. Using
it, you can define template fields in your beets configuration file and refer
to them from your template strings in the ``[paths]`` section (see
:doc:`/reference/config/`).

To use inline field definitions, first enable the plugin by putting ``inline``
on your ``plugins`` line in your configuration file. Then, make a
``pathfields:`` block in your config file. Under this key, every line defines a
new template field; the key is the name of the field (you'll use the name to
refer to the field in your templates) and the value is a Python expression or
function body. The Python code has all of a track's fields in scope, so you can
refer to any normal attributes (such as ``artist`` or ``title``) as Python
variables.

Here are a couple of examples of expressions::

    pathfields:
        initial: albumartist[0].upper() + u'.'
        disc_and_track: u'%02i.%02i' % (disc, track) if
                        disctotal > 1 else u'%02i' % (track)

Note that YAML syntax allows newlines in values if the subsequent lines are
indented.

These examples define ``$initial`` and ``$disc_and_track`` fields that can be
referenced in path templates like so::

    paths:
        default: $initial/$artist/$album%aunique{}/$disc_and_track $title

If you need to use statements like ``import``, you can write a Python function
body instead of a single expression. In this case, you'll need to ``return``
a result for the value of the path field, like so::

    pathfields:
        filename: |
            import os
            from beets.util import bytestring_path 
            return bytestring_path(os.path.basename(path))

You might want to use the YAML syntax for "block literals," in which a leading
``|`` character indicates a multi-line block of text.
