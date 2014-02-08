IHate Plugin
============

The ``ihate`` plugin allows you to automatically skip things you hate during
import or warn you about them. It supports any query, params will be checked
with OR chained logic, so as long as long as one element is satisfied the album
will be skipped.
There are two groups: warn and skip. The skip group is checked first.

To use the plugin, enable it by including ``ihate`` in the ``plugins`` line of
your beets config. Then, add an ``ihate:`` section to your configuration file::

    ihate:
        # you will be warned about these suspicious genres/artists:
        warn:
			- artist:rnb
			- genre: soul
			#only warn about tribute albums in rock genre
			- genre:rock album:tribute
        # never import any of this:
        skip:
			- genre:russian\srock
			- genre:polka
			- artist:manowar
			- album:christmas

Note: The plugin will trust your decision in 'as-is' mode.
