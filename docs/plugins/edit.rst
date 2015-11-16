Edit Plugin
============
The ``edit`` plugin lets you open the tags, fields from a group of items, edit them in a text-editor and save them back.
Add the ``edit`` plugin to your ``plugins:`` in your ``config.yaml``. Then
simply do a query.
::

     beet edit beatles
     beet edit beatles -a
     beet edit beatles -f '$title $lyrics'



You get a list of hits to edit.``edit`` opens your standard text-editor with a list of your hits and for each hit a bunch of fields.
Without anything specified in your ``config.yaml`` for ``edit:`` you will see

for items
::

    $track-$title-$artist-$album

and for albums
::

   $album-$albumartist

You can get extra fields from the cmdline by adding
::

   -e year  -e comments


If you add ``--all`` you get all the fields.

After you edit the values in your text-editor - *and you may only edit the values, no deleting fields or adding fields!* - you save the file and you get a summary of your changes. Check em. Apply the changes into your library.

If you add ``--group`` you will get a list of fields with their values and the objects ids that use them.
So you can see ex: that the comment "downloaded from x-site" is used by 40 items. You can then delete that
string and have cleaned up your comments.
Or you can see that artist: J. S. Bach is used by 40 items and artist: JS Bach by 10. Change as you like,

Configuration
-------------

Make a ``edit:`` section in your config.yaml ``(beet config -e)``
::

    edit:
       albumfields: genre album
       itemfields: track artist

* The ``albumfields:`` and ``itemfields:`` is a list of fields you want to change.
  ``albumfields:`` gets picked if you put ``-a`` in your search query, else ``itemfields:``. For a list of fields
  do the ``beet fields`` command. Or put in a faulty one, hit enter and you get a list of available field.
