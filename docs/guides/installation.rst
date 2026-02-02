Installation
============

Beets requires `Python 3.10 or later`_. You can install it using package
managers, pipx_, pip_ or by using package managers.

.. _python 3.10 or later: https://python.org/download/

Using ``pipx`` or ``pip``
-------------------------

We recommend installing with pipx_ as it isolates beets and its dependencies
from your system Python and other Python packages. This helps avoid dependency
conflicts and keeps your system clean.

.. <!-- start-quick-install -->

.. tab-set::

    .. tab-item:: pipx

        .. code-block:: console

            pipx install beets

    .. tab-item:: pip

        .. code-block:: console

            pip install beets

    .. tab-item:: pip (user install)

        .. code-block:: console

            pip install --user beets

.. <!-- end-quick-install -->

If you don't have pipx_ installed, you can follow the instructions on the `pipx
installation page`_ to get it set up.

.. _pip: https://pip.pypa.io/en/

.. _pipx: https://pipx.pypa.io/stable

.. _pipx installation page: https://pipx.pypa.io/stable/installation/

Using a Package Manager
-----------------------

Depending on your operating system, you may be able to install beets using a
package manager. Here are some common options:

.. attention::

    Package manager installations may not provide the latest version of beets.

    Release cycles for package managers vary, and they may not always have the
    most recent version of beets. If you want the latest features and fixes,
    consider using pipx_ or pip_ as described above.

    Additionally, installing external beets plugins may be surprisingly
    difficult when using a package manager.

- On **Debian or Ubuntu**, depending on the version, beets is available as an
  official package (`Debian details`_, `Ubuntu details`_), so try typing:
  ``apt-get install beets``. But the version in the repositories might lag
  behind, so make sure you read the right version of these docs. If you want the
  latest version, you can get everything you need to install with pip as
  described below by running: ``apt-get install python-dev python-pip``
- On **Arch Linux**, `beets is in [extra] <arch extra_>`_, so just run ``pacman
  -S beets``. (There's also a bleeding-edge `dev package <aur_>`_ in the AUR,
  which will probably set your computer on fire.)
- On **Alpine Linux**, `beets is in the community repository <alpine package_>`_
  and can be installed with ``apk add beets``.
- On **Void Linux**, `beets is in the official repository <void package_>`_ and
  can be installed with ``xbps-install -S beets``.
- For **Gentoo Linux**, beets is in Portage as ``media-sound/beets``. Just run
  ``emerge beets`` to install. There are several USE flags available for
  optional plugin dependencies.
- On **FreeBSD**, there's a `beets port <freebsd_>`_ at ``audio/beets``.
- On **OpenBSD**, there's a `beets port <openbsd_>`_ can be installed with
  ``pkg_add beets``.
- On **Fedora** 22 or later, there's a `DNF package`_ you can install with
  ``sudo dnf install beets beets-plugins beets-doc``.
- On **Solus**, run ``eopkg install beets``.
- On **NixOS**, there's a `package <nixos_>`_ you can install with ``nix-env -i
  beets``.
- Using **MacPorts**, run ``port install beets`` or ``port install beets-full``
  to include many third-party plugins.

.. _alpine package: https://pkgs.alpinelinux.org/package/edge/community/x86_64/beets

.. _arch extra: https://archlinux.org/packages/extra/any/beets/

.. _aur: https://aur.archlinux.org/packages/beets-git/

.. _debian details: https://tracker.debian.org/pkg/beets

.. _dnf package: https://packages.fedoraproject.org/pkgs/beets/

.. _freebsd: http://portsmon.freebsd.org/portoverview.py?category=audio&portname=beets

.. _nixos: https://github.com/NixOS/nixpkgs/tree/master/pkgs/tools/audio/beets

.. _openbsd: http://openports.se/audio/beets

.. _ubuntu details: https://launchpad.net/ubuntu/+source/beets

.. _void package: https://github.com/void-linux/void-packages/tree/master/srcpkgs/beets

Installation FAQ
----------------

MacOS Installation
~~~~~~~~~~~~~~~~~~

**Q: I'm getting permission errors on macOS. What should I do?**

Due to System Integrity Protection on macOS 10.11+, you may need to install for
your user only:

.. code-block:: console

    pip install --user beets

You might need to also add ``~/Library/Python/3.x/bin`` to your ``$PATH``.

Windows Installation
~~~~~~~~~~~~~~~~~~~~

**Q: What's the process for installing on Windows?**

Installing beets on Windows can be tricky. Following these steps might help you
get it right:

1. `Install Python`_ (check "Add Python to PATH" skip to 3)
2. Ensure Python is in your ``PATH`` (add if needed):

   - Settings → System → About → Advanced system settings → Environment
     Variables
   - Edit "PATH" and add: `;C:\Python39;C:\Python39\Scripts`
   - *Guide: [Adding Python to
     PATH](https://realpython.com/add-python-to-path/)*

3. Now install beets by running: ``pip install beets``
4. You're all set! Type ``beet version`` in a new command prompt to verify the
   installation.

**Bonus: Windows Context Menu Integration**

Windows users may also want to install a context menu item for importing files
into beets. Download the beets.reg_ file and open it in a text file to make sure
the paths to Python match your system. Then double-click the file add the
necessary keys to your registry. You can then right-click a directory and choose
"Import with beets".

.. _beets.reg: https://github.com/beetbox/beets/blob/master/extra/beets.reg

.. _install pip: https://pip.pypa.io/en/stable/installing/

.. _install python: https://python.org/download/

ARM Installation
~~~~~~~~~~~~~~~~

**Q: Can I run beets on a Raspberry Pi or other ARM device?**

Yes, but with some considerations: Beets on ARM devices is not recommended for
Linux novices. If you are comfortable with troubleshooting tools like ``pip``,
``make``, and binary dependencies (e.g. ``ffmpeg`` and ``ImageMagick``), you
will be fine. We have `notes for ARM`_ and an `older ARM reference`_. Beets is
generally developed on x86-64 based devices, and most plugins target that
platform as well.

.. _notes for arm: https://github.com/beetbox/beets/discussions/4910

.. _older arm reference: https://discourse.beets.io/t/diary-of-beets-on-arm-odroid-hc4-armbian/1993
