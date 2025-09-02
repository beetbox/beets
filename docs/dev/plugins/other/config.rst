Read Configuration Options
==========================

Plugins can configure themselves using the ``config.yaml`` file. You can read
configuration values in two ways. The first is to use `self.config` within your
plugin class. This gives you a view onto the configuration values in a section
with the same name as your plugin's module. For example, if your plugin is in
``greatplugin.py``, then `self.config` will refer to options under the
``greatplugin:`` section of the config file.

For example, if you have a configuration value called "foo", then users can put
this in their ``config.yaml``:

::

    greatplugin:
        foo: bar

To access this value, say ``self.config['foo'].get()`` at any point in your
plugin's code. The `self.config` object is a *view* as defined by the Confuse_
library.

.. _confuse: https://confuse.readthedocs.io/en/latest/

If you want to access configuration values *outside* of your plugin's section,
import the `config` object from the `beets` module. That is, just put ``from
beets import config`` at the top of your plugin and access values from there.

If your plugin provides configuration values for sensitive data (e.g.,
passwords, API keys, ...), you should add these to the config so they can be
redacted automatically when users dump their config. This can be done by setting
each value's `redact` flag, like so:

::

    self.config['password'].redact = True
