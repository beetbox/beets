Plugin Development Guide
========================

Beets plugins are Python modules or packages that extend the core functionality
of beets. The plugin system is designed to be flexible, allowing developers to
add virtually any type of features.

.. _writing-plugins:

Writing Plugins
---------------

A beets plugin is just a Python module or package inside the ``beetsplug``
namespace package. (Check out `this article`_ and `this Stack Overflow
question`_ if you haven't heard about namespace packages.) So, to make one,
create a directory called ``beetsplug`` and add either your plugin module:

::

    beetsplug/
        myawesomeplugin.py

or your plugin subpackage:

::

    beetsplug/
        myawesomeplugin/
            __init__.py
            myawesomeplugin.py

.. attention::

    You do not anymore need to add a ``__init__.py`` file to the ``beetsplug``
    directory. Python treats your plugin as a namespace package automatically,
    thus we do not depend on ``pkgutil``-based setup in the ``__init__.py`` file
    anymore.

.. _this article: https://realpython.com/python-namespace-package/#setting-up-some-namespace-packages

.. _this stack overflow question: https://stackoverflow.com/a/27586272/9582674

The meat of your plugin goes in ``myawesomeplugin.py``. There, you'll have to
import ``BeetsPlugin`` from ``beets.plugins`` and subclass it, for example

.. code-block:: python

    from beets.plugins import BeetsPlugin


    class MyAwesomePlugin(BeetsPlugin):
        pass

Once you have your ``BeetsPlugin`` subclass, there's a variety of things your
plugin can do. (Read on!)

To use your new plugin, package your plugin (see how to do this with poetry_ or
setuptools_, for example) and install it into your ``beets`` virtual
environment. Then, add your plugin to beets configuration

.. _poetry: https://python-poetry.org/docs/pyproject/#packages

.. _setuptools: https://setuptools.pypa.io/en/latest/userguide/package_discovery.html#finding-simple-packages

.. code-block:: yaml

    # config.yaml
    plugins:
      - myawesomeplugin

and you're good to go!

