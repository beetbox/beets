---
title: 'moving from Google Code to GitHub: a horrible, ultimately rewarding odyssey'
layout: main
section: blog
---
The beets project began on May 14, 2008 with my first commit to a Subversion repository. On that day, [GitHub][] was [four days old][launch].

Had I known of GitHub then, I never would have started the project on Google Code. But I didn't, so I did, and it's been a hell of a time gradually moving the project over. Moving the code was easy and happened earliest. (The repository is also mirrored [on BitBucket][bb] as a Mercurial repo.) The wiki was its own ordeal and required manual conversion from Google Code's proprietary wiki syntax to Markdown (thanks, vim macros). But I procrastinated on the hardest part: the issues. Today, I finally moved that last puzzle piece over.

While I'm excited to finally move from an aging, neglected issue tracker to a shiny, well-supported new thing, the process probably could not have been more painful. Here are some tips for other open-source projects looking to make the same transition.

* Start early! This was only made more painful by having more than 500 issues in the Google Code tracker. I wish I had not procrastinated so long.
* Use the handy, hacky [google-code-issues-migrator script][script] by @arthur-debert on GitHub.
* But be aware that this project suffers from a peculiar kind of tragedy of the commons. Everybody needs this script *once* but no one is motivated to maintain it long term. So take a look at the repository's [forks][forks] and choose one by a reasonably recent pilgrim. [Here's mine.][mine] As messy as the code and the network of forks is, this little cottage industry is an incredible testament to the open-source bazaar and how GitHub is able to facilitate it.
* To test your migration, I suggest creating a temporary, private repository that won't bug anyone as you open and close a million issues. This way, I was able to debug lots of problems with labels, which you don't get to see when performing a dry run.
* You're going to need to hack the script for your particular needs. Here are some things I did:
  * I cobbled together some features from various forks of the repository, such as a `--skip_closed` flag. (Beets has hundreds of closed issues that I don't need clogging up the issue tracker.)
  * I added a flag to turn off comments and issue bodies. The issues now just link back to Google Code for their historical context. This works for us because the issues in the old tracker are old and have lots of comments, some of which are totally irrelevant. The original report text is also not usually very relevant out of context (although the title usually is).
  * I changed the script to only migrate labels that have a configured mapping since I've resolved to fiddle with labels less and use a simpler organization scheme.
* Here's the worst part: since there's no way to avoid creating each issue in turn, GitHub is going to send an email for every new issue that gets copied over. There's no awesome way to get around this; you'll just have to apologize to all your repository's watchers. (I tried temporarily removing all the repository collaborators, but this does not, unfortunately, unsubscribe them.)
* I did, however, use a temporary user to do the migration instead of my main account. This helped avoid cluttering my history with 89 different "created issue" events. Since I deleted that user, the migrated issues are now marked as having been created by a cute little [ghost][].
* Finally, Google code lets you replace a project tab with a wiki page. I used this to [redirect users to the GitHub issue tracker][gcw]. Fortunately, this does not prevent access to old issues (which are linked from GitHub).

As unpleasant as it was (as I write this, I'm *still* deleting straggling notification spam), I recommend moving from Google Code to GitHub Issues. This is an observation that's been made umpteen times before, but I remember when Google Code was an incredible relief from the antiquated and convoluted SourceForge---and this move has been every bit as satisfying.

[ghost]: https://github.com/ghost
[gcw]: http://code.google.com/p/beets/wiki/Issues?tm=3
[mine]: https://github.com/sampsyo/google-code-issues-migrator
[forks]: https://github.com/arthur-debert/google-code-issues-migrator/network
[script]: https://github.com/arthur-debert/google-code-issues-migrator
[bb]: https://bitbucket.org/adrian/beets
[launch]: https://github.com/blog/40-we-launched
[GitHub]: http://github.com/
