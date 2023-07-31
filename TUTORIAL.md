# Beets Tutorial for Beginners
Hello and welcome to the Beets Tutorial for Beginners. If you have limited experience coding in Python and have never used Beets, you've 
come to the right place. This tutorial will walk you through all the steps necessary to set up Beets and use it to accomplish a simple task.

## Prerequisites
In order to complete this tutorial successfully, there are a few things that you should already have installed:

## 1. You will need Python. Beets works on Python 3.6 or later.
### macOS 
macOS 11 (Big Sur) includes Python 3.8 out of the box. You can opt for a more recent Python installing it via [Homebrew](https://brew.sh/) (` brew install python3 `)
. There’s also a [MacPorts](https://www.macports.org/) port. Run ` port install beets ` or ` port install beets-full ` to include many third-party plugins.

### Debian or Ubuntu
On Debian or Ubuntu, depending on the version, beets is available as an official package ([Debian details](https://tracker.debian.org/pkg/beets), [Ubuntu details](https://launchpad.net/ubuntu/+source/beets)), so try typing: ` apt-get install beets `. But the version in the repositories might lag behind, so make sure you read the right version of these docs. If you want the latest version, you can get everything you need to install with pip as described below by running: ` apt-get install python-dev python-pip `

### Arch Linux
On Arch Linux, beets is in [community](https://wiki.archlinux.org/title/Beets), so just run ` pacman -S beets `. (There’s also a bleeding-edge [dev package](https://aur.archlinux.org/packages/beets-git) in the AUR, which will probably set your computer on fire.)

### Gentoo Linux
For Gentoo Linux, beets is in Portage as ` media-sound/beets `. Just run ` emerge beets ` to install. There are several USE flags available for optional plugin dependencies.

### FreeBSD
On FreeBSD, there’s a [beets port](https://www.freebsd.org/ports/) at ` audio/beets `.

### OpenBSD
On OpenBSD, there’s a [beets port](https://www.openbsd.org/faq/ports/ports.html) can be installed with ` pkg_add beets `.

### Slackware
For Slackware, there’s a [SlackBuild](https://slackbuilds.org/repository/14.2/multimedia/beets/) available.

### Fedora
On Fedora 22 or later, there’s a [DNF package](https://docs.fedoraproject.org/en-US/quick-docs/dnf/) you can install with ` sudo dnf install beets beets-plugins beets-doc `.

### Solus
On Solus, run ` eopkg install beetsv`.

### NixOS
On NixOS, there’s a [package](https://github.com/NixOS/nixpkgs/tree/master/pkgs/tools/audio/beets) you can install with ` nix-env -i beets `.

### pip
If you have [pip](https://pip.pypa.io/en/stable/), just say ` pip install beets ` (or ` pip install --user beets ` if you run into permissions problems).

To install without pip, download beets from its [PyPI page](https://pypi.org/project/beets/#files) and run ` python setup.py install ` in the directory therein.

The best way to upgrade beets to a new version is by running ` pip install -U beets `. You may want to follow [@b33ts](https://twitter.com/i/flow/login?redirect_after_login=%2Fb33ts) on Twitter to hear about progress on new versions.

### Installing by Hand on macOS 10.11 and Higher
Starting with version 10.11 (El Capitan), macOS has a new security feature called [System Integrity Protection](https://support.apple.com/en-us/HT204899) (SIP) that prevents you from modifying some parts of the system. This means that some `pip` commands may fail with a permissions error. (You probably won’t run into this if you’ve installed Python yourself with [Homebrew](https://brew.sh/) or otherwise. You can also try [MacPorts](https://www.macports.org/).)

If this happens, you can install beets for the current user only by typing ` pip install --user beets `. If you do that, you might want to add ` ~/Library/Python/3.6/bin ` to your ` $PATH `.

### Installing on Windows
Installing beets on Windows can be tricky. Following these steps might help you get it right:

1. If you don’t have it, [install Python](https://www.python.org/downloads/) (you want Python 3.6). The installer should give you the option to “add Python to PATH.” Check this box. If you do that, you can skip the next step.
2. If you haven’t done so already, set your `PATH` environment variable to include Python and its scripts. To do so, you have to get the “Properties” window for “My Computer”, then choose the “Advanced” tab, then hit the “Environment Variables” button, and then look for the `PATH` variable in the table. Add the following to the end of the variable’s value: ` ;C:\Python36;C:\Python36\Scripts `. You may need to adjust these paths to point to your Python installation.
3. Now install beets by running: ` pip install beets `
4. You’re all set! Type `beet` at the command prompt to make sure everything’s in order.

Windows users may also want to install a context menu item for importing files into beets. Download the [beets.reg](https://github.com/beetbox/beets/blob/master/extra/beets.reg) file and open it in a text file to make sure the paths to Python match your system. Then double-click the file add the necessary keys to your registry. You can then right-click a directory and choose “Import with beets”.

Because I don’t use Windows myself, I may have missed something. If you have trouble or you have more detail to contribute here, please direct it to the [mailing list](https://groups.google.com/g/beets-users?pli=1).

## Configuring
...
