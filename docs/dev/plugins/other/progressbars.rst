.. _plugin-progress_bars:

Progress Bars
=============

Progress Bars for long-running operations provide valuable feedback to the user,
giving a realistic expectation of how long the command will take to finish, and
reassuring them that progress is being made. A standard implementation of
progress bars for Beets is available with ``ui.iprogress_bar``.

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
in parallel is to use the ``concurrent.futures.ThreadPoolExecutor#map`` method,
and to iterate over its results, for example:

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
