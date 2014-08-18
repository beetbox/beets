Attachments
===========

Beets also gives you tools to organize the non-audio files that are
part of your music collection, e.g. cover images, digital booklets, rip
logs, etc. These are called *attachments*. Each attachment has at least
a path and a type attribute, and a track or album (an *entity*) it is
attached to. The type attribute provides a basic taxonomy for your
attachments and allows plugins to provide additional functionality for
specific types.


Getting Started
---------------

TODO: Introduction


Attaching Single Files
^^^^^^^^^^^^^^^^^^^^^^

Suppose you have downloaded the cover of the Beatles’ “Revolver” album
and the file is called `cover.jpg`. You can attach it to the album with
the following command: ::

    $ beet attach /path/to/cover.jpg --type cover album:Revolver
    add cover attachment /path/to/cover.jpg to 'The Beatles - Revolver'

The file at ``/path/to/cover.jpg`` has now been moved to the album
directory and you can query the attachment with ::

    $ beet attachls type:cover e:album:Revolver
    cover: /music/Revolver/cover.jpg

The query arguments for that `attachls` command work like the arguments
for the usual :ref:`ls <list-cmd>` command, with one addition: You can match against
the album or track (the *entity*) the file is attached to using the
``e:`` prefix. For more on the `attachls` command see :ref:`the
reference <attachls-cmd>`.

Maybe you want your cover images to have a different name, say
`front.jpg`. You can change the default paths for you attachments
through the configuration file: ::

    attachments:
        paths:
            - type: cover
              path: front.$ext

This moves all attachments of type cover are to `front.ext` in the
corresponding album directory, where `ext` is the extension of the
source file. ::

    $ beet attach /path/to/cover.jpg --type cover album:Revolver
    add cover attachment /path/to/cover.jpg to 'The Beatles - Revolver'

    $ beet attachls type:cover e:album:Revolver
    cover: /music/Revolver/front.jpg


Beets can also be configured to automatically detect the type of an
attachment from its filename. ::

    attachments:
        types:
            cover.*: cover

The :ref:`types configuration <conf-attachments-types>` is a map from
glob patterns or regular expressions to type names. You can now omit
the ``--type`` option and beet will detect the type automatically ::

    $ beet attach /path/to/cover.jpg album:Revolver
    add cover attachment /path/to/cover.jpg to 'The Beatles - Revolver'

    $ beet attachls type:cover e:album:Revolver
    cover: /music/Revolver/cover.jpg

Of course you can still specify another type on the command line.


Importing Attachments
^^^^^^^^^^^^^^^^^^^^^

Beets will automatically create attachments when you import new music.

Since you already have “Revolver” in your library, suppose you want to
also add the “Abbey Road” album. You have ripped the album and moved it
to the ``/import`` directory. The directory also contains the files
``cover.jpg`` and ``booklet.pdf`` that you want to create attachments
for. To automatically detect the types, we add the following to our
configuration: ::

    attachments:
        types:
            cover.*: cover
            booklet.pdf: booklet

In addition to adding the album to your library, the ``beet import
/import`` command will now print the lines ::

    add cover attachment /import/cover.jpg to 'The Beatles - Revolver'
    add booklet attachment /import/booklet.pdf to 'The Beatles - Revolver'

and you can confirm it with ::

    $ beet attachls "e:Abbey Road"
    /music/Abbey Road/cover.jpg
    /music/Abbey Road/booklet.pdf

For each album that is about to be imported, beets looks at all the
non-music files contained in the album’s source directory. Beets then
tries to determine the type of each file and, if successful, creates an
attachment of this type. Files with no type are ignored.  The file
manipulations for attachments mirror that of the music files and can be
configured through the ``import.move`` and ``import.copy`` options.


Import Attachments Only
^^^^^^^^^^^^^^^^^^^^^^^

If you have used beets before, you may already have some files in your
library that you want to attach with beets. Instead of repeating the
`attach` command for each of those files, there is a :ref:`attach-import
command <attach-import-cmd>`. This command is similar to a reimport
with ``beet import``, but it just creates attachments and skip all
audio files.

As an example, suppose you have a ``cover.jpg`` file in some of your
album directories and you want them to be added as a ``cover``
attachment to their corresponding album. First make sure the type of
the file is recognised by beets. ::

    attachments:
        types:
            cover.jpg: cover

Then run ::

    $ beet attach-import
    add cover attachment /music/Revolver/cover.jpg to 'The Beatles - Revolver'
    add cover attachment /music/Abbey Road/cover.jpg to 'The Beatles - Abbey Road'
    ...

and all cover images will be attached to their albums.


.. _attachment-plugins:

Attachment Plugins
------------------

TODO


Reference
=========


Command-Line
------------

``attach``
^^^^^^^^^^

``attachls``
^^^^^^^^^^^^

``attach-import``
^^^^^^^^^^^^^^^^^

Configuration
-------------

.. _conf-attachments-types:

types
^^^^^

paths
^^^^^


To Do
=====

* Fallback type for discover and import
* Ignore dot files
* Interactive type input on import (create issue)
* Documentation for multiple types (do we need them)
* Document track attachments
* Move attachments with same path
* Automatically determine query from path for `attach`
* Remove warning for unknown files
* Additional template variables overwritten by flex attrs
