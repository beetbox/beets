---
title: your musical year in review
layout: main
section: blog
---
Against my better judgment, I tend to think of music in years. Some part of me feels like it understands music better in the context of its time---what other bands were doing contemporaneously, the year's major headlines, and, most importantly, the phase of my life when I first heard an album I love.

It's the same instinct that, over the last few weeks, has flooded the Web with top-*N* lists. Even if I never write it down, I find myself making a list each winter of the "best" albums of the year. I'm not a music critic, but in January, I sometimes wish I were: as utterly subjective as my yearly mental list is, it helps me close the books on 2012 and file its music away in my memory before moving on to 2013's releases.

Here's how beets can help you with your own retrospective. First and foremost, you probably want to see a list of all your albums that were released last year:

    $ beets ls -a year:2012

(I use this query---or its [randomized][random] counterpart---almost daily throughout the year to decide what to listen to.) You might also be curious to see how many albums you collected in the year:

    $ beet ls -a year:2012 | wc -l
    85

We can take the chronology-worshiping one step further using full release dates. Since most albums in [MusicBrainz][] have release months and years, we can sort these albums by date:

    $ beet ls -af '$month-$day $albumartist - $album' year:2012 | sort -n

That query helps me "replay" the year from start to finish when thinking about each album.

This kind of flexible collection browsing is one of the reasons I originally started building beets. I hope it helps you look back over the music of 2012.

## My Favorites

For whatever it's worth, here's a sort, predictable list of some albums I remember fondly from last year, copied &rsquo;n pasted out of my terminal window in no particular order:

* alt-J - An Awesome Wave
* Passion Pit - Gossamer
* Santigold - Master of My Make-Believe
* Jack White - Blunderbuss
* Dirty Projectors - Swing Lo Magellan
* How to Dress Well - Total Loss
* Miguel - Kaleidoscope Dream
* Bob Mould - Silver Age
* Kendrick Lamar - good kid, m.A.A.d city
* Macklemore & Ryan Lewis - The Heist

Everyone should clearly love all of these records as much as I do.

[MusicBrainz]: http://musicbrainz.org/
[random]: http://beets.readthedocs.org/en/1.0rc2/plugins/rdm.html
