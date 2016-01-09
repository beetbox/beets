---
title: the road to 1.0
section: blog
layout: main
---
Beets has been in beta forever---for small values of *forever*, at least. I made [the first commit][firstcommit] to the original Subversion repository (for shame!) on May 14, 2008 and uploaded [version 1.0b1][b1] on June 17, 2010. I'm now working on beets' sixteenth beta. It's high time that the project hit the big 1.0. I'm excited to give beets the point-zero stamp of approval, but I have two big, backwards-incompatible changes I want to make before sprouting a stable maintenance branch. In this post, I'll describe my plans for beets 1.0b16 and b17---and beyond.

## Beta 16

As nerd-oriented software, beets has a *lot* of [configuration options][config]. The config file, affectionately known as ``~/.beetsconfig``, has used an [INI][]-like syntax as defined by Python's [ConfigParser][] since the beginning. More than two years later, beets has outgrown the dated, inflexible ConfigParser system. So the next beta of beets will focus on ripping out ConfigParser altogether and replacing it with an entirely new configuration system that solves many problems at once. Here's what you can expect in 1.0b16:

[ini]: http://en.wikipedia.org/wiki/INI_file
[configparser]: http://docs.python.org/library/configparser.html

* [YAML][] syntax. The config file has grown a troubling number of half-working syntax hacks over the years. Lists of things have to be separated by whitespace, which means you can't use spaces in [regular expressions][replace]. Egregiously, I had to force users to substitute `_` characters for `:`s in query-based [path format][pathconfig] keys because ConfigParser splits on colons. Because it has a well-defined and nuanced [syntax specification][yamlspec], YAML-based config files will eschew these hacks: lists will look like lists and all characters will be treated as equals.
* You'll have a ``~/.config/beets`` directory (or the equivalent on Windows). No more cluttering your home directory with the configuration file, the state file, the library database, and maybe even the import log.
* ConfigParser does not play nice with Unicode. It's 2012, folks.
* You'll be able to combine multiple configuration files---for example, using a global base configuration with per-location overrides.
* Most crucially, programming with the ConfigParser API is getting to be a nightmare. Look no further than the monstrous [import_files][] function signature to witness the pain of threading every config option through the UI to the business end of the code. Every time I add a new config option or command-line switch to ``beet import``, I have to touch at least five files to keep the frontend and backend in sync and update the unit tests. And that's just to parse the option: the real work for the feature begins *after* all this. The ConfigParser disaster discourages me from adding new features to beets.

These problems are so basic that I don't think I'm alone in growing uneasy with ConfigParser. So I'm writing a new configuration library called [Confit][] (that's pronounced [*con-FEE*][confitwiki]). I hope to make Confit into the best available library for configuring Python applications. I'll have more to say about Confit on this blog as work progresses.

[confitwiki]: http://en.wikipedia.org/wiki/Confit
[confit]: https://github.com/sampsyo/confit
[import_files]: https://github.com/beetbox/beets/blob/30ac59f3d20dd3e7ef72456e8fca3e47713d38dc/beets/ui/commands.py#L627
[yamlspec]: http://www.yaml.org/spec/1.2/spec.html
[replace]: http://beets.readthedocs.org/en/latest/reference/config.html#replace
[pathconfig]: http://beets.readthedocs.org/en/latest/reference/config.html#path-format-configuration
[yaml]: http://yaml.org/
[config]: http://beets.readthedocs.org/en/latest/reference/config.html
[firstcommit]: https://github.com/beetbox/beets/commit/c1ed60af98bd5f18ab0a32bf782260ac15954d8e
[b1]: http://beets.readthedocs.org/en/latest/changelog.html#b1-june-17-2010

## Beta 17

Unlike b16's configuration overhaul, beta 17's nightmare is a less user-visible one: the [plugin API][pluginapi]. If you browse through the code for [beets' standard plugins][plugins], you'll quickly see that they all employ a tragic conflation between module-scoped and object-scoped variables. There are ``global``s all over the place and a nonsensical distinction between [decorated][decorator] functions and specially-named methods.

The plugin API overhaul will consolidate everything into the object scope. Plugins will follow the [singleton pattern][singleton], so it will no longer be necessary to keep anything module-global or assigned to the class itself. Decorators will be deemphasized; events will use a method naming convention instead.

And, finally, we'll drop [namespace packages][]. I didn't know this when I first started using the `beetsplug` namespace package for beets plugins, but [a bug][nspbug] in [distribute][] utterly breaks them when they're installed with a program like [pip][]. This meant that some users could never use third-party plugins without reinstalling beets. ([PEP 420][pep420] fixes everything but, alas, won't be backported to Python 2.x.)

[pep420]: http://www.python.org/dev/peps/pep-0420/
[distribute]: http://pypi.python.org/pypi/distribute/
[pip]: http://www.pip-installer.org/
[namespace packages]: http://docs.python.org/library/pkgutil.html#pkgutil.extend_path
[nspbug]: https://bitbucket.org/tarek/distribute/issue/179/namespace-packages-installed-with-single
[singleton]: http://en.wikipedia.org/wiki/Singleton_pattern
[decorator]: http://www.python.org/dev/peps/pep-0318/

While these changes aren't particularly exciting for end users, it's important that I break all the plugins before 1.0 rather than after. The goal is to make beets' plugin system future-proof---to contain the [spaghetti][spaghetti code] before it spreads.

[spaghetti code]: http://en.wikipedia.org/wiki/Spaghetti_code
[plugins]: http://beets.readthedocs.org/en/latest/plugins/index.html#plugins-included-with-beets
[pluginapi]: http://beets.readthedocs.org/en/latest/plugins/writing.html

## Beyond

With these two major changes out of the way, it will be time for some release candidates and then a massive party as we release 1.0. At this point, I plan on dividing beets development into a stable/[trunk][] development model: version 1.0 will see bug-fix-only releases while the new features go into a separate 1.1 branch. This will let me---and maybe other developers?---experiment with new stuff without rocking the boat for users who don't want to be bothered.

I have some exciting plans for new directions post-1.0. But, for now, I have two big betas to work on---we can talk about 1.1 and beyond a little later. Keep that dial right here.

[trunk]: http://en.wikipedia.org/wiki/Trunk_(software)
