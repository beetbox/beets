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

.. rubric:: Plugin Events

``pluginload``
    :Parameters: (none)
    :Description: Called after all plugins have been loaded after the ``beet``
        command starts.

``import``
    :Parameters: ``lib`` (|Library|), ``paths`` (list of path strings)
    :Description: Called after the ``import`` command finishes.

``album_imported``
    :Parameters: ``lib`` (|Library|), ``album`` (|Album|)
    :Description: Called every time the importer finishes adding an album to the
        library.

``album_removed``
    :Parameters: ``lib`` (|Library|), ``album`` (|Album|)
    :Description: Called every time an album is removed from the library (even
        when its files are not deleted from disk).

``item_copied``
    :Parameters: ``item`` (|Item|), ``source`` (path), ``destination`` (path)
    :Description: Called whenever an item file is copied.

``item_imported``
    :Parameters: ``lib`` (|Library|), ``item`` (|Item|)
    :Description: Called every time the importer adds a singleton to the library
        (not called for full-album imports).

``before_item_imported``
    :Parameters: ``item`` (|Item|), ``source`` (path), ``destination`` (path)
    :Description: Called with an ``Item`` object immediately before it is
        imported.

``before_item_moved``
    :Parameters: ``item`` (|Item|), ``source`` (path), ``destination`` (path)
    :Description: Called with an ``Item`` object immediately before its file is
        moved.

``item_moved``
    :Parameters: ``item`` (|Item|), ``source`` (path), ``destination`` (path)
    :Description: Called with an ``Item`` object whenever its file is moved.

``item_linked``
    :Parameters: ``item`` (|Item|), ``source`` (path), ``destination`` (path)
    :Description: Called with an ``Item`` object whenever a symlink is created
        for a file.

``item_hardlinked``
    :Parameters: ``item`` (|Item|), ``source`` (path), ``destination`` (path)
    :Description: Called with an ``Item`` object whenever a hardlink is created
        for a file.

``item_reflinked``
    :Parameters: ``item`` (|Item|), ``source`` (path), ``destination`` (path)
    :Description: Called with an ``Item`` object whenever a reflink is created
        for a file.

``item_removed``
    :Parameters: ``item`` (|Item|)
    :Description: Called with an ``Item`` object every time an item (singleton
        or part of an album) is removed from the library (even when its file is
        not deleted from disk).

``write``
    :Parameters: ``item`` (|Item|), ``path`` (path), ``tags`` (dict)
    :Description: Called just before a file's metadata is written to disk.
        Handlers may modify ``tags`` or raise ``library.FileOperationError`` to
        abort.

``after_write``
    :Parameters: ``item`` (|Item|)
    :Description: Called after a file's metadata is written to disk.

``import_task_created``
    :Parameters: ``task`` (|ImportTask|), ``session`` (|ImportSession|)
    :Description: Called immediately after an import task is initialized. May
        return a list (possibly empty) of replacement tasks.

``import_task_start``
    :Parameters: ``task`` (|ImportTask|), ``session`` (|ImportSession|)
    :Description: Called before an import task begins processing.

``import_task_apply``
    :Parameters: ``task`` (|ImportTask|), ``session`` (|ImportSession|)
    :Description: Called after metadata changes have been applied in an import
        task (on the UI thread; keep fast). Prefer a pipeline stage otherwise
        (see :ref:`plugin-stage`).

``import_task_before_choice``
    :Parameters: ``task`` (|ImportTask|), ``session`` (|ImportSession|)
    :Description: Called after candidate search and before deciding how to
        import. May return an importer action (only one handler may return
        non-None).

``import_task_choice``
    :Parameters: ``task`` (|ImportTask|), ``session`` (|ImportSession|)
    :Description: Called after a decision has been made about an import task.
        Use ``task.choice_flag`` to inspect or change the action.

``import_task_files``
    :Parameters: ``task`` (|ImportTask|), ``session`` (|ImportSession|)
    :Description: Called after filesystem manipulation (copy/move/write) for an
        import task.

``library_opened``
    :Parameters: ``lib`` (|Library|)
    :Description: Called after beets starts and initializes the main Library
        object.

``database_change``
    :Parameters: ``lib`` (|Library|), ``model`` (|Model|)
    :Description: A modification has been made to the library database (may not
        yet be committed).

``cli_exit``
    :Parameters: ``lib`` (|Library|)
    :Description: Called just before the ``beet`` command-line program exits.

``import_begin``
    :Parameters: ``session`` (|ImportSession|)
    :Description: Called just before a ``beet import`` session starts.

``trackinfo_received``
    :Parameters: ``info`` (|TrackInfo|)
    :Description: Called after metadata for a track is fetched (e.g., from
        MusicBrainz). Handlers can modify the tags seen by later pipeline stages
        or adjustments (e.g., ``mbsync``).

``albuminfo_received``
    :Parameters: ``info`` (|AlbumInfo|)
    :Description: Like ``trackinfo_received`` but for album-level metadata.

``album_matched``
    :Parameters: ``match`` (``AlbumMatch``)
    :Description: Called after ``Item`` objects from a folder that's being
        imported have been matched to an ``AlbumInfo`` and the corresponding
        distance has been calculated. Missing and extra tracks, if any, are
        included in the match.

``before_choose_candidate``
    :Parameters: ``task`` (|ImportTask|), ``session`` (|ImportSession|)
    :Description: Called before prompting the user during interactive import.
        May return a list of ``PromptChoices`` to append to the prompt (see
        :ref:`append_prompt_choices`).

``mb_track_extract``
    :Parameters: ``data`` (dict)
    :Description: Called after metadata is obtained from MusicBrainz for a
        track. Must return a (possibly empty) dict of additional ``field:
        value`` pairs to apply (overwriting existing fields).

``mb_album_extract``
    :Parameters: ``data`` (dict)
    :Description: Like ``mb_track_extract`` but for album tags. Overwrites tags
        set at the track level with the same field.

The included ``mpdupdate`` plugin provides an example use case for event
listeners.
