Titlecase Plugin
================

The ``titlecase`` plugin lets you format tags and paths in accordance
with the titlecase guidelines in the `New York Times Manual of Style`_
and uses the `python titlecase library`_.

Motiviation for this plugin comes from a desire to resolve differences
in style between databases sources. For example, `MusicBrainz style`_ 
follows standard title case rules, except in the case of terms that are
deemed generic, like "mix" and "remix". On the other hand, `Discogs guidlines`_
recommend capitalizing the first letter of each word, even for small words
like "of" and "a". This plugin aims to achieve a middleground between
disparate approaches to casing, and bring more consistency to titlecasing
in your library.

.. _new york times manual of style: https://search.worldcat.org/en/title/946964415

.. _python titlecase library: https://pypi.org/project/titlecase/

.. _musicbrainz style: https://musicbrainz.org/doc/Style

.. _discogs style: https://support.discogs.com/hc/en-us/articles/360005006334-Database-Guidelines-1-General-Rules#Capitalization_And_Grammar

Installation
------------

To use the ``titlecase`` plugin, first enable it in your configuration (see
:ref:`using-plugins`). Then, install ``beets`` with ``titlecase`` extra:

.. code-block:: bash

    pip install "beets[titlecase]"

You can now configure ``titlecase`` to your preference.

Configuration
-------------

This plugin offers several configuration options
to tune its function to your preference.

Default
~~~~~~~

.. code-block:: yaml

    titlecase:
        auto: yes
        preserve: None
        include: ALL
        exclude: 
        force_lowercase: yes
        small_first_last: yes

- **auto**: Whether to automatically apply titlecase to new imports. Default: ``yes``

- **preserve**: Space seperated list of words and acronyms to preserve the case of.
  For example, without specifying ``DJ`` on the list, titlecase will format it as ``Dj``.

- **include**: Space seperated list of fields to titlecase.
  When filled out, only the fields specified will be touched by the plugin. 
  Default: ``ALL``

- **exclude**: Space seperated list of fields to exclude from processing.
  If a field is listed in include, and is listed in exclude, exclude takes
  precedence.

- **force_lowercase**: Force all strings to lowercase before applying titlecase.
  This helps fix ``uNuSuAl CaPiTaLiZaTiOn PaTtErNs``. Default: ``yes``

- **small_first_last**: An option from the base titlecase library. Controls if
  capitalize small words at the start of a sentence. With this turned off ``a``  and 
  similar words will not be capitalized under any circumstance. Default: ``yes``

Excluded Fields
~~~~~~~~~~~~~~~

``titlecase`` only ever modifies string fields, and will never
interact with fields that are considered to be case sensitive.

For reference, the string fields ``titlecase`` ignores:

.. code-block:: bash

        id
        mb_workid
        mb_trackid
        mb_albumid
        mb_artistid
        mb_albumartistid
        mb_albumartistids
        mb_releasetrackid
        acoustid_fingerprint
        acoustid_id
        mb_releasegroupid
        asin
        isrc
        format
        bitrate_mode
        encoder_info
        encoder_settings

Running Manually
----------------

From the command line, type:

::

    $ beet titlecase [QUERY]

You can specify additional configuration options with the following flags:

