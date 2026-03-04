Titlecase Plugin
================

The ``titlecase`` plugin lets you format tags and paths in accordance with the
titlecase guidelines in the `New York Times Manual of Style`_ and uses the
`python titlecase library`_.

Motivation for this plugin comes from a desire to resolve differences in style
between databases sources. For example, `MusicBrainz style`_ follows standard
title case rules, except in the case of terms that are deemed generic, like
"mix" and "remix". On the other hand, `Discogs guidelines`_ recommend
capitalizing the first letter of each word, even for small words like "of" and
"a". This plugin aims to achieve a middle ground between disparate approaches to
casing, and bring more consistency to titles in your library.

.. _discogs guidelines: https://support.discogs.com/hc/en-us/articles/360005006334-Database-Guidelines-1-General-Rules#Capitalization_And_Grammar

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
        fields: []
        preserve: []
        replace: []
        separators: []
        force_lowercase: no
        small_first_last: yes
        the_artist: yes
        all_lowercase: no
        all_caps: no
        after_choice: no

.. conf:: auto
    :default: yes

    Whether to automatically apply titlecase to new imports.

.. conf:: fields
    :default: []

     A list of fields to apply the titlecase logic to. You must specify the fields
     you want to have modified in order for titlecase to apply changes to metadata.

     A good starting point is below, which will titlecase album titles, track titles, and all artist fields.

.. code-block:: yaml

    titlecase:
      fields:
        - album
        - title
        - albumartist
        - albumartist_credit
        - albumartist_sort
        - albumartists
        - albumartists_credit
        - albumartists_sort
        - artist
        - artist_credit
        - artist_sort
        - artists
        - artists_credit
        - artists_sort

.. conf:: preserve
    :default: []

     List of words and phrases to preserve the case of. Without specifying ``DJ`` on
     the list, titlecase will format it as ``Dj``, or specify ``The Beatles`` to make sure
     ``With The Beatles`` is not capitalized as ``With the Beatles``.

.. conf:: replace
    :default: []

     The replace function takes place before any titlecasing occurs, and is intended to
     help normalize differences in puncuation styles. It accepts a list of tuples, with
     the first being the target, and the second being the replacement.

     An example configuration that enforces one style of quotation mark is below.

.. code-block:: yaml

    titlecase:
      replace:
        - "’": "'"
        - "‘": "'"
        - "“": '"'
        - "”": '"'

.. conf:: separators
    :default: []

     A list of characters to treat as markers of new sentences. Helpful for split titles
     that might otherwise have a lowercase letter at the start of the second string.

.. conf:: force_lowercase
    :default: no

    Force all strings to lowercase before applying titlecase, but can cause
    problems with all caps acronyms titlecase would otherwise recognize.

.. conf:: small_first_last
    :default: yes

     An option from the base titlecase library. Controls capitalizing small words at the start
     of a sentence. With this turned off ``a`` and similar words will not be capitalized
     under any circumstance.

.. conf:: the_artist
    :default: yes

     If a field name contains ``artist``, then any lowercase ``the`` will be
     capitalized. Useful for bands with ``The`` as part of the proper name,
     like ``Amyl and The Sniffers``.

.. conf:: all_caps
    :default: no

    If the letters a-Z in a string are all caps, do not modify the string. Useful
    if you encounter a lot of acronyms.

.. conf:: all_lowercase
    :default: no

    If the letters a-Z in a string are all lowercase, do not modify the string.
    Useful if you encounter a lot of stylized lowercase spellings, but otherwise
    want titlecase applied.

.. conf:: after_choice
    :default: no

     By default, titlecase runs on the candidates that are received, adjusting them before
     you make your selection and creating different weight calculations. If you'd rather
     see the data as recieved from the database, set this to true to run after you make
     your tag choice.

Dangerous Fields
~~~~~~~~~~~~~~~~

``titlecase`` only ever modifies string fields, however, this doesn't prevent
you from selecting a case sensitive field that another plugin or feature may
rely on.

In particular, including any of the following in your configuration could lead
to unintended behavior:

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
