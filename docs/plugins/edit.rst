Edit Plugin
============
The ``edit`` plugin lets you open the tags, fields from a group of items, edit them in a text-editor and save them back.
Add the ``edit`` plugin to your ``plugins:`` in your ``config.yaml``. Then
you simply put in a query like you normally do.
::

     beet edit beatles
     beet edit beatles -a
     beet edit beatles -f '$title $lyrics'



You get a list of hits and then you can edit them. The ``edit`` opens your standard text-editor with a list of your hits and for each hit a bunch of fields.

Without anything specified in your ``config.yaml`` for ``edit:`` you will see

for items
::

    $track-$title-$artist-$album

and for albums
::

   $album-$albumartist

You can get fields from the cmdline by adding
::

    -f '$genre $added'

or

::

   -e '$year $comments'

If you use ``-f '$field ...'`` you get *only* what you specified.

If you use ``-e '$field ...'`` you get what you specified *extra*.

If you add ``--all`` you get all the fields.

After you edit the values in your text-editor - *and you may only edit the values, no deleting fields or adding fields!* - you save the file, answer with ``y`` on ``Done?`` and you get a summary of your changes. Check em, answer ``y`` or ``n`` and the changes are written to your library.

Configuration
-------------

Make a ``edit:`` section in your config.yaml ``(beet config -e)``
::

    edit:
       editor: nano -w -p
       diff_method: html
       browser: firefox  -private-window
       albumfields: genre album
       itemfields: track artist
       not_fields: id path
       separator: "<>"

* ``editor:`` pick your own texteditor; add arguments if needed. If no``editor:`` then your system opens the file-extension.

* ``diff_method:`` 4 choices. With no ``diff_method:`` you get the beets way of showing differences.
    - ``ndiff``: you see original and the changed yamls with the changes.
    - ``unified``: you see the changes with a bit of context. Simple and compact.
    - ``html``: a html file that you can open in a browser. Looks nice.
    - ``vimdiff``: gives you VIM with the diffs.You need VIM for this.

* ``browser:``
  If you pick ``diff_method:html`` you can specify a viewer for it (if needed add arguments). If not, let your system open the file-extension.

* The ``albumfields:`` and ``itemfields:`` lets you list the fields you want to change.
  ``albumfields:`` gets picked if you put ``-a`` in your search query, else ``itemfields:``. For a list of fields
  do the ``beet fields`` command.

* The ``not_fields:``. Fields that you put in here will not be changed. You can see them but not change them. It always contains ``id`` and standard also the ``path``.
  Don't want to mess with them.

* The default ``separator:`` prints like:

::

        -02-The Night Before-The Beatles-Help!

  
but you can pick anything else. With "<>" it will look like:
::

        <>02<>The Night Before<>The Beatles<>Help!
