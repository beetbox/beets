Fuzzy Search Plugin
===================

The ``fuzzy`` plugin provides a prefixed query that searches your library using
fuzzy pattern matching. This can be useful if you want to find a track with
complicated characters in the title.

First, enable the plugin named ``fuzzy`` (see :ref:`using-plugins`).
You'll then be able to use the ``~`` prefix to use fuzzy matching::

    $ beet ls '~Vareoldur'
    Sigur Rós - Valtari - Varðeldur

Configuration
-------------

Available options:

- ``threshold``: a value of 1.0 will show only perfect matches and a value of
  0.0 will match everything.
  Default: ``0.7``
- ``prefix``: character to use to designate fuzzy queries.
  Default: ``~`` (needs to be escaped or quoted in most shells)
