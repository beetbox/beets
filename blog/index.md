---
layout: main
title: The beets blog.
section: blogindex
shorttitle: blog
---
This is the weblog for [beets][], an open-source music management system by
[Adrian Sampson][]. It consists of announcements about the project, guides to
doing fancy stuff with beets, and technical articles about Python and
music-related development.

[Subscribe to the feed.][sub] You should also follow
[@b33ts](http://twitter.com/b33ts) on Twitter, where smaller project updates
are posted more frequently.

[beets]: {{site.url}}
[Adrian Sampson]: http://www.cs.washington.edu/homes/asampson/
[sub]: {{ site.url }}/blog/atom.xml

{% for post in site.posts %}
* {{ post.date | date: '%B %e, %Y' }}: <a href="{{ post.url }}">{{ post.title }}</a>.
{% endfor %}
