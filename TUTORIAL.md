# Beets Tutorial for Beginners
Hello and welcome to the Beets Tutorial for Beginners. If you have limited experience coding in Python and have never used Beets, you've 
come to the right place. This tutorial will walk you through all the steps necessary to set up Beets and use it to accomplish a simple task.

## Prerequisites
In order to complete this tutorial successfully, there are a few things that you should already have installed:

## You will need Python. Beets works on Python 3.6 or later.
### 1. macOS 
macOS 11 (Big Sur) includes Python 3.8 out of the box. You can opt for a more recent Python installing it via [Homebrew](https://brew.sh/) (` brew install python3 `)
. There’s also a [MacPorts](https://www.macports.org/) port. Run ` port install beets ` or ` port install beets-full ` to include many third-party plugins.

### 2. Debian or Ubuntu
On Debian or Ubuntu, depending on the version, beets is available as an official package ([Debian details](https://tracker.debian.org/pkg/beets), [Ubuntu details](https://launchpad.net/ubuntu/+source/beets)), so try typing: ` apt-get install beets `. But the version in the repositories might lag behind, so make sure you read the right version of these docs. If you want the latest version, you can get everything you need to install with pip as described below by running: ` apt-get install python-dev python-pip `

### 3. Arch Linux
On Arch Linux, beets is in [community](https://wiki.archlinux.org/title/Beets), so just run ` pacman -S beets `. (There’s also a bleeding-edge [dev package](https://aur.archlinux.org/packages/beets-git) in the AUR, which will probably set your computer on fire.)

### 4. Gentoo Linux
For Gentoo Linux, beets is in Portage as ` media-sound/beets `. Just run ` emerge beets ` to install. There are several USE flags available for optional plugin dependencies.

### 5. FreeBSD
On FreeBSD, there’s a [beets port](https://www.freebsd.org/ports/) at ` audio/beets `.

### 6. OpenBSD
On OpenBSD, there’s a [beets port](https://www.openbsd.org/faq/ports/ports.html) can be installed with ` pkg_add beets `.

### 7. Slackware
For Slackware, there’s a [SlackBuild](https://slackbuilds.org/repository/14.2/multimedia/beets/) available.

### 8. Fedora
On Fedora 22 or later, there’s a [DNF package](https://docs.fedoraproject.org/en-US/quick-docs/dnf/) you can install with ` sudo dnf install beets beets-plugins beets-doc `.

### 9. Solus
On Solus, run ` eopkg install beetsv`.

### 10. NixOS
On NixOS, there’s a [package](https://github.com/NixOS/nixpkgs/tree/master/pkgs/tools/audio/beets) you can install with ` nix-env -i beets `.

### 11. pip
If you have [pip](https://pip.pypa.io/en/stable/), just say ` pip install beets ` (or ` pip install --user beets ` if you run into permissions problems).

To install without pip, download beets from its [PyPI page](https://pypi.org/project/beets/#files) and run ` python setup.py install ` in the directory therein.

The best way to upgrade beets to a new version is by running ` pip install -U beets `. You may want to follow [@b33ts](https://twitter.com/i/flow/login?redirect_after_login=%2Fb33ts) on Twitter to hear about progress on new versions.

### 12. Installing by Hand on macOS 10.11 and Higher
Starting with version 10.11 (El Capitan), macOS has a new security feature called [System Integrity Protection](https://support.apple.com/en-us/HT204899) (SIP) that prevents you from modifying some parts of the system. This means that some `pip` commands may fail with a permissions error. (You probably won’t run into this if you’ve installed Python yourself with [Homebrew](https://brew.sh/) or otherwise. You can also try [MacPorts](https://www.macports.org/).)

If this happens, you can install beets for the current user only by typing ` pip install --user beets `. If you do that, you might want to add ` ~/Library/Python/3.6/bin ` to your ` $PATH `.

### 13. Installing on Windows
Installing beets on Windows can be tricky. Following these steps might help you get it right:

1. If you don’t have it, [install Python](https://www.python.org/downloads/) (you want Python 3.6). The installer should give you the option to “add Python to PATH.” Check this box. If you do that, you can skip the next step.
2. If you haven’t done so already, set your `PATH` environment variable to include Python and its scripts. To do so, you have to get the “Properties” window for “My Computer”, then choose the “Advanced” tab, then hit the “Environment Variables” button, and then look for the `PATH` variable in the table. Add the following to the end of the variable’s value: ` ;C:\Python36;C:\Python36\Scripts `. You may need to adjust these paths to point to your Python installation.
3. Now install beets by running: ` pip install beets `
4. You’re all set! Type `beet` at the command prompt to make sure everything’s in order.

Windows users may also want to install a context menu item for importing files into beets. Download the [beets.reg](https://github.com/beetbox/beets/blob/master/extra/beets.reg) file and open it in a text file to make sure the paths to Python match your system. Then double-click the file add the necessary keys to your registry. You can then right-click a directory and choose “Import with beets”.

Because I don’t use Windows myself, I may have missed something. If you have trouble or you have more detail to contribute here, please direct it to the [mailing list](https://groups.google.com/g/beets-users?pli=1).

## Step 1. Configuring
You’ll want to set a few basic options before you start using beets. The [configuration](https://beets.readthedocs.io/en/stable/reference/config.html) is stored in a text file. You can show its location by `running beet config -p`, though it may not exist yet. Run beet `config -e to edit` the configuration in your favorite text editor. The file will start out empty, but here’s good place to start:

```
directory: ~/music
library: ~/data/musiclibrary.db
```

Change that first path to a directory where you’d like to keep your music. Then, for `library`, choose a good place to keep a database file that keeps an index of your music. (The config’s format is [YAML](https://yaml.org/). You’ll want to configure your text editor to use spaces, not real tabs, for indentation. Also, ~ means your home directory in these paths, even on Windows.)

The default configuration assumes you want to start a new organized music folder (that `directory` above) and that you’ll copy cleaned-up music into that empty folder using beets’ `import` command (see below). But you can configure beets to behave many other ways:

- Start with a new empty directory, but move new music in instead of copying it (saving disk space). Put this in your config file:

```
import:
    move: yes
```

- Keep your current directory structure; importing should never move or copy files but instead just correct the tags on music. Put the line `copy: no` under the `import:` heading in your config file to disable any copying or renaming. Make sure to point `directory` at the place where your music is currently stored.
- Keep your current directory structure and do not correct files’ tags: leave files completely unmodified on your disk. (Corrected tags will still be stored in beets’ database, and you can use them to do renaming or tag changes later.) Put this in your config file:

```
import:
    copy: no
    write: no
```

to disable renaming and tag-writing.

There are approximately six million other configuration options you can set here, including the directory and file naming scheme. See [Configuration](https://beets.readthedocs.io/en/stable/reference/config.html) for a full reference.

## Step 2. Importing Your Library

The next step is to import your music files into the beets library database. Because this can involve modifying files and moving them around, data loss is always a possibility, so now would be a good time to make sure you have a recent backup of all your music. We’ll wait.

There are two good ways to bring your existing library into beets. You can either: (a) quickly bring all your files with all their current metadata into beets’ database, or (b) use beets’ highly-refined autotagger to find canonical metadata for every album you import. Option (a) is really fast, but option (b) makes sure all your songs’ tags are exactly right from the get-go. The point about speed bears repeating: using the autotagger on a large library can take a very long time, and it’s an interactive process. So set aside a good chunk of time if you’re going to go that route. For more on the interactive tagging process, see [Using the Auto-Tagger](https://beets.readthedocs.io/en/stable/guides/tagger.html).

If you’ve got time and want to tag all your music right once and for all, do this:

```
$ beet import /path/to/my/music
```

(Note that by default, this command will copy music into the directory you specified above. If you want to use your current directory structure, set the `import.copy` config option.) To take the fast, un-autotagged path, just say:

```
$ beet import -A /my/huge/mp3/library
```

Note that you just need to add `-A` for “don’t autotag”.

## Step 3. Adding More Music

If you’ve ripped or… otherwise obtained some new music, you can add it with the beet `import command`, the same way you imported your library. Like so:

```
$ beet import ~/some_great_album
```

This will attempt to autotag the new album (interactively) and add it to your library. There are, of course, more options for this command—just type `beet help import` to see what’s available.

## Step 4: Seeing Your Music

If you want to query your music library, the `beet list` (shortened to `beet ls`) command is for you. You give it a p[query string](https://beets.readthedocs.io/en/stable/reference/query.html), which is formatted something like a Google search, and it gives you a list of songs. Thus:

```
$ beet ls the magnetic fields
The Magnetic Fields - Distortion - Three-Way
The Magnetic Fields - Distortion - California Girls
The Magnetic Fields - Distortion - Old Fools
$ beet ls hissing gronlandic
of Montreal - Hissing Fauna, Are You the Destroyer? - Gronlandic Edit
$ beet ls bird
The Knife - The Knife - Bird
The Mae Shi - Terrorbird - Revelation Six
$ beet ls album:bird
The Mae Shi - Terrorbird - Revelation Six
```

By default, a search term will match any of a handful of [common attributes](https://beets.readthedocs.io/en/stable/reference/query.html#keywordquery) of songs. (They’re also implicitly joined by ANDs: a track must match all criteria in order to match the query.) To narrow a search term to a particular metadata field, just put the field before the term, separated by a : character. So `album:bird` only looks for `bird` in the “album” field of your songs. (Need to know more? [Queries](https://beets.readthedocs.io/en/stable/reference/query.html) will answer all your questions.)

The `beet list` command also has an `-a` option, which searches for albums instead of songs:

```
$ beet ls -a forever
Bon Iver - For Emma, Forever Ago
Freezepop - Freezepop Forever
```

There’s also an `-f` option (for format) that lets you specify what gets displayed in the results of a search:

```
$ beet ls -a forever -f "[$format] $album ($year) - $artist - $title"
[MP3] For Emma, Forever Ago (2009) - Bon Iver - Flume
[AAC] Freezepop Forever (2011) - Freezepop - Harebrained Scheme
```

In the format option, field references like $format and $year are filled in with data from each result. You can see a full list of available fields by running `beet fields`.

Beets also has a `stats` command, just in case you want to see how much music you have:

```
$ beet stats
Tracks: 13019
Total time: 4.9 weeks
Total size: 71.1 GB
Artists: 548
Albums: 1094
```

## Step 5. Keep Playing

This is only the beginning of your long and prosperous journey with beets. To keep learning, take a look at [Advanced Awesomeness](https://beets.readthedocs.io/en/stable/guides/advanced.html) for a sampling of what else is possible. You’ll also want to glance over the [Command-Line Interface](https://beets.readthedocs.io/en/stable/reference/cli.html) page for a more detailed description of all of beets’ functionality. (Like deleting music! That’s important.)

Also, check out [beets’ plugins](https://beets.readthedocs.io/en/stable/plugins/index.html). The real power of beets is in its extensibility—with plugins, beets can do almost anything for your music collection.

You can always get help using the `beet help` command. The plain `beet help` command lists all the available commands; then, for example, `beet help import` gives more specific help about the `import` command.`
