---
title: rescheduling 1.0
layout: main
section: blog
---
I [blogged previously][opoblog] that beets would see two more betas---16 and 17---before hitting 1.0. The first upcoming beta version would include a complete overhaul of the configuration system.

Since that post in August, something awesome has happened: the beets community has contributed an collection of [new features and fixes][changelog] to beets, including:

* The *Convert* plugin for transcoding and embedding album art in copies.
* A convenient *Fuzzy Search* plugin.
* The aptly-named *The* plugin, which helps format strings for sorting.
* A *Zero* plugin for nulling out certain fields.
* The new *IHate* plugin to help you skip over albums.
* A completely rewritten and more stable version of the *ReplayGain* plugin.
* Album art image resizing.
* ... and much, much more.

A million thanks to all the contributors over the last few months (see the [changelog][] for credits).

Work on the as-planned beta 16 has been going on concurrently under the [confit branch][]. But, at this point, it would be unwise to unleash all these great new contributed features in the same release as the major refactoring that [Confit][] entails.

So the release schedule is changing. The current development version will become 1.0 RC 1 in the next few days. After a testing period, we'll release 1.0. At this point, the Confit branch will be developed as 1.1. This will let us fix bugs in the stable version of beets while we polish up 1.1 as the next major version.

To summarize: 1.0 very soon; Confit right after that. Here goes!

[Confit]: https://github.com/sampsyo/confit
[confit branch]: https://github.com/beetbox/beets/tree/confit
[opoblog]: {{site.url}}/blog/one-point-oh.html
[changelog]: http://beets.readthedocs.org/en/latest/changelog.html
