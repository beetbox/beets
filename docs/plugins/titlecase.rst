Titlecase Plugin
================

The ``titlecase`` plugin lets you format tags and paths in accordance with the
titlecase guidelines in the `New York Times Manual of Style`_ and uses the
`python titlecase library`_.

Motiviation for this plugin comes from a desire to resolve differences in style
between databases sources. For example, `MusicBrainz style`_ follows standard
title case rules, except in the case of terms that are deemed generic, like
"mix" and "remix". On the other hand, `Discogs guidlines`_ recommend
capitalizing the first letter of each word, even for small words like "of" and
"a". This plugin aims to achieve a middleground between disparate approaches to
casing, and bring more consistency to titlecasing in your library.

.. _discogs style: https://support.discogs.com/hc/en-us/articles/360005006334-Database-Guidelines-1-General-Rules#Capitalization_And_Grammar

.. _musicbrainz style: https://musicbrainz.org/doc/Style

.. _new york times manual of style: https://search.worldcat.org/en/title/946964415

.. _python titlecase library: https://pypi.org/project/titlecase/

Installation
------------

To use the ``titlecase`` plugin, first enable it in your configuration (see
:ref:`using-plugins`). Then, install ``beets`` with ``titlecase`` extra:

.. code-block:: bash

    pip install "beets[titlecase]"

If you'd like to just use the path format expression, call ``%titlecase`` in
your path formatter, and set ``auto`` to ``no`` in the configuration.

::

    paths:
      default: %titlecase($albumartist)/$titlecase($albumtitle)/$track $title

You can now configure ``titlecase`` to your preference.

Configuration
-------------

This plugin offers several configuration options to tune its function to your
preference.

Default
~~~~~~~

.. code-block:: yaml

    titlecase:
        auto: yes
        fields:
        preserve:
        force_lowercase: no
        small_first_last: yes

.. conf:: auto
    :default: yes

    Whether to automatically apply titlecase to new imports.

.. conf:: fields

    A list of fields to apply the titlecase logic to. You must specify the fields
    you want to have modified in order for titlecase to apply changes to metadata.

.. conf:: preserve

    List of words and phrases to preserve the case of. Without specifying ``DJ`` on
    the list, titlecase will format it as ``Dj``, or specify ``The Beatles`` to make sure
    ``With The Beatles`` is not capitalized as ``With the Beatles``

.. conf:: force_lowercase
    :default: no

    Force all strings to lowercase before applying titlecase, but can cause
    problems with all caps acronyms titlecase would otherwise recognize.

.. conf:: small_first_last

    An option from the base titlecase library. Controls capitalizing small words at the start
    of a sentence. With this turned off ``a`` and similar words will not be capitalized
    under any circumstance.

Excluded Fields
~~~~~~~~~~~~~~~

``titlecase`` only ever modifies string fields, and will never interact with
fields that it considers to be case sensitive.

For reference, the string fields ``titlecase`` ignores:

.. code-block:: bash

    acoustid_fingerprint
    acoustid_id
    artists_ids
    asin
    deezer_track_id
    format
    id
    isrc
    mb_workid
    mb_trackid
    mb_albumid
    mb_artistid
    mb_artistids
    mb_albumartistid
    mb_albumartistids
    mb_releasetrackid
    mb_releasegroupid
    bitrate_mode
    encoder_info
    encoder_settings

Running Manually
----------------

From the command line, type:

::

    $ beet titlecase [QUERY]

Configuration is drawn from the config file. Without a query the operation will
be applied to the entire collection.
