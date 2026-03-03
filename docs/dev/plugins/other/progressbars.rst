.. _plugin-progress_bars:

Progress Bars
=============

Progress bars for long-running operations provide valuable feedback to the user,
giving a realistic expectation of how long the command will take to finish, and
reassuring them that progress is being made. A standard implementation of
progress bars for Beets is available in the core UI module as
``ui.iprogress_bar`` and does not require any plugin to be enabled.

Library convenience methods
--------------------------

When iterating over items or albums from the library, you can use
:meth:`~beets.library.Library.items_with_progress` and
:meth:`~beets.library.Library.albums_with_progress`
instead of calling ``ui.iprogress_bar`` directly. These methods accept the same
query and sort arguments as :meth:`~beets.library.Library.items` and
:meth:`~beets.library.Library.albums`,
plus a description and optional unit label for the progress bar:

.. code-block:: python

    for item in lib.items_with_progress(
        "Embedding artwork",
        args,
        unit="item",
    ):
        art.embed_item(self._log, item, imagepath, ...)

    for album in lib.albums_with_progress(
        "Updating albums",
        args,
        unit="album",
    ):
        do_something_to(album)

This avoids repeating the same ``ui.iprogress_bar(..., desc=..., unit=...)``
arguments in every command.

Using ``ui.iprogress_bar`` directly
----------------------------------

The standard implementation wraps any iterable, and has particular logic
specific to Album and Item iterators. When iterating over Album or Item objects,
the progress bar will additionally indicate how many of the database records
have been modified. Using this standard implementation will ensure your plugin
displays progress in a consistent manner across Beets.

The ``ui.iprogress_bar`` implementation uses the enlighten_ library, and follows
its API closely, for example:

.. code-block:: python

    for item in ui.iprogress_bar(
        lib.items(args),
        desc="Analyzing",
        unit="track",
    ):
        self.handle_track(item)

.. _enlighten: https://python-enlighten.readthedocs.io/en/stable/

If the iterable does not expose its length directly, then the total number of
items to process can be provided with the ``total`` kwarg, for example:

.. code-block:: python

    items = ...
    num_items = ...

    for item in ui.iprogress_bar(items, desc="Analyzing", unit="track", total=num_items):
        self.handle_track(item)

A simple method for displaying progress while applying a function to all results
in parallel is to use the ``ThreadPoolExecutor.map()`` method, and to iterate
over its results, for example:

.. code-block:: python

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor() as executor:
        for _ in ui.iprogress_bar(
            executor.map(self.handle_track, items),
            desc="Analyzing",
            unit="track",
            total=len(items),
        ):
            pass