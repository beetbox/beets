Installation
============

Beets requires `Python 3.10 or later`_. You can install it using pipx_ or pip_.

.. _python 3.10 or later: https://www.python.org/downloads/

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

.. _pip: https://pip.pypa.io/en/stable/

.. _pipx: https://pipx.pypa.io/stable

.. _pipx installation page: https://pipx.pypa.io/stable/how-to/install-pipx/

Managing Plugins with ``pipx``
------------------------------

When using pipx_, you can install beets with built-in plugin dependencies using
extras, inject third-party packages, and upgrade everything cleanly.

Install beets with extras for built-in plugins:

.. code-block:: console

    pipx install "beets[lyrics,lastgenre]"

If you already have beets installed, reinstall with a new set of extras:

.. code-block:: console

    pipx install --force "beets[lyrics,lastgenre]"

Inject additional packages into the beets environment (useful for third-party
plugins):

.. code-block:: console

    pipx inject beets <package-name>

To upgrade beets and all injected packages:

.. code-block:: console

    pipx upgrade beets

Installation FAQ
----------------

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

.. _install python: https://www.python.org/downloads/

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

Package Manager Installation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Q: Can I install beets using my operating system's built-in package manager?**

We generally don't recommend this route. OS package managers tend to ship
outdated versions of beets, and installing third-party plugins into a
system-managed environment ranges from awkward to impossible. You'll have a much
better time with pipx_ or pip_ as described above.

That said, if you know what you're doing and prefer your system package manager,
here are the options available:

- **Debian/Ubuntu** (`Debian <debian details_>`_, `Ubuntu <ubuntu details_>`_):
  ``apt-get install beets``
- **Arch Linux** (`extra <arch btw_>`_, `AUR dev <aur_>`_): ``pacman -S beets``
- **Alpine Linux** (`package <alpine package_>`_): ``apk add beets``
- **Void Linux** (`package <void package_>`_): ``xbps-install -S beets``
- **Gentoo Linux**: ``emerge beets`` (USE flags available for optional plugin
  deps)
- **FreeBSD** (`port <freebsd_>`_): ``audio/beets``
- **OpenBSD** (`port <openbsd_>`_): ``pkg_add beets``
- **Fedora** (`package <dnf package_>`_): ``dnf install beets beets-plugins
  beets-doc``
- **Solus**: ``eopkg install beets``
- **NixOS** (`package <nixos_>`_): ``nix-env -i beets``
- **MacPorts**: ``port install beets`` or ``port install beets-full`` (includes
  third-party plugins)

.. _alpine package: https://pkgs.alpinelinux.org/package/edge/community/x86_64/beets

.. _arch btw: https://archlinux.org/packages/extra/any/beets/

.. _aur: https://aur.archlinux.org/packages/beets-git/

.. _debian details: https://tracker.debian.org/pkg/beets

.. _dnf package: https://packages.fedoraproject.org/pkgs/beets/

.. _freebsd: https://www.freshports.org/audio/beets/

.. _nixos: https://github.com/NixOS/nixpkgs/tree/master/pkgs/development/python-modules/beets

.. _openbsd: https://openports.pl/path/audio/beets

.. _ubuntu details: https://launchpad.net/ubuntu/+source/beets

.. _void package: https://github.com/void-linux/void-packages/tree/master/srcpkgs/beets
