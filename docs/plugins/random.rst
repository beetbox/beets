Random Plugin
=============

The ``random`` plugin provides a command that randomly selects tracks or albums
from your library. This can be helpful if you need some help deciding what to
listen to.

First, enable the plugin named ``random`` (see :ref:`using-plugins`). You'll
then be able to use the ``beet random`` command::

    $ beet random
    Aesop Rock - None Shall Pass - The Harbor Is Yours

The command has several options that resemble those for the ``beet list``
command (see :doc:`/reference/cli`). To choose an album instead of a single
track, use ``-a``; to print paths to items instead of metadata, use ``-p``; and
to use a custom format for printing, use ``-f FORMAT``.

If the ``-e`` option is passed, the random choice will be even among
artists (the albumartist field). This makes sure that your anthology
of Bob Dylan won't make you listen to Bob Dylan 50% of the time.

The ``-n NUMBER`` option controls the number of objects that are selected and
printed (default 1). To select 5 tracks from your library, type ``beet random
-n5``.

As an alternative, you can use ``-t MINUTES`` to choose a set of music with a
given play time. To select tracks that total one hour, for example, type
``beet random -t60``.
