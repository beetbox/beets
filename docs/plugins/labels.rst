Labels plugin
=============

``labels`` is a plugin which allows you to give multiple, arbitrary tags or ``labels`` 
to the music in your library.
It's a different way to search and filter the library.

You can think of this as having multiple genre tags, 
or a way to associate feelings, places, experiences, activities or 
anything you can think of to your music.

So to start with, we want to enable the plugin.
This is done by adding something like

::

    plugins: labels

To your beets config file. (details :doc: `/plugins/index`).
This will activate the ``beet labels`` command.

Without any arguments, it just prints a list of the labels you have created.
But since you're most likely using ``labels`` for the first time, you don't have any labels yet.

Don't worry, labeling things is easy.
A couple of examples:

::

    $ beet labels irish punk rock drinking -a flogging molly
    $ beet labels crunchy rock happy-depressing -a albumartist:eels album:souljacker

So everything between ``beet labels`` and ``-a`` are labels. 
Just words or phrases separated by a whitespace.

``-a`` (or ``--attach-to``) is the option that attaches those labels to some 
tracks from the library. Everything after ``-a`` is 
treated as a query (see :doc: `/reference/query` ).

That means, in the first example, all tracks containing the phrase "flogging molly" 
in their metadata are given the 4 tags: "irish", "punk", "rock" and "drinking".  
The "Souljacker" album gets "crunchy", "rock" and "happy-depressing".

Now we can filter the library based on these labels:

::

    $ beet labels irish

Easy as pie, this will list all the stuff you've labeled as "irish" (in this case "Flogging Molly").
Or you can do:

::

   $ beet labels rock crunchy

This returns all the tracks from "Souljacker", but even though "Flogging Molly" also has 
the "rock" label, it's not "crunchy" so it's not treated as a match.


If you'd like to label full albums instead of tracks, you can include the ``--albums`` option.

Removing labels from items is done the same way as attaching them, except 
you substitute ``-a`` with ``-r`` (``--remove-from``). e.g. 

::

   $ beet labels punk -r flogging molly

That strips the "punk" label from Flogging Molly.
