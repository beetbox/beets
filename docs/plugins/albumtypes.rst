AlbumTypes Plugin
=================

The ``albumtypes`` plugin adds the ability to format and output album types,
such as "Album", "EP", "Single", etc. List of available type can be found
`here`_.

To use the ``albumtypes`` plugin, enable it in your configuration
(see :ref:`using-plugins`). Then, add ``$atypes`` to your path formats as
desired.

.. _here: https://musicbrainz.org/doc/Release_Group/Type

Configuration
-------------

To configure the plugin, make a ``albumtypes:`` section in your configuration
file. The available options are:

- **types**: An ordered list of album type to format mappings. The order of the
  mappings determines their order in the output. If a mapping is missing or
  blank, it will not be in the output.
  Default: ``[]``.
- **ignore_va**: A list of types that should not be output for Various Artists
  albums. Useful for not adding redundant information - various artist albums
  are often compilations.
  Default: ``[]``.
- **bracket**: Defines the brackets to enclose each album type in the output.
  Default: ``'[]'``

Examples
--------
Example config::

    albumtypes:
        types:
            - ep: 'EP'
            - single: 'Single'
            - soundtrack: 'OST'
            - live: 'Live'
            - compilation: 'Anthology'
            - remix: 'Remix'
        ignore_va: compilation
        bracket: '()'

    paths:
        default: $albumartist/($year)$atypes $album/...
        albumtype:soundtrack Various Artists/$album ($year)$atypes)/...
        comp: Various Artists/$album ($year)$atypes/...

Example outputs::

    Aphex Twin/(1993)(EP)(Remix) On Remixes
    Pink Flow/(1995)(Live) p·u·l·s·e
    Various Artists/20th Century Lullabies (1999)
    Various Artists/Ocean's Eleven (2001)(OST)

