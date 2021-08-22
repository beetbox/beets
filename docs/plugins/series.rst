Series Plugin
=================

The ``series`` plugin fetches the series metadata from MusicBrainz,
saving into these fields.

- **mb_seriesid**: The MusicBrainz id of the series.
- **series**: The title of the series
- **volume**: The order of the album in the series

Usage
-----
To use the ``series`` plugin, enable it in your configuration
(see :ref:`using-plugins`).

Configuration
-------------

To configure the plugin, make a ``series:`` section in your
configuration file. The available options are:

- **items_per_page**: The maximum number of items per query
  Default: `10`

- **fields**: The mapping between the plugin fields and your tags.
  Each field has these options:

  - **field_name**: The name of your tag.
  - **write**: If you want to write this field in the database.
    Default: `True`

  The configuration keys are `id`, `name` and `volume` for `mb_seriesid`,
  `series` and `volume`.

  Example: You already use the `volume` field for audio loudness,
  so you want to change the tag name to `series_volume`.
  ::
    series:
      fields:
        volume:
          field_name: 'series_volume'

