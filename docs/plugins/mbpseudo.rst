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
the pseudo-releases. For ``artist`` in particular, keep in mind that even
pseudo-releases might specify it with the original script, so you should also
configure import :ref:`languages` to give artist aliases more priority.
Therefore, the minimum configuration for this plugin looks like this:

.. code-block:: yaml

    plugins: mbpseudo # remove musicbrainz

    import:
        languages: en

    mbpseudo:
        scripts:
        - Latn

A release may have multiple pseudo-releases, for example when there is both a
transliteration and a translation available. By default, only 1 pseudo-release
per official release is emitted as candidate, using the languages from the
configuration to decide which one has most priority. If you're importing in
timid mode and you would like to receive all valid pseudo-releases as additional
candidates, you can add the following to the configuration:

.. code-block:: yaml

    mbpseudo:
        multiple_allowed: yes

.. note::

    Reimporting in particular might not give you a pseudo-release proposal if
    multiple candidates exist and are allowed.

Note that the `search_limit` configuration applies to the initial search for
official releases, and that the `data_source` in the database will be
"MusicBrainz". Nevertheless, `data_source_mismatch_penalty` must also be
specified under `mbpseudo` if desired (see also
:ref:`metadata-source-plugin-configuration`). An example with multiple data
sources may look like this:

.. code-block:: yaml

    plugins: mbpseudo deezer

    import:
        languages: en

    mbpseudo:
        data_source_mismatch_penalty: 0
        scripts:
        - Latn

    deezer:
        data_source_mismatch_penalty: 0.2

Custom Tags Only
----------------

By default, the data from the pseudo-release will be used to create a proposal
that is independent from the official release and sets all properties in its
metadata. It's possible to change the configuration so that some information
from the pseudo-release is instead added as custom tags, keeping the metadata
from the official release:

.. code-block:: yaml

    mbpseudo:
        # other config not shown
        custom_tags_only: yes

The default custom tags with this configuration are specified as mappings where
the keys define the tag names and the values define the pseudo-release property
that will be used to set the tag's value:

.. code-block:: yaml

    mbpseudo:
        album_custom_tags:
            album_transl: album
            album_artist_transl: artist
        track_custom_tags:
            title_transl: title
            artist_transl: artist

Note that the information for each set of custom tags corresponds to different
metadata levels (album or track level), which is why ``artist`` appears twice
even though it effectively references album artist and track artist
respectively.

If you want to modify any mapping under ``album_custom_tags`` or
``track_custom_tags``, you must specify *everything* for that set of tags in
your configuration file because any customization replaces the whole dictionary
of mappings for that level.

.. note::

    These custom tags are also added to the music files, not only to the
    database.
