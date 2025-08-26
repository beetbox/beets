Plugin Development
==================

Beets plugins are Python modules or packages that extend the core functionality
of beets. The plugin system is designed to be flexible, allowing developers to
add virtually any type of features to beets.

For instance you can create plugins that add new commands to the command-line
interface, listen for events in the beets lifecycle or extend the autotagger
with new metadata sources.

.. _basic-plugin-setup:

Basic Plugin Setup
------------------

A beets plugin is just a Python module or package inside the ``beetsplug``
namespace [namespace]_ package. To create the basic plugin layout, create a
directory called ``beetsplug`` and add either your plugin module:

.. code-block:: shell

    beetsplug/
    └── myawesomeplugin.py

or your plugin subpackage

.. code-block:: shell

    beetsplug/
    └── myawesomeplugin/
        ├── __init__.py
        └── myawesomeplugin.py

.. attention::

    You do not need to add an ``__init__.py`` file to the ``beetsplug``
    directory. Python treats your plugin as a namespace package automatically,
    thus we do not depend on ``pkgutil``-based setup in the ``__init__.py`` file
    anymore.

The meat of your plugin goes in ``myawesomeplugin.py``. Every plugin has to
extend the :class:`beets.plugins.BeetsPlugin` abstract base class [baseclass]_ .
For instance, a minimal plugin without any functionality would look like this:

.. code-block:: python

    # beetsplug/myawesomeplugin.py
    from beets.plugins import BeetsPlugin


    class MyAwesomePlugin(BeetsPlugin):
        pass

To use your new plugin, you need to package [packaging]_ your plugin and install
it into your ``beets`` (virtual) environment. To enable your plugin, add it it
to the beets configuration

.. code-block:: yaml

    # config.yaml
    plugins:
      - myawesomeplugin

and you're good to go!

.. [namespace] Check out `this article`_ and `this Stack Overflow question`_ if
    you haven't heard about namespace packages.

.. [baseclass] Abstract base classes allow us to define a contract which any
    plugin must follow. This is a common paradigm in object-oriented
    programming, and it helps to ensure that plugins are implemented in a
    consistent way. For more information, see for example pep-3119_.

.. [packaging] There are a variety of packaging tools available for python, for
    example you can use poetry_, setuptools_ or hatchling_.

.. _hatchling: https://hatch.pypa.io/latest/config/build/#build-system

.. _pep-3119: https://peps.python.org/pep-3119/#rationale

.. _poetry: https://python-poetry.org/docs/pyproject/#packages

.. _setuptools: https://setuptools.pypa.io/en/latest/userguide/package_discovery.html#finding-simple-packages

.. _this article: https://realpython.com/python-namespace-package/#setting-up-some-namespace-packages

.. _this stack overflow question: https://stackoverflow.com/a/27586272/9582674

More information
----------------

For more information on writing plugins, feel free to check out the following
resources:

.. toctree::
    :maxdepth: 2
    :includehidden:

    commands
    events
    other
