Bucket Plugin
==============

The ``bucket`` plugin groups your files into buckets folders representing
*ranges*. This kind of organization can classify your music by periods of time
(e.g,. *1960s*, *1970s*, etc.), or to divide overwhelmingly large folders into
smaller subfolders by grouping albums or artists alphabetically (e.g., *A-F*,
*G-M*, *N-Z*).

To use the plugin, enable ``bucket`` in your configuration file (see
:ref:`using-plugins`). The plugin provides a :ref:`template function
<template-functions>` called ``%bucket`` for use in path format expressions::

    paths:
        default: /%bucket{$year}/%bucket{$artist}/$albumartist-$album-$year

Then, define your ranges in the ``bucket:`` section of the config file::

    bucket:
        bucket_alpha: ['A-F', 'G-M', 'N-Z']
        bucket_year:  ['1980s', '1990s', '2000s']

The ``bucket_year`` parameter is used for all substitutions occuring on the
``$year`` field, while ``bucket_alpha`` takes care of textual fields.

The definition of a range is somewhat loose, and multiple formats are allowed:

- For alpha ranges: the range is defined by the lowest and highest (ASCII-wise) alphanumeric characters in the string you provide. For example, *ABCD*, *A-D*, *A->D*, and *[AD]* are all equivalent.
- For year ranges: digits characters are extracted and the two extreme years define the range. For example, *1975-77*, *1975,76,77* and *1975-1977* are equivalent. If no upper bound is given, the range is extended to current year (unless a later range is defined). For example, *1975* encompasses all years from 1975 until now.

If you want to group your files into multiple year ranges, you don't have to
enumerate them all in `bucket_year` parameter but can activate the ``extrapolate``
option instead. This option will generate year bucket names by reproducing characteristics
of declared buckets::

    bucket:
        bucket_year: ['2000-05']
        extrapolate: true

The above configuration creates five-year ranges for any input year.
