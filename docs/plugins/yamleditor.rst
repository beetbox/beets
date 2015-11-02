Yamleditor Plugin
=================
The ``yamleditor`` plugin lets you open the tags, fields from a group of items
, edit them in a text-editor and save them back.

You simply put in a query like you normally do in beets.

    `beet yamleditor beatles`
    
    `beet yamleditor beatles -a`
    
    `beet yamleditor beatles -f'$title-$lyrics'`
    


You get a list of hits and then you can edit them.
The ``yamleditor`` opens your standard text-editor with a list of your hits
and for each hit a bunch of fields.

Without anything specified in your ``config.yaml`` for ``yamleditor:``
you will get

    `track-$title-$artist-$album`      for items
    
and

   `$album-$albumartist`             for albums

you can get more fields from the cmdline by adding

    `-f '$genre $added'`
    
or

   `-e '$year $comments'`

If you use ``-f '$field $field'`` you get *only* what you specified.

If you use ``-e '$field $field'`` you get what you specified *extra*.

    ``-f or -e '$_all'``      gets you all the fields

After you edit the values in your text-editor - *and you may only edit the values,
no deleting fields or adding fields!* - you save the file, answer with y on ``Done`` and
you get a summary of your changes.
Check em, answer y or n and the changes are written to your library.

Configuration
-------------

Make a ``yamleditor:`` section in your config.yaml ``(beet config -e)``

    yamleditor:
       * editor: nano                   
       * editor_args:               
       * diff_method: ndiff 
       * html_viewer:firefox               
       * html_args :                
       * albumfields: genre album    
       * itemfields: track artist    
       * not_fields: id path         
       * separator: "<>"   
       
* editor: you can pick your own texteditor. Defaults to systems default.
* editor_args: in case you need extra arguments for your text-editor.
* diff_method: 4 choices with no diff_method you get the beets way of showing differences.
    * ndiff: you see original and the changed yaml files with the changes
    * unified: you see the changes with a bit of context. Simple and compact. 
    * html: a html file that you can open in a browser. Looks nice. 
    * vimdiff: gives you VIM with the diffs
  
* html_viewer:
  If you pick ``html`` you can specify a viewer for it. If not the systems-default
  will be picked.
* html_args: in case your html_viewer needs arguments
* The ``albumfields`` and ``itemfields`` let you put in a list of fields you want to change.
  ``albumfields`` gets picked if you put -a in your search query else ``itemfields``. For a list of fields
  do the ``beet fields``.

* The ``not_fields`` always contain ``id`` and standard also the ``path``.
  Don't want to mess with them.

* The default ``separator`` prints like:

        ``-02-The Night Before-The Beatles-Help!``

   but with ex "<>" it will look like:

        ``<>02<>The Night Before<>The Beatles<>Help!``
