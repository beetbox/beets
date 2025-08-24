.. _plugin_events:

Listen for Events
~~~~~~~~~~~~~~~~~

Event handlers allow plugins to run code whenever something happens in beets'
operation. For instance, a plugin could write a log message every time an album
is successfully autotagged or update MPD's index whenever the database is
changed.

You can "listen" for events using ``BeetsPlugin.register_listener``. Here's an
example:

::

    from beets.plugins import BeetsPlugin

    def loaded():
        print 'Plugin loaded!'

    class SomePlugin(BeetsPlugin):
      def __init__(self):
        super().__init__()
        self.register_listener('pluginload', loaded)

Note that if you want to access an attribute of your plugin (e.g. ``config`` or
``log``) you'll have to define a method and not a function. Here is the usual
registration process in this case:

::

    from beets.plugins import BeetsPlugin

    class SomePlugin(BeetsPlugin):
      def __init__(self):
        super().__init__()
        self.register_listener('pluginload', self.loaded)

      def loaded(self):
        self._log.info('Plugin loaded!')

The events currently available are:

- ``pluginload``: called after all the plugins have been loaded after the
  ``beet`` command starts
- ``import``: called after a ``beet import`` command finishes (the ``lib``
  keyword argument is a Library object; ``paths`` is a list of paths (strings)
  that were imported)
- ``album_imported``: called with an ``Album`` object every time the ``import``
  command finishes adding an album to the library. Parameters: ``lib``,
  ``album``
- ``album_removed``: called with an ``Album`` object every time an album is
  removed from the library (even when its file is not deleted from disk).
- ``item_copied``: called with an ``Item`` object whenever its file is copied.
  Parameters: ``item``, ``source`` path, ``destination`` path
- ``item_imported``: called with an ``Item`` object every time the importer adds
  a singleton to the library (not called for full-album imports). Parameters:
  ``lib``, ``item``
- ``before_item_moved``: called with an ``Item`` object immediately before its
  file is moved. Parameters: ``item``, ``source`` path, ``destination`` path
- ``item_moved``: called with an ``Item`` object whenever its file is moved.
  Parameters: ``item``, ``source`` path, ``destination`` path
- ``item_linked``: called with an ``Item`` object whenever a symlink is created
  for a file. Parameters: ``item``, ``source`` path, ``destination`` path
- ``item_hardlinked``: called with an ``Item`` object whenever a hardlink is
  created for a file. Parameters: ``item``, ``source`` path, ``destination``
  path
- ``item_reflinked``: called with an ``Item`` object whenever a reflink is
  created for a file. Parameters: ``item``, ``source`` path, ``destination``
  path
- ``item_removed``: called with an ``Item`` object every time an item (singleton
  or album's part) is removed from the library (even when its file is not
  deleted from disk).
- ``write``: called with an ``Item`` object, a ``path``, and a ``tags``
  dictionary just before a file's metadata is written to disk (i.e., just before
  the file on disk is opened). Event handlers may change the ``tags`` dictionary
  to customize the tags that are written to the media file. Event handlers may
  also raise a ``library.FileOperationError`` exception to abort the write
  operation. Beets will catch that exception, print an error message and
  continue.
- ``after_write``: called with an ``Item`` object after a file's metadata is
  written to disk (i.e., just after the file on disk is closed).
- ``import_task_created``: called immediately after an import task is
  initialized. Plugins can use this to, for example, change imported files of a
  task before anything else happens. It's also possible to replace the task with
  another task by returning a list of tasks. This list can contain zero or more
  ``ImportTask``. Returning an empty list will stop the task. Parameters:
  ``task`` (an ``ImportTask``) and ``session`` (an ``ImportSession``).
- ``import_task_start``: called when before an import task begins processing.
  Parameters: ``task`` and ``session``.
- ``import_task_apply``: called after metadata changes have been applied in an
  import task. This is called on the same thread as the UI, so use this
  sparingly and only for tasks that can be done quickly. For most plugins, an
  import pipeline stage is a better choice (see :ref:`plugin-stage`).
  Parameters: ``task`` and ``session``.
- ``import_task_before_choice``: called after candidate search for an import
  task before any decision is made about how/if to import or tag. Can be used to
  present information about the task or initiate interaction with the user
  before importing occurs. Return an importer action to take a specific action.
  Only one handler may return a non-None result. Parameters: ``task`` and
  ``session``
- ``import_task_choice``: called after a decision has been made about an import
  task. This event can be used to initiate further interaction with the user.
  Use ``task.choice_flag`` to determine or change the action to be taken.
  Parameters: ``task`` and ``session``.
- ``import_task_files``: called after an import task finishes manipulating the
  filesystem (copying and moving files, writing metadata tags). Parameters:
  ``task`` and ``session``.
- ``library_opened``: called after beets starts up and initializes the main
  Library object. Parameter: ``lib``.
- ``database_change``: a modification has been made to the library database. The
  change might not be committed yet. Parameters: ``lib`` and ``model``.
- ``cli_exit``: called just before the ``beet`` command-line program exits.
  Parameter: ``lib``.
- ``import_begin``: called just before a ``beet import`` session starts up.
  Parameter: ``session``.
- ``trackinfo_received``: called after metadata for a track item has been
  fetched from a data source, such as MusicBrainz. You can modify the tags that
  the rest of the pipeline sees on a ``beet import`` operation or during later
  adjustments, such as ``mbsync``. Slow handlers of the event can impact the
  operation, since the event is fired for any fetched possible match ``before``
  the user (or the autotagger machinery) gets to see the match. Parameter:
  ``info``.
- ``albuminfo_received``: like ``trackinfo_received``, the event indicates new
  metadata for album items. The parameter is an ``AlbumInfo`` object instead of
  a ``TrackInfo``. Parameter: ``info``.
- ``before_choose_candidate``: called before the user is prompted for a decision
  during a ``beet import`` interactive session. Plugins can use this event for
  :ref:`appending choices to the prompt <append_prompt_choices>` by returning a
  list of ``PromptChoices``. Parameters: ``task`` and ``session``.
- ``mb_track_extract``: called after the metadata is obtained from MusicBrainz.
  The parameter is a ``dict`` containing the tags retrieved from MusicBrainz for
  a track. Plugins must return a new (potentially empty) ``dict`` with
  additional ``field: value`` pairs, which the autotagger will apply to the
  item, as flexible attributes if ``field`` is not a hardcoded field. Fields
  already present on the track are overwritten. Parameter: ``data``
- ``mb_album_extract``: Like ``mb_track_extract``, but for album tags.
  Overwrites tags set at the track level, if they have the same ``field``.
  Parameter: ``data``

The included ``mpdupdate`` plugin provides an example use case for event
listeners.