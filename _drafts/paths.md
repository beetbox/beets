---
title: "our solution for the hell that is filename encoding, such as it is"
layout: main
section: blog
---
By far, the worst part of working on beets is dealing with filenames. And since our job is to keep track of your files in the database, we have to deal with them all the time. This post describes the problems we discovered in the project's early days, how we address them now, and some alternatives.

## What is a Path?

What would you say a path is? In Python terms, what should the type of the argument to [`open`][open] or [`os.listdir`][listdir] be?

[open]: https://docs.python.org/2/library/functions.html#open
[listdir]: https://docs.python.org/2/library/os.html#os.listdir

Let's say you think it should be text. The OS should tell us what encoding it's using, and we get to treat its paths as human-readable strings. So the correct type is [`unicode`][unicode] on Python 2 or [`str`][str] on Python 3.

Here's the thing, though: on Unixes, *paths are fundamentally bytes*. The arguments and return types of the standard Posix OS interfaces [`open(2)`][os-open] and [`opendir(2)`][os-opendir] use [C `char*` strings][cstring] (because we still live in 1969).

This means that your operating system can, and does, lie about its filesystem encoding. As we discovered in the early days of beets, Linuxes everywhere often say their filesystem encoding is one thing and then give you bytes in a completely different encoding. The OS makes no attempt to avoid giving you completely arbitrary bytes. If you just call `fn.decode(sys.getfilesystemencoding())` in attempt to make turn your paths into Unicode text, Python will crash sometimes.

So, we must conclude that paths are bytes. But here's the other thing: on Windows, *paths are fundamentally text*. The equivalent interfaces on Windows accept and return [wide character strings][winstrings]---and on Python, that means [`unicode`][unicode] objects. So our grand plan to use bytes as the one true path representation is foiled.

It gets worse: to use full-length paths on Windows, you need to [prefix them with the four characters `\\?\`][win-prefix]. Every time. I know.

[winstrings]: https://msdn.microsoft.com/en-us/library/windows/desktop/ff381407(v=vs.85).aspx
[cstring]: https://en.wikibooks.org/wiki/C_Programming/Strings
[os-open]: http://pubs.opengroup.org/onlinepubs/009695399/functions/open.html
[os-opendir]: http://pubs.opengroup.org/onlinepubs/009695399/functions/opendir.html
[unicode]: https://docs.python.org/2/library/functions.html#unicode
[str]: https://docs.python.org/3/library/stdtypes.html#text-sequence-type-str
[win-prefix]: https://msdn.microsoft.com/en-us/library/windows/desktop/aa365247(v=vs.85).aspx

This contradiction is the root of all evil.
It's the cause of a huge amount of fiddly boilerplate code in beets, a good number of bug reports, and a lot of sadness during our current port to Python 3.

## Our Conventions

In beets, we adhere to a set of [coding conventions][hacking] that, when ruthlessly enforced, avoid potential problems.

First, we need one consistent type to store in our database. We picked bytes. This way, we can consistently represent Unix filesystems, and it requires only a bit of hacking to support Windows too. In particular, beets encodes all filenames using a fixed encoding (UTF-8) on Windows, just so that the path type is always bytes on all platforms.

To make this all work, we use three pervasive little utility functions:

* We use [`bytestring_path`][bytestring_path] to force all paths to our consistent representation. If you don't know where a path came from, you can just pass it through `bytestring_path` to rectify it before proceeding.
* The opposite function, [`displayable_path`][displayable_path], must be used to format error messages and log output. It does its best to decode the path to human-readable Unicode text, and it's not allowed to fail---but it's *lossy*. The result is only good for human consumption, not for returning back to the OS. Hence the name, which is intentionally not `unicode_path`.
* Every argument to an OS function like [`open`][open] or [`listdir`][listdir] must pass through the third utility: [`syspath`][syspath]. Think of this as converting from beets's internal representation to the OS's own representation. On Unix, this is a no-op: the representations are the same. On Windows, this returns a bytestring path back to Unicode and then adds the ridiculous [`\\?\` prefix][win-prefix], which avoids problems with long names.

It's not fun to force everybody to use these utilities everywhere, but it does work. Since we instated this policy, Unicode errors do happen but they're not nearly as pervasive as they were in the project's early days.

[displayable_path]: https://github.com/beetbox/beets/blob/42d642f1f603645ca8c3f6b0a17cd3048ef857c8/beets/util/__init__.py#L337-L353
[hacking]: https://github.com/beetbox/beets/wiki/Hacking#handling-paths
[bytestring_path]: https://github.com/beetbox/beets/blob/42d642f1f603645ca8c3f6b0a17cd3048ef857c8/beets/util/__init__.py#L316-L334
[syspath]: https://github.com/beetbox/beets/blob/42d642f1f603645ca8c3f6b0a17cd3048ef857c8/beets/util/__init__.py#L356-L387

## Must It Be This Way?

Although our solution works, I won't pretend to love it. Here are a few alternatives we might consider for the future.

### Python 3's Surrogate Escape

Python 3 chose the opposite answer to the root-of-all-evil contradiction: paths are always Unicode. Instead, it uses [surrogate escapes][pep383] to represent bytes that didn't fit the platform's purported filesystem encoding. This way, Python 3's Unicode [`str`][str] can represent arbitrary bytes in filenames. (The first commit to beets happened a bit before Python 3.0 was released, so perhaps the project can be forgiven for not adopting this approach in the first place.)

We could switch to this approach, but a few lingering details worry me:

* Migrating old bytes paths to surrogate-escaped strings won't exactly be fun.
* Might surrogate escapes tie us too much to the Python ecosystem? What happens when you try to send one of these paths to another tool that interacts with the same filesystem?
* People in the Python community have misgivings about the current implementation of surrogate escapes. [Nick Coghlan summarizes.][ncoghlan] We'll need to investigate the nuances ourselves.

[ncoghlan]: https://thoughtstreams.io/ncoghlan_dev/missing-pieces-in-python-3-unicode/

### Require UTF-8 Everywhere

One day, I believe we will live in a world where everything is UTF-8 all the time. We could hasten that good day by requiring that all paths be UTF-8 and either rejecting or fixing any other filenames as they come into beets. For now, though, this seems a just tad user-hostile for a program that works so closely with your files.

### Pathlib

We could switch to Python 3's [pathlib][] module. We'd still need to choose a uniform representation for putting these paths into our database, though, and it's not clear how well the Python 2 backport works. But we do have [a ticket for it][pathlib-ticket].

[pathlib-ticket]: https://github.com/beetbox/beets/issues/1409
[pathlib]: https://docs.python.org/3/library/pathlib.html
[pep383]: https://www.python.org/dev/peps/pep-0383/
