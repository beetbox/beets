---
title: the SQLite lock timeout nightmare
layout: main
section: blog
---
Software has bugs. There are little bugs: the [beets release notes][relnotes] are saturated with them. And then there are the monstrous, enormous bugs: the kind that follow you from version to version, from year to year.

[relnotes]: http://readthedocs.org/docs/beets/-/changelog.html

This is a story about one of those bugs. It existed in eleven releases of beets over almost two years. The problem stuck around for so long because it seemed to manifest exclusively on other people's machines. Until the day I finally fixed it, I never reproduced the bug once on my own box.

Here's what the bug looked like to users who experienced it: beets is running along normally, happily chewing through your multi-terabyte music collection and making corrections. Then, seemingly at random, it crashes and spits out:

    sqlite3.OperationalError: database is locked

This is particularly frustrating because there's no correlation at all between what you do as a user and when this exception comes up. Like appendicitis, `OperationalError` can strike at any time, which makes it all the more maddening.

## The Problem

A little bit of background: beets uses the amazing [SQLite][] database library to store its music catalog. When importing music, multiple threads collaborate to speed up the process and several of the threads have to read from and write to the database. Fortunately, SQLite's [transactions][] and [ACID guarantees][] make this straightforward: each thread gets to make atomic accesses without bothering the other threads.

[ACID guarantees]: http://en.wikipedia.org/wiki/ACID

But things can go wrong. If a transaction stays open too long, it can block other threads from accessing the database---or, in the worst case, several threads can deadlock while waiting for each other. For exactly this reason, SQLite has a lock timeout built in. If it ever sees that a thread has been waiting for a lock for more than five seconds (by default), it throws up its hands and the user sees the dreaded `database is locked` error.

So the solution should be simple: somewhere, beets is holding a transaction open for more than five seconds, so we can either find the offending transaction or crank up that timeout. But herein lies the mystery: five seconds is a *long* time. That beets spends *5,000 milliseconds* manipulating the database in a single transaction is indicative of something dark and terrible. No amount of `SELECT`s and `INSERT`s at beets' scale should add up to five seconds, so turning up the timeout parameter is really just painting over the rot.

So I looked at every line in the source where a transaction could start. I made extra-double-sure that filesystem operations happened only outside of transactions. I fastidiously closed every [cursor][] after each `SELECT`. But all this was to no avail---the bug reports continued to pour in.

At this point, I was almost certain that nothing was wrong with beets' transactions in themselves. I measured the length of each access and, on my machine, they each took a handful of milliseconds apiece---nowhere near a full five seconds.

## The Real Problem

I finally gave up trying to reproduce the problem on my own machine. Eventually, one incredibly helpful user offered to give me guest SSH access so I could see the bug manifest *in vitro* on his machine.

I again set about measuring the length of each transaction. And again, most transactions were in the one- or two-millisecond range. But, this time, an occasional transaction would sometimes take *much* longer: 1.08 seconds, say. And, eventually, some errant transaction would take 5.04 seconds and beets would crash: `database is locked`.

But there was a pattern. Every long-lasting transaction took slightly more than an integral number of seconds. I saw transactions that took 1.02 and 1.04 seconds, but never 1.61 seconds or 0.98 seconds. Something was adding whole seconds to transactions' latencies.

Digging through the [SQLite source code][sqlite source], I looked for places where it could sleep in whole-second increments. I found [sqliteDefaultBusyCallback][dbc], the function that gets called when SQLite tries to acquire a lock but finds that it's held by a different thread. In ordinary circumstances, that function uses a simple backoff algorithm to wait a few milliseconds before trying again. But that reasonable behavior is wrapped in a preprocessor conditional like `#if HAVE_USLEEP` and, if SQLite doesn't think the system can sleep in millisecond intervals, it sleeps *for a whole second each time*.

So this was why some users saw this horrible behavior but I never did: all my systems have SQLite compiled with `HAVE_USLEEP=1`. Disassembling SQLite on my machine and the affected user's confirmed the difference. Even though [usleep][] is so old that it was obsoleted by [nanosleep][] in 2001, the user's SQLite had somehow been compiled assuming it did not exist.

The mystery was solved. And while one solution would be to [berate the world's software packagers][bsdemail] into compiling SQLite with `HAVE_USLEEP=1`, we needed a nearer-term solution.

[nanosleep]: http://pubs.opengroup.org/onlinepubs/7908799/xsh/nanosleep.html
[usleep]: http://pubs.opengroup.org/onlinepubs/7908799/xsh/usleep.html
[dbc]: http://read.cs.ucla.edu/~vandebo/sqlite/source/src/main.c#L305
[sqlite source]: http://www.sqlite.org/download.html
[bsdemail]: http://mail-index.netbsd.org/current-users/2012/06/01/msg020320.html

## The Solution

A simple solution would be to crank the SQLite lock timeout up to eleven. But I wanted something a little bit more durable and a little less ad-hoc. So beets' eventual solution to the SQLite Lock Timeout Bug from Hell kills several birds with one [Pythonic][zen] stone:

* Ensure that SQLite locks can *never* time out because they never contend.
* Through a simple coding convention, make it easy to avoid accidentally leaving a transaction open longer than it needs to be.
* Use *portable* synchronization that will work if beets eventually [moves to a dumber storage backend][nosql] that doesn't have its own concurrency support.

To accomplish all of this, beets uses *explicit transactions* that make it obvious where database accesses begin and end. And those transactions are made *mutually exclusive* using Python-level locks to ensure that only one thread accesses the database at a time.

Here's what it looks like. When a thread needs to access the database, it uses a [`with` block][with] and a "Transaction" [context manager][ctx] to query and manipulate the data. Here's [an example](https://github.com/beetbox/beets/blob/master/beets/library.py#L1182) in which a Library object looks up an Item by its ID:

    with self.transaction() as tx:
        rows = tx.query('SELECT * FROM items WHERE id=?', (load_id,))

The only way to access the database is via methods on the [Transaction object][txn]. And creating a Transaction means acquiring a lock. Together, these two restrictions make it impossible for two different threads to access the database at the same time. This reduces the concurrency available in the DB (appropriate for beets but not for, say, a popular Web service) but eradicates the possibility of SQLite timeouts and will make it easy for beets to move to a different backend in the future---even one that doesn't support concurrency itself.

[txn]: https://github.com/beetbox/beets/blob/master/beets/library.py#L919

To make this explicit-transaction approach feasible, transactions need to be *composable:* it has to be possible to take two correctly-coded transactional functions and call them both together in a single transaction. For example, the beets Library has [a method that deletes a single track](https://github.com/beetbox/beets/blob/master/beets/library.py#L1220). The ["beet remove" command][beet remove] needs to remove *many* tracks in one fell, atomic swoop.

The smaller method---`Library.remove`---uses a transaction internally so it can synchronize correctly when it's called alone. But the higher-level command has to call it many times in a single transaction, [like so](https://github.com/beetbox/beets/blob/master/beets/ui/commands.py#L984):

    with lib.transaction():
        for item in items:
            lib.remove(item)

To make all of this work, I want to make the *outermost* transaction the only one that synchronizes. If a thread enters a transaction and then, before leaving the outer one, enters another nested transaction, the inner one should have no effect. In this case, the transaction that surrounds the `for` loop needs to synchronize with other threads, but the inner transactions (inside each call to ``lib.remove``) should be [no-ops][nop] because the thread is already holding a lock.

To accomplish this, each thread transparently maintains a *transaction stack* that keeps track of all the Transaction objects that are currently active. When a transaction starts, it gets pushed onto the stack; when it finishes, it pops off. When the stack goes from having zero transactions to one, the thread acquires a lock; when the last transaction is popped from the stack, the lock is released. This simple policy allows beets to safely compose transactional code into larger functions.

[beet remove]: http://beets.readthedocs.org/en/latest/reference/cli.html#remove
[ctx]: http://docs.python.org/library/stdtypes.html#typecontextmanager
[with]: http://www.python.org/dev/peps/pep-0343/
[zen]: http://www.python.org/dev/peps/pep-0020/
[nosql]: https://github.com/beetbox/beets/wiki/Refactoring
[nop]: http://en.wikipedia.org/wiki/NOP

## Takeaway for Other Projects

What can we learn from the vanquishing of this monstrous bug---other than the [well-known fact][cbug classification] that [concurrency bugs are horrifying][heisenbug]? I think there are two lessons here: one for everybody who uses SQLite and one developers of any small-scale, desktop application that uses a database. 

[heisenbug]: http://en.wiktionary.org/wiki/heisenbug
[cbug classification]: http://www.cs.columbia.edu/~junfeng/09fa-e6998/papers/concurrency-bugs.pdf

### Assume SQLite Sleeps Whole Seconds

If you use SQLite, you currently need to assume that some users will have a copy compiled without usleep support. If you're using multiple threads, this means that, even under light contention, some transactions *will* take longer than five seconds. Either turn the timeout parameter up or otherwise account for this inevitability.

I haven't seen this particular quirk documented elsewhere, but it should be common knowledge among SQLite users.

### Try Explicit Transactions

If you're writing a small-scale application that doesn't need highly concurrent access to a database, consider using explicit transactions based on a language-level construct (Python's [context managers][ctx] are a perfect example).

Without explicit transactions, it's hard---impossible, in some cases---to see where transactions begin and end. So it's easy to introduce bugs where transactions remain open much longer than they need to be. There are several advantages to marking the start and end of every transaction:

* It's easy to verify that a transaction ends in a timely manner.
* You can add synchronization to unsynchronized datastores like [LevelDB][] or flat files.
* You can interpose on transactions for debugging purposes. For example, you might want to measure the time taken by each transaction. (This technique was instrumental to diagnosing this bug in beets.)

And if you're coding for SQLite in Python, feel free to [steal beets' Transaction implementation][txn]---it's open source!

[LevelDB]: http://code.google.com/p/leveldb/
[cursor]: http://docs.python.org/library/sqlite3.html#cursor-objects
[transactions]: http://www.sqlite.org/lang_transaction.html
[SQLite]: http://www.sqlite.org/
