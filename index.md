---
layout: main
section: main
---
<iframe width="560" height="345" src="http://www.youtube.com/embed/ZaqJmjM23D0" frameborder="0"></iframe>

The purpose of beets is to get your music collection right once and for all. It
catalogs your collection, automatically improving its metadata as it goes using
the [MusicBrainz][] database. (It also downloads cover art for albums it
imports.) Then it provides a bouquet of tools for manipulating and accessing
your music.

[MusicBrainz]: http://musicbrainz.org/

Because beets is designed as a library, it can do almost anything you can
imagine for your music collection. Via [plugins][], beets becomes a panacea:

[plugins]: http://readthedocs.org/docs/beets/-/plugins/

* Embed and extract album art from files&rsquo; tags.
* Listen to your library with a music player that speaks the [MPD][]
  protocol and works with [a staggering variety of
  interfaces][MPD clients].
* Fetch lyrics for all your songs from databases on the Web.
* Manage your [MusicBrainz music collection][coll].
* Analyze music files' metadata from the command line.
* Clean up crufty tags left behind by other, less-awesome tools.
* Browse your music library graphically through a Web browser and play it in
  any browser that supports [HTML5 audio][].

[HTML5 audio]: http://www.w3.org/TR/html-markup/audio.html
[coll]: http://musicbrainz.org/show/collection/
[MPD]: http://mpd.wikia.com/
[MPD clients]: http://mpd.wikia.com/wiki/Clients

If beets doesn't do what you want yet, [writing your own plugin][writing] is
shockingly simple if you know a little Python.

[writing]: http://readthedocs.org/docs/beets/-/plugins/#writing-plugins
    
<p class="teaser">Install beets by typing
<code><a href="http://pip.openplans.org/">pip</a> install beets</code>.
You might then want to read the
<a href="http://readthedocs.org/docs/beets/-/guides/main.html">Getting
Started</a> guide. Then follow
<a href="http://twitter.com/b33ts">@b33ts</a>
on Twitter for updates.</p>
