Fuzzy Search Plugin
=============

The ``fuzzy_search`` plugin provides a command that search your library using
fuzzy pattern matching. This can be useful if you want to find a track with complicated characters in the title.

First, enable the plugin named ``fuzzy_search`` (see :doc:`/plugins/index`).
You'll then be able to use the ``beet fuzzy`` command::

    $ beet fuzzy Vareoldur
    Sigur Rós - Valtari - Varðeldur

The command has several options that resemble those for the ``beet list``
command (see :doc:`/reference/cli`). To choose an album instead of a single
track, use ``-a``; to print paths to items instead of metadata, use ``-p``; and
to use a custom format for printing, use ``-f FORMAT``.

The ``-t NUMBER`` option lets you specify how precise the fuzzy match has to be
(default is 0.7). To make a fuzzier search, try ``beet fuzzy -t 0.5 Varoeldur``.
A value of ``1`` will show only perfect matches and a value of ``0`` will match everything.
