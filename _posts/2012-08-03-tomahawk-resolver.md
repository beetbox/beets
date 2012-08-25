---
title: Tomahawk resolver
layout: main
section: blog
---
Beets is a music library manager--not, for the most part, a music player. It does include a [simple player plugin][bpd] and an [experimental Web-based player][web], but it generally leaves actual sound-reproduction to specialized tools.

[Tomahawk][] is one particularly exciting new open-source music player. The magic of Tomahawk lies in its ability to consolidate many sources of music into a single player interface. (It's also a very nicely-designed, cross-platform player even if you don't count the magic.) To integrate new sources of music with Tomahawk, you just have to provide a [resolver][]: a piece of code that searches for music and gives it to Tomahawk to display and play back.

There's now a [beets Tomahawk resolver][beets resolver] that can hook your meticulously organized beets music library into the Tomahawk interface. And it even works remotely, so you can stream music from a server running beets to a different machine running Tomahawk.

To use the resolver, first run the [beets Web plugin][web] on the machine with your music. Just add `web` to your "plugins" line in [~/.beetsconfig][config] and then run `beet web` to start the server. Then, on the machine running Tomahawk (this might, of course, be the same computer), get a copy the resolver repository. For example:

    git clone git://github.com/tomahawk-player/tomahawk-resolvers.git

Then, open the Tomahawk settings and add a new service using the "Install from file..." button. Navigate to `tomahawk-resolvers/beets` and choose the `beets.js` file. Then, click the wrench icon next to the beets resolver to configure it:

![Configuring the beets Tomahawk resolver.](/images/tomahawk-resolver-config.png)

You'll need to enter the hostname and port of the beets Web server. (You don't need to change anything if you're running the server on the local host on the default port, 8337.)

Tomahawk will now be able to find tracks from your beets library. Type a query into the "global search" box and rock out.

[beets resolver]: https://github.com/sampsyo/beets/tree/master/extra/beets-resolver
[resolver]: http://www.tomahawk-player.org/resolvers.html
[Tomahawk]: http://www.tomahawk-player.org/
[bpd]: http://readthedocs.org/docs/beets/-/plugins/bpd.html
[web]: http://readthedocs.org/docs/beets/-/plugins/web.html
[config]: http://readthedocs.org/docs/beets/-/reference/config.html
[git]: https://github.com/sampsyo/beets
[mercurial]: https://bitbucket.org/adrian/beets
