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

To configure the plugin, make a ``fuzzy:`` section in your configuration
file. The available options are:

- **threshold**: The "sensitivity" of the fuzzy match. A value of 1.0 will
  show only perfect matches and a value of 0.0 will match everything.
  Default: 0.7.
- **prefix**: The character used to designate fuzzy queries.
  Default: ``~``, which may need to be escaped in some shells.
