Fish plugins
============

The ``fish`` plugin adds a ``beet fish`` command that will create a fish
autocompletion file ``beet.fish`` in ``~/.config/fish/completions``
This makes `fish`_ - a different shell - autocomplete commands for beet.

.. _fish: http://fishshell.com/

Configuring
===========

This will only make sense if you have the `fish`_  shell installed.
Enable the ``fish`` plugin (see :ref:`using-plugins`).
If you install or disable plugins, run ``beet fish`` again. It takes the values
from the plugins you have enabled.

Using
=====

Type ``beet fish``. Hit ``enter`` and will see the file ``beet.fish`` appear
in ``.config/fish/completions`` in your home folder.

For a  not-fish user: After you type ``beet`` in your fish-prompt and ``TAB``
you will get the autosuggestions for all your plugins/commands and
typing ``-`` will get you all the options available to you.
If you type ``beet ls`` and you ``TAB`` you will get a list of all the album/item
fields that beet offers. Start typing ``genr`` ``TAB`` and fish completes
``genre:`` ... ready to type on...

Options
=======

The default is that you get autocompletion for all the album/item fields.
You can disable that with ``beet fish -f`` In that case you only get all
the plugins/commands/options. Everything else you type in yourself.
If you want completion for a specific album/item field, you can get that like
this ``beet fish -e genre`` or ``beet fish -e genre -e albumartist`` .
Then when you type at your fish-prompt ``beet list genre:`` and you ``TAB``
you will get a list of all your genres to choose from.
REMEMBER : we get all the values of these fields and put them in the completion
file. It is not meant to be a replacement of your database. In other words :
speed and size matters.
