Inline Plugin
=============

The ``inline`` plugin lets you use Python expressions to customize your path
formats. Using it, you can define template fields in your beets configuration
file and refer to them from your template strings in the ``[paths]`` section
(see :doc:`/reference/config/`).

To use inline field definitions, first enable the plugin by putting ``inline``
on your ``plugins`` line, like so::

    [beets]
    plugins: inline

Then, make a ``[pathfields]`` section in your config file. In this section,
every line defines a new template field; the key is the name of the field
(you'll use the name to refer to the field in your templates) and the value is a
Python expression. The expression has all of a track's items in scope, so you
can refer to any normal attributes (such as ``artist`` or ``title``) as Python
variables. Here are a couple of examples::

    [pathfields]
    artist_initial: artist[0].upper() + u'.'
    disc_and_track: u'%02i.%02i' % (disc, track) if
                    disctotal > 1 else u'%02i' % (track)

(Note that the config file's syntax allows newlines in values if the subsequent
lines are indented.) These examples define ``$artist_initial`` and
``$disc_and_track`` fields that can be referenced in path templates like so::

    [paths]
    default: $artist_initial/$artist/$album/$disc_and_track $title
