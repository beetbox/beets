Random Plugin
=============

The ``rdm`` plugin provides a command that randomly selects tracks or albums
from your library. This can be helpful if you need some help deciding what to
listen to.

First, enable the plugin named ``rdm`` (see :doc:`/plugins/index`). You'll then
be able to use the ``beet random`` command::

    $ beet random
    Aesop Rock - None Shall Pass - The Harbor Is Yours

The command has several options that resemble those for the ``beet list``
command (see :doc:`/reference/cli`). To choose an album instead of a single
track, use ``-a``; to print paths to items instead of metadata, use ``-p``; and
to use a custom format for printing, use ``-f FORMAT``.
