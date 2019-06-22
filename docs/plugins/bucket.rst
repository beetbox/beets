Bucket Plugin
=============

The ``bucket`` plugin groups your files into buckets folders representing
*ranges*. This kind of organization can classify your music by periods of time
(e.g,. *1960s*, *1970s*, etc.), or divide overwhelmingly large folders into
smaller subfolders by grouping albums or artists alphabetically (e.g. *A-F*,
*G-M*, *N-Z*).

To use the ``bucket`` plugin, first enable it in your configuration (see
:ref:`using-plugins`).
The plugin provides a :ref:`template function
<template-functions>` called ``%bucket`` for use in path format expressions::

    paths:
        default: /%bucket{$year}/%bucket{$artist}/$albumartist-$album-$year

Then, define your ranges in the ``bucket:`` section of the config file::

    bucket:
        bucket_alpha: ['A-F', 'G-M', 'N-Z']
        bucket_year:  ['1980s', '1990s', '2000s']

The ``bucket_year`` parameter is used for all substitutions occurring on the
``$year`` field, while ``bucket_alpha`` takes care of textual fields.

The definition of a range is somewhat loose, and multiple formats are allowed:

- For alpha ranges: the range is defined by the lowest and highest (ASCII-wise)
  alphanumeric characters in the string you provide. For example, ``ABCD``,
  ``A-D``, ``A->D``, and ``[AD]`` are all equivalent.
- For year ranges: digits characters are extracted and the two extreme years
  define the range. For example, ``1975-77``, ``1975,76,77`` and ``1975-1977`` are
  equivalent. If no upper bound is given, the range is extended to current year
  (unless a later range is defined). For example, ``1975`` encompasses all years
  from 1975 until now.

The ``%bucket`` template function guesses whether to use alpha- or year-style
buckets depending on the text it receives. It can guess wrong if, for example,
an artist or album happens to begin with four digits. Provide ``alpha`` as the
second argument to the template to avoid this automatic detection: for
example, use ``%bucket{$artist,alpha}``.


Configuration
-------------

To configure the plugin, make a ``bucket:`` section in your configuration file.
The available options are:

- **bucket_alpha**: Ranges to use for all substitutions occurring on textual
  fields.
  Default: none.
- **bucket_alpha_regex**: A ``range: regex`` mapping (one per line) where
  ``range`` is one of the `bucket_alpha` ranges and ``value`` is  a regex that
  overrides original range definition.
  Default: none.
- **bucket_year**: Ranges to use for all substitutions occurring on the
  ``$year`` field.
  Default: none.
- **extrapolate**: Enable this if you want to group your files into multiple
  year ranges without enumerating them all. This option will generate year
  bucket names by reproducing characteristics of declared buckets.
  Default: ``no``

Here's an example::

      bucket:
         bucket_year: ['2000-05']
         extrapolate: true
         bucket_alpha: ['A - D', 'E - L', 'M - R', 'S - Z']
         bucket_alpha_regex:
           'A - D': ^[0-9a-dA-D…äÄ]

This configuration creates five-year ranges for any input year.
The `A - D` bucket now matches also all artists starting with ä or Ä and 0 to 9
and … (ellipsis). The other alpha buckets work as ranges.
