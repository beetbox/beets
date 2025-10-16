MusicBrainz Pseudo-Release Plugin
=================================

The `mbpseudo` plugin can be used *instead of* the `musicbrainz` plugin to
search for MusicBrainz pseudo-releases_ during the import process, which are
added to the normal candidates from the MusicBrainz search.

.. _pseudo-releases: https://musicbrainz.org/doc/Style/Specific_types_of_releases/Pseudo-Releases

This is useful for releases whose title and track titles are written with a
script_ that can be translated or transliterated into a different one.

.. _script: https://en.wikipedia.org/wiki/ISO_15924

Pseudo-releases will only be included if the initial search in MusicBrainz
returns releases whose script is *not* desired and whose relationships include
pseudo-releases with desired scripts.

Configuration
-------------

Since this plugin first searches for official releases from MusicBrainz, all
options from the `musicbrainz` plugin's :ref:`musicbrainz-config` are supported,
but they must be specified under `mbpseudo` in the configuration file.
Additionally, the configuration expects an array of scripts that are desired for
the pseudo-releases. Therefore, the minimum configuration for this plugin looks
like this:

.. code-block:: yaml

    plugins: mbpseudo # remove musicbrainz

    mbpseudo:
        scripts:
        - Latn

Note that the `search_limit` configuration applies to the initial search for
official releases, and that the `data_source` in the database will be
"MusicBrainz". Nevertheless, `data_source_mismatch_penalty` must also be
specified under `mbpseudo` (see also
:ref:`metadata-source-plugin-configuration`). An example with multiple data
sources may look like this:

.. code-block:: yaml

    plugins: mbpseudo deezer

    mbpseudo:
        data_source_mismatch_penalty: 0
        scripts:
        - Latn

    deezer:
        data_source_mismatch_penalty: 0.2
