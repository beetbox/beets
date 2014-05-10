Bucket Plugin
==============

The ``bucket`` plugin helps you keep a balanced files tree for your library
by grouping your files into buckets folders representing ranges.
This kind of files organization is usually used to classify your music by
periods (eg *1960s*, *1970s* etc), or to divide bloated folders into smaller
subfolders by grouping albums/artists alphabetically (eg *A-F*, *G-M*, *N-Z*).
To use this plugin, enable it by including ``bucket`` into ``plugins`` line of your
beets config. The plugin provides a template function called ``%bucket`` for
use in path format expressions::

    paths:
        default: /%bucket($year)/%bucket($artist)/$albumartist-$album-$year

You must then define what ranges representations you allow in the ``bucket:``
section of the config file :

    bucket:
        bucket_alpha: ['A-F', 'G-M', 'N-Z']
        bucket_year:  ['1980s', '1990s', '2000s']

The ``bucket_year`` parameter is used for all substitutions occuring on the
``$year`` field, while ``bucket_alpha`` takes care of the others textual fields.

The definition of a range is somewhat loose, and multiple formats are allowed :

- for alpha ranges: the range is defined by the lowest and highest (ascii-wise) alphanumeric characters. eg *'ABCD'*, *'A-D'*, *'A->D'*, *[AD]* are equivalent.
- for year ranges: digits characters are extracted and the two extremes years define the range. eg *'1975-77'*, *'1975,76,77'* and *'1975-1977'* are equivalent. If no upper bound is given, the range is extended to current year (unless a later range is defined). eg *'1975'* encompasses all years from 1975 until now.

If you want to group your files into many small year ranges, you don't have to
enumerate them all in `bucket_year` parameter but can activate the ``extrapolate``
option instead. This option will generate year bucket names by reproducing characteristics
of declared buckets.

    bucket:
        bucket_year: ['2000-05']
        extrapolate: true

is enough to make the plugin return an enclosing five years range for any input year.


