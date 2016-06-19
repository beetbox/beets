---
title: "we’re pretty happy with SQLite & not urgently interested in a fancier DBMS"
---

Every once in a while, someone suggests that beets should use a "real database." I think this means storing music metadata in [PostgreSQL][] or [MySQL][] as an alternative to our current [SQLite][] database. The idea is that a more complicated DBMS should be faster, especially for huge music libraries.

The pseudo-official position of the beets project is that supporting a new DBMS is probably not worth your time. If you're interested in performance, please consider helping to optimize our database *queries* instead.

There are three reasons I'm unenthusiastic about alternative DBMSes: I'm skeptical that they will actually help performance; it's a clear case of premature optimization; and SQLite is unbeatably convenient for desktop applications like beets.

## Workload

Many people assume that Postgres or MySQL must be faster than SQLite. But performance depends on the workload, and SQLite is a great match for the beets workload.

Specifically, serious client--server DBMSes are great for web applications, where writes are frequent and concurrency is paramount. In beets, we have the opposite workload: we're read-heavy and write-light, and we rarely need concurrent updates. The main case when beets writes to its database is on [import][], and import performance is dominated by I/O to the network and to music files. This mostly-read workload is exactly what SQLite was [made for][whentouse].

[import]: http://docs.beets.io/en/latest/reference/cli.html#import
[whentouse]: https://www.sqlite.org/whentouse.html

## Low-Hanging Fruit

As [Prof. Knuth][knuth] tells us, optimization before measurement is the [root of all evil][knuth-goto]. Before we embark on any [big change for performance's sake][performance], we should have some scrap of empirical evidence to suggest that it might pay off.

[knuth]: http://www-cs-faculty.stanford.edu/~uno/
[performance]: http://c2.com/cgi/wiki?PrematureOptimization
[knuth-goto]: https://www.cs.sjsu.edu/~mak/CS185C/KnuthStructuredProgrammingGoTo.pdf

There's a better way to spend our limited developer attention. We haven't invested at all in making our database queries efficient---we have almost no indices, no principled denormalization, and certainly no detailed profiling data. Carefully measuring our query efficiency is likely to yield asymptotically better database behavior. And since we've spent so little time on it so far, there's probably a vast orchard of low-hanging fruit there.

## Hassle

Even if everything else were equal, connecting to a new database backend would incur inconvenience for users and developers. SQLite is built into Python; any other DBMS would mean a new dependency. The "real databases" people usually envision are client--server systems; these are many times more frustrating to use than an embedded library that uses a flat file. SQLite isn't perfect, of course, but it's pretty damn good for being hassle-free.

If you're convinced that a real database would be good for beets, I'd love to be proven wrong. But you need to prove it: measure the bottlenecks in beets first, think carefully about whether they might be query problems rather than DBMS problems, and be confident that the return in performance is worth the cost in hassle.

[sqlite]: https://sqlite.org
[postgresql]: https://www.postgresql.org
[mysql]: https://www.mysql.com
