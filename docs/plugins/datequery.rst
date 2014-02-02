DateQuery Plugin
================

The ``datequery`` plugin enables date fields to be queried against date
instants or date intervals.

Dates can be specified as year-month-day where only year is mandatory.

Date intervals must have at least a start or an end. The endpoints are
separated by two dots.

A field can be queried as a date by prefixing the date criteria by ``T``.

Example command line queries::

  # All albums added in the year 2008:
  beet ls -a 'added:T2008'

  # All items added in the years 2008, 2009 and 2010
  beet ls 'added:T2008..2010'

  # All items added before the year 2010
  beet ls 'added:T..2009'

  # All items added in the interval [2008-12-01T00:00:00, 2009-10-12T00:00:00)
  beet ls 'added:T2008-12..2009-10-11'

  # All items with a stored file modification time in the interval [2008-12-01T00:00:00, 2008-12-03T00:00:00)
  beet ls 'mtime:T2008-12-01..2008-12-02'
