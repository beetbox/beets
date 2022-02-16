Fish Plugin
===========

The ``fish`` plugin adds a ``beet fish`` command that creates a `Fish shell`_
tab-completion file named ``beet.fish`` in ``~/.config/fish/completions``.
This enables tab-completion of ``beet`` commands for the `Fish shell`_.

.. _Fish shell: https://fishshell.com/

Configuration
-------------

Enable the ``fish`` plugin (see :ref:`using-plugins`) on a system running the
`Fish shell`_.

Usage
-----

Type ``beet fish`` to generate the ``beet.fish`` completions file at:
``~/.config/fish/completions/``. If you later install or disable plugins, run
``beet fish`` again to update the completions based on the enabled plugins.

For users not accustomed to tab completion… After you type ``beet`` followed by
a space in your shell prompt and then the ``TAB`` key, you should see a list of
the beets commands (and their abbreviated versions) that can be invoked in your
current environment. Similarly, typing ``beet -<TAB>`` will show you all the
option flags available to you, which also applies to subcommands such as
``beet import -<TAB>``. If you type ``beet ls`` followed by a space and then the
and the ``TAB`` key, you will see a list of all the album/track fields that can
be used in beets queries. For example, typing ``beet ls ge<TAB>`` will complete
to ``genre:`` and leave you ready to type the rest of your query.

Options
-------

In addition to beets commands, plugin commands, and option flags, the generated
completions also include by default all the album/track fields. If you only want
the former and do not want the album/track fields included in the generated
completions, use ``beet fish -f`` to only generate completions for beets/plugin
commands and option flags.

If you want generated completions to also contain album/track field *values* for
the items in your library, you can use the ``-e`` or ``--extravalues`` option.
For example: ``beet fish -e genre`` or ``beet fish -e genre -e albumartist``
In the latter case, subsequently typing ``beet list genre: <TAB>`` will display
a list of all the genres in your library and ``beet list albumartist: <TAB>``
will show a list of the album artists in your library. Keep in mind that all of
these values will be put into the generated completions file, so use this option
with care when specified fields contain a large number of values. Libraries with,
for example, very large numbers of genres/artists may result in higher memory
utilization, completion latency, et cetera. This option is not meant to replace
database queries altogether.

By default, the completion file will be generated at
``~/.config/fish/completions/``.
If you want to save it somewhere else, you can use the ``-o`` or ``--output``
option.
