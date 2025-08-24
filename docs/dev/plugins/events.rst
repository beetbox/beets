.. _plugin_events:

Listen for Events
=================

.. currentmodule:: beets.plugins

Event handlers allow plugins to hook into whenever something happens in beets'
operations. For instance, a plugin could write a log message every time an album
is successfully autotagged or update MPD's index whenever the database is
changed.

You can "listen" for events using :py:meth:`BeetsPlugin.register_listener`.
Here's an example:

.. code-block:: python

    from beets.plugins import BeetsPlugin


    def loaded():
        print("Plugin loaded!")


    class SomePlugin(BeetsPlugin):
        def __init__(self):
            super().__init__()
            self.register_listener("pluginload", loaded)

Note that if you want to access an attribute of your plugin (e.g. ``config`` or
``log``) you'll have to define a method and not a function. Here is the usual
registration process in this case:

.. code-block:: python

    from beets.plugins import BeetsPlugin


    class SomePlugin(BeetsPlugin):
        def __init__(self):
            super().__init__()
            self.register_listener("pluginload", self.loaded)

        def loaded(self):
            self._log.info("Plugin loaded!")

.. list-table:: Plugin Events
    :widths: 15 25 60
    :header-rows: 1

    - - Event
      - Parameters
      - Description
    - - `pluginload`
      -
      - called after all the plugins have been loaded after the ``beet`` command
        starts
    - - `import`
      - :py:class:`lib <beets.library.Library>`, ``paths`` is a list of paths
        (strings)
      - called after the ``import`` command finishes.
    - - `album_imported`
      - :py:class:`lib <beets.library.Library>`, :py:class:`album
        <beets.library.Album>`
      - called every time the ``import`` command finishes adding an album to the
        library
    - - `album_removed`
      - :py:class:`lib <beets.library.Library>`, :py:class:`album
        <beets.library.Album>`
      - called every time an album is removed from the library (even when its
        file is not deleted from disk)
    - - `item_copied`
      - :py:class:`item <beets.library.Item>`, ``source`` path, ``destination``
        path
      - called whenever an item file is copied
    - - `item_imported`
      - :py:class:`lib <beets.library.Library>`, :py:class:`item
        <beets.library.Item>`
      - called every time the importer adds a singleton to the library (not
        called for full-album imports)
    - - `before_item_imported`
      - :py:class:`item <beets.library.Item>`, ``source`` path, ``destination``
        path
      - called with an item object immediately before it is imported
    - - `before_item_moved`
      - :py:class:`item <beets.library.Item>`, ``source`` path, ``destination``
        path
      - called with an ``Item`` object immediately before its file is moved
    - - `item_moved`
      - :py:class:`item <beets.library.Item>`, ``source`` path, ``destination``
        path
      - called with an ``Item`` object whenever its file is moved
    - - `item_linked`
      - :py:class:`item <beets.library.Item>`, ``source`` path, ``destination``
        path
      - called with an ``Item`` object whenever a symlink is created for a file
    - - `item_hardlinked`
      - :py:class:`item <beets.library.Item>`, ``source`` path, ``destination``
        path
      - called with an ``Item`` object whenever a hardlink is created for a file
    - - `item_reflinked`
      - :py:class:`item <beets.library.Item>`, ``source`` path, ``destination``
        path
      - called with an ``Item`` object whenever a reflink is created for a file
    - - `item_removed`
      - :py:class:`item <beets.library.Item>`
      - called with an ``Item`` object every time an item (singleton or album's
        part) is removed from the library (even when its file is not deleted
        from disk).
    - - `write`
      - :py:class:`item <beets.library.Item>`, ``path``, ``tags`` dictionary
      - called with an ``Item`` object, a ``path``, and a ``tags`` dictionary
        just before a file's metadata is written to disk (i.e., just before the
        file on disk is opened). Event handlers may change the ``tags``
        dictionary to customize the tags that are written to the media file.
        Event handlers may also raise a ``library.FileOperationError`` exception
        to abort the write operation. Beets will catch that exception, print an
        error message, and continue.
    - - `after_write`
      - :py:class:`item <beets.library.Item>`
      - called with an ``Item`` object after a file's metadata is written to
        disk (i.e., just after the file on disk is closed).
    - - `import_task_created`
      - :py:class:`task <beets.importer.ImportTask>`, :py:class:`session
        <beets.importer.ImportSession>`
      - called immediately after an import task is initialized. Plugins can use
        this to, for example, change imported files of a task before anything
        else happens. It's also possible to replace the task with another task
        by returning a list of tasks. This list can contain zero or more
        ImportTasks. Returning an empty list will stop the task.
    - - `import_task_start`
      - :py:class:`task <beets.importer.ImportTask>`, :py:class:`session
        <beets.importer.ImportSession>`
      - called when before an import task begins processing.
    - - `import_task_apply`
      - :py:class:`task <beets.importer.ImportTask>`, :py:class:`session
        <beets.importer.ImportSession>`
      - called after metadata changes have been applied in an import task. This
        is called on the same thread as the UI, so use this sparingly and only
        for tasks that can be done quickly. For most plugins, an import pipeline
        stage is a better choice (see :ref:`plugin-stage`).
    - - `import_task_before_choice`
      - :py:class:`task <beets.importer.ImportTask>`, :py:class:`session
        <beets.importer.ImportSession>`
      - called after candidate search for an import task before any decision is
        made about how/if to import or tag. Can be used to present information
        about the task or initiate interaction with the user before importing
        occurs. Return an importer action to take a specific action. Only one
        handler may return a non-None result.
    - - `import_task_choice`
      - :py:class:`task <beets.importer.ImportTask>`, :py:class:`session
        <beets.importer.ImportSession>`
      - called after a decision has been made about an import task. This event
        can be used to initiate further interaction with the user. Use
        ``task.choice_flag`` to determine or change the action to be taken.
    - - `import_task_files`
      - :py:class:`task <beets.importer.ImportTask>`, :py:class:`session
        <beets.importer.ImportSession>`
      - called after an import task finishes manipulating the filesystem
        (copying and moving files, writing metadata tags).
    - - `library_opened`
      - :py:class:`lib <beets.library.Library>`
      - called after beets starts up and initializes the main Library object.
    - - `database_change`
      - :py:class:`lib <beets.library.Library>`, :py:class:`model
        <beets.library.Model>`
      - a modification has been made to the library database. The change might
        not be committed yet.
    - - `cli_exit`
      - :py:class:`lib <beets.library.Library>`
      - called just before the ``beet`` command-line program exits.
    - - `import_begin`
      - :py:class:`session <beets.importer.ImportSession>`
      - called just before a ``beet import`` session starts up.
    - - `trackinfo_received`
      - :py:class:`info <beets.autotag.TrackInfo>`
      - called after metadata for a track item has been fetched from a data
        source, such as MusicBrainz. You can modify the tags that the rest of
        the pipeline sees on a ``beet import`` operation or during later
        adjustments, such as ``mbsync``.
    - - `albuminfo_received`
      - :py:class:`info <beets.autotag.AlbumInfo>`
      - like `trackinfo_received`, the event indicates new metadata for album
        items.
    - - `before_choose_candidate`
      - :py:class:`task <beets.importer.ImportTask>`, :py:class:`session
        <beets.importer.ImportSession>`
      - called before the user is prompted for a decision during a ``beet
        import`` interactive session. Plugins can use this event for
        :ref:`appending choices to the prompt <append_prompt_choices>` by
        returning a list of ``PromptChoices``.
    - - `mb_track_extract`
      - :py:class:`data <dict>`
      - called after the metadata is obtained from MusicBrainz. The parameter is
        a ``dict`` containing the tags retrieved from MusicBrainz for a track.
        Plugins must return a new (potentially empty) ``dict`` with additional
        ``field: value`` pairs, which the autotagger will apply to the item, as
        flexible attributes if ``field`` is not a hardcoded field. Fields
        already present on the track are overwritten.
    - - `mb_album_extract`
      - :py:class:`data <dict>`
      - Like `mb_track_extract`, but for album tags. Overwrites tags set at the
        track level, if they have the same ``field``.

The included ``mpdupdate`` plugin provides an example use case for event
listeners.
