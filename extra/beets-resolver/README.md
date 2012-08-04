beets Tomahawk resolver
=======================

This is a script resolver for [Tomahawk][tomahawk player] that hooks into
[beets][beets music manager]. It uses [beets' web plugin][] to access your
beets library remotely.

To use it, just start ``beet web``, load this resolver, and start playing
music. Change the hostname and port at the top of the file if the server isn't
running on localhost (I'll make a real UI for this eventually).

[beets' web plugin]: http://beets.readthedocs.org/en/latest/plugins/web.html
[beets music manager]: http://beets.radbox.org/
[tomahawk player]: http://tomahawk-player.org/
