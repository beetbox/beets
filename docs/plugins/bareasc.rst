Bare-ASCII Search Plugin
========================

The ``bareasc`` plugin provides a prefixed query that searches your library using
simple ASCII character matching, with accented characters folded to their base
ASCII character. This can be useful if you want to find a track with accented
characters in the title or artist, particularly if you are not confident
you have the accents correct. It is also not unknown for the accents
to not be correct in the database entry or wrong in the CD information.

First, enable the plugin named ``bareasc`` (see :ref:`using-plugins`).
You'll then be able to use the ``#`` prefix to use bare-ASCII matching::

    $ beet ls '#dvorak'
    István Kertész - REQUIEM - Dvořàk: Requiem, op.89 - Confutatis maledictis

Command
-------

In addition to the query prefix, the plugin provides a utility ``bareasc`` command.
This command is **exactly** the same as the ``beet list`` command except that
the output is passed through the bare-ASCII transformation before being printed.
This allows you to easily check what the library data looks like in bare ASCII,
which can be useful if you are trying to work out why a query is not matching.

Using the same example track as above::

    $ beet bareasc 'Dvořàk'
    Istvan Kertesz - REQUIEM - Dvorak: Requiem, op.89 - Confutatis maledictis

Note: the ``bareasc`` command does *not* automatically use bare-ASCII queries.
If you want a bare-ASCII query you still need to specify the ``#`` prefix.

Notes
-----

If the query string is all in lower case, the comparison ignores case as well as
accents.

The default ``bareasc`` prefix (``#``) is used as a comment character in some shells
so may need to be protected (for example in quotes) when typed into the command line.

The bare ASCII transliteration is quite simple. It may not give the expected output
for all languages. For example, German u-umlaut ``ü`` is transformed into ASCII ``u``,
not into ``ue``.

The bare ASCII transformation also changes Unicode punctuation like double quotes,
apostrophes and even some hyphens. It is often best to leave out punctuation
in the queries. Note that the punctuation changes are often not even visible
with normal terminal fonts. You can always use the ``bareasc`` command to print the
transformed entries and use a command like ``diff`` to compare with the output
from the ``list`` command.

Configuration
-------------

To configure the plugin, make a ``bareasc:`` section in your configuration
file. The only available option is:

- **prefix**: The character used to designate bare-ASCII queries.
  Default: ``#``, which may need to be escaped in some shells.

Credits
-------

The hard work in this plugin is done in Sean Burke's
`Unidecode <https://pypi.org/project/Unidecode/>`__ library.
Thanks are due to Sean and to all the people who created the Python
version and the beets extensible query architecture.
