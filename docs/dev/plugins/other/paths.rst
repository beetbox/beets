Handling Paths
==============

Historically, this chapter recommended the utilities ``syspath()``,
``normpath()``, ``bytestring_path()``, and ``displayable_path()`` for handling
file paths in Beets. These ensured consistent behavior across Linux, macOS, and
Windows before Python’s ``pathlib`` offered a unified and reliable API.

- ``syspath()`` worked around Windows Unicode and long-path issues by converting
  to a system-safe string (adding the ``\\?\`` prefix where needed). Modern
  Python (≥3.6) handles this automatically through its wide-character APIs.
- ``normpath()`` normalized slashes and removed ``./`` or ``..`` parts but did
  not expand ``~``. It was used mainly for paths from user input or config
  files.
- ``bytestring_path()`` converted paths to ``bytes`` for storage in the
  database. Paths in the database are still stored as bytes today, though there
  are plans to eventually store ``pathlib.Path`` objects directly.
- ``displayable_path()`` converted byte paths to Unicode for display or logging.

These utilities remain safe to use when maintaining older code, but new code and
refactors should prefer ``pathlib.Path``:

- Use the ``.filepath`` property on ``Item`` and ``Album`` to access paths as
  ``pathlib.Path``. This replaces ``displayable_path(item.path)``.
- Normalize or expand paths using ``Path(...).expanduser().resolve()``, which
  correctly expands ``~`` and resolves symlinks.
- Cross-platform details like path separators, Unicode handling, and long-path
  support are handled automatically by ``pathlib``.

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

    path_bytes = bytestring_path(item.filepath)

In short, the old utilities were necessary for cross-platform safety in early
Beets versions, but ``pathlib.Path`` now provides these guarantees natively and
should be used for all new code. ``bytestring_path()`` is still used only for
database storage.
