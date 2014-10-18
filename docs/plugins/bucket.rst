Bucket Plugin
==============

The ``bucket`` plugin groups your files into buckets folders representing
*ranges*. This kind of organization can classify your music by periods of time
(e.g,. *1960s*, *1970s*, etc.), or divide overwhelmingly large folders into
smaller subfolders by grouping albums or artists alphabetically (e.g. *A-F*,
*G-M*, *N-Z*).

To use the plugin, first enable it in your configuration (see
:ref:`using-plugins`).
The plugin provides a :ref:`template function
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

Configuration
-------------

Available options :

- ``bucket_alpha`` defines ranges to use for all substitutions occuring on
textual fields
- ``bucket_alpha_regex`` allows to define a regex to override a `bucket_alpha`
range definition
- ``bucket_year`` defines ranges to use for all substitutions occuring on the `$year` field
- ``extrapolate`` : activate it when you want to group your files into multiple
year ranges without enumerating them all. This option will generate year bucket
names by reproducing characteristics of declared buckets::

Here's an example::

      bucket:
         bucket_year: ['2000-05']
         extrapolate: true
         bucket_alpha: ['A - D', 'E - L', 'M - R', 'S - Z']
         bucket_alpha_regex:
           'A - D': ^[0-9a-dA-D‚Ä¶√§√Ñ]

The above configuration creates five-year ranges for any input year.
The *A - D* bucket now matches also all artists starting with √§ or √Ñ and 0 to 9 and ‚Ä¶ (three dots). The other alpha buckets work as ranges.
