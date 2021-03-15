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

Notes
-----

If the query string is all in lower case, the comparison ignores case as well as
accents.

The default ``bareasc`` prefix (``#``) is used as a comment character in some shells
so may need to be protected (for example in quotes) when typed into the command line.

The bare ASCII transformation is quite simple. It may not work perfectly for all
languages and does not handle transformations which change the number of letters.
For example, German u-umlaut ``ü`` is transformed into ASCII ``u``, not into ``ue``.

Configuration
-------------

To configure the plugin, make a ``bareasc:`` section in your configuration
file. The only available option is:

- **prefix**: The character used to designate bare-ASCII queries.
  Default: ``#``, which may need to be escaped in some shells.

Credits
-------

The hard work in this plugin is done in Sean Burke's Unidecode library.
Thanks are due to Sean and to all the people who created the Python
version and the beets extensible query architecture.
