Handling Paths
==============

``pathlib`` provides a clean, cross-platform API for working with filesystem
paths.

Use the ``.filepath`` property on ``Item`` and ``Album`` library objects to
access paths as ``pathlib.Path`` objects. This produces a readable, native
representation suitable for printing, logging, or further processing.

Normalize paths using ``Path(...).expanduser().resolve()``, which expands ``~``
and resolves symlinks.

Cross-platform differences—such as path separators, Unicode handling, and
long-path support (Windows) are automatically managed by ``pathlib``.

When storing paths in the database, however, convert them to bytes with
``bytestring_path()``. Paths in Beets are currently stored as bytes, although
there are plans to eventually store ``pathlib.Path`` objects directly. To access
media file paths in their stored form, use the ``.path`` property on ``Item``
and ``Album``.

Legacy utilities
----------------

Historically, Beets used custom utilities to ensure consistent behavior across
Linux, macOS, and Windows before ``pathlib`` became reliable:

- ``syspath()``: worked around Windows Unicode and long-path limitations by
  converting to a system-safe string (adding the ``\\?\`` prefix where needed).
- ``normpath()``: normalized slashes and removed ``./`` or ``..`` parts but did
  not expand ``~``.
- ``bytestring_path()``: converted paths to bytes for database storage (still
  used for that purpose today).
- ``displayable_path()``: converted byte paths to Unicode for display or
  logging.

These functions remain safe to use in legacy code, but new code should rely
solely on ``pathlib.Path``.

Examples
--------

Old style

.. code-block:: python

    displayable_path(item.path)
    normpath("~/Music/../Artist")
    syspath(path)

New style

.. code-block:: python

    item.filepath
    Path("~/Music/../Artist").expanduser().resolve()
    Path(path)

When storing paths in the database

.. code-block:: python

    path_bytes = bytestring_path(Path("/some/path/to/file.mp3"))
