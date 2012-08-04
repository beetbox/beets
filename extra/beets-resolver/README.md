beets Tomahawk resolver
=======================

This is a script resolver for [Tomahawk][tomahawk player] that hooks into
[beets][beets music manager]. It uses [beets' web plugin][] to access your
beets library remotely.

To use it, just start ``beet web`` on the machine with your music and load this
resolver on the machine running Tomahawk. Use the configuration button on the
resolver to set the hostname and port of the beets server (these default to
localhost:8337). You should be able to start playing music immediately.

[beets' web plugin]: http://beets.readthedocs.org/en/latest/plugins/web.html
[beets music manager]: http://beets.radbox.org/
[tomahawk player]: http://tomahawk-player.org/
