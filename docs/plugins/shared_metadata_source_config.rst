.. _data_source_mismatch_penalty:

.. conf:: data_source_mismatch_penalty
    :default: 0.5

    Penalty applied when the data source of a
    match candidate differs from the original source of your existing tracks. Any
    decimal number between 0.0 and 1.0

    This setting controls how much to penalize matches from different metadata
    sources during import. The penalty is applied when beets detects that a match
    candidate comes from a different data source than what appears to be the
    original source of your music collection.

    **Example configurations:**

    .. code-block:: yaml

        # Prefer MusicBrainz over Discogs when sources don't match
        plugins: musicbrainz discogs

        musicbrainz:
            data_source_mismatch_penalty: 0.3  # Lower penalty = preferred
        discogs:
            data_source_mismatch_penalty: 0.8  # Higher penalty = less preferred

    .. code-block:: yaml

        # Do not penalise candidates from Discogs at all
        plugins: musicbrainz discogs

        musicbrainz:
            data_source_mismatch_penalty: 0.5
        discogs:
            data_source_mismatch_penalty: 0.0

    .. code-block:: yaml

        # Disable cross-source penalties entirely
        plugins: musicbrainz discogs

        musicbrainz:
            data_source_mismatch_penalty: 0.0
        discogs:
            data_source_mismatch_penalty: 0.0

    .. tip::

        The last configuration is equivalent to setting:

        .. code-block:: yaml

            match:
                distance_weights:
                    data_source: 0.0  # Disable data source matching

.. conf:: source_weight
    :default: 0.5

    .. deprecated:: 2.5 Use `data_source_mismatch_penalty`_ instead.

.. conf:: search_limit
    :default: 5

    Maximum number of search results to return.
