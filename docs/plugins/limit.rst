Limit Query Plugin
==================

``limit`` is a plugin to limit a query to the first or last set of 
results. We also provide a query prefix ``'<n'`` to inline the same 
behavior in the ``list`` command. They are analagous to piping results:

    $ beet [list|ls] [QUERY] | [head|tail] -n n

There are two provided interfaces:

1. ``beet lslimit [--head n | --tail n] [QUERY]`` returns the head or 
tail of a query

2. ``beet [list|ls] [QUERY] '<n'`` returns the head of a query

There are two differences in behavior: 

1. The query prefix does not support tail.

2. The query prefix could appear anywhere in the query but will only 
have the same behavior as the ``lslimit`` command and piping to ``head`` 
when it appears last.

Performance for the query previx is much worse due to the current  
singleton-based implementation. 

So why does the query prefix exist? Because it composes with any other 
query-based API or plugin (see :doc:`/reference/query`). For example, 
you can use the query prefix in ``smartplaylist``
(see :doc:`/plugins/smartplaylist`) to limit the number of tracks in a smart
playlist for applications like most played and recently added.

Configuration
-------------

Enable the ``limit`` plugin in your configuration (see
:ref:`using-plugins`).

Examples
--------

First 10 tracks

    $ beet ls | head -n 10
    $ beet lslimit --head 10
    $ beet ls '<10'

Last 10 tracks

    $ beet ls | tail -n 10
    $ beet lslimit --tail 10

100 mostly recently released tracks

    $ beet lslimit --head 100 year- month- day-
    $ beet ls year- month- day- '<100'
    $ beet lslimit --tail 100 year+ month+ day+
