Fuzzy Search Plugin
===================

The ``fuzzy`` plugin provides a query prefix that search you library using fuzzy
pattern matching. This can be useful if you want to find a track with
complicated characters in the title.

First, enable the plugin named ``fuzzy`` (see :doc:`/plugins/index`).
You'll then be able to use the ``~`` prefix to use fuzzy matching::

    $ beet ls '~Vareoldur'
    Sigur Rós - Valtari - Varðeldur

The plugin provides to config option to let you choose the prefix and the
threshold.::

    fuzzy:
        threshold: 0.8
        prefix: '@'

A threshold value of ``1`` will show only perfect matches and a value of ``0``
will match everything.

The default prefix ``~`` needs to be escaped or quoted in most shells. If this
bothers you, you can change the prefix in your config file.
