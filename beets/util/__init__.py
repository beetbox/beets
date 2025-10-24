# This file is part of beets.
# Copyright 2016, Adrian Sampson.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""Miscellaneous utility functions."""

from __future__ import annotations

import warnings
from importlib import import_module
from multiprocessing.pool import ThreadPool
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Generic,
    TypeVar,
    cast,
)

from beets.util.exceptions import HumanReadabaleErrorArgs, HumanReadableError
from beets.util.io import (
    CHAR_REPLACE,
    PATH_SEP,
    CommandOutput,
    FilesystemError,
    MoveOperation,
    PathBytes,
    PathLike,
    StrPath,
    ancestry,
    as_string,
    asciify_path,
    bytestring_path,
    case_sensitive,
    clean_module_tempdir,
    command_output,
    components,
    copy,
    displayable_path,
    editor_command,
    get_max_filename_length,
    get_temp_filename,
    hardlink,
    interactive_open,
    legalize_path,
    link,
    mkdirall,
    move,
    normpath,
    open_anything,
    path_as_posix,
    plurality,
    prune_dirs,
    reflink,
    remove,
    samefile,
    sanitize_path,
    sorted_walk,
    str2bool,
    syspath,
    truncate_path,
    unique_path,
)
from beets.util.misc import get_most_common_tags

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence


T = TypeVar("T")

__all__: list[str] = [
    "CHAR_REPLACE",
    "PATH_SEP",
    "CommandOutput",
    "FilesystemError",
    "HumanReadabaleErrorArgs",
    "HumanReadableError",
    "MoveOperation",
    "PathBytes",
    "PathLike",
    "StrPath",
    "ancestry",
    "as_string",
    "asciify_path",
    "bytestring_path",
    "case_sensitive",
    "clean_module_tempdir",
    "command_output",
    "components",
    "copy",
    "displayable_path",
    "editor_command",
    "get_max_filename_length",
    "get_most_common_tags",
    "get_temp_filename",
    "hardlink",
    "interactive_open",
    "legalize_path",
    "link",
    "mkdirall",
    "move",
    "normpath",
    "open_anything",
    "path_as_posix",
    "plurality",
    "prune_dirs",
    "reflink",
    "remove",
    "samefile",
    "sanitize_path",
    "sorted_walk",
    "str2bool",
    "syspath",
    "truncate_path",
    "unique_path",
]


def par_map(transform: Callable[[T], Any], items: Sequence[T]) -> None:
    """Apply the function `transform` to all the elements in the
    iterable `items`, like `map(transform, items)` but with no return
    value.

    The parallelism uses threads (not processes), so this is only useful
    for IO-bound `transform`s.
    """
    pool = ThreadPool()
    pool.map(transform, items)
    pool.close()
    pool.join()


class cached_classproperty(Generic[T]):
    """Descriptor implementing cached class properties.

    Provides class-level dynamic property behavior where the getter function is
    called once per class and the result is cached for subsequent access. Unlike
    instance properties, this operates on the class rather than instances.
    """

    cache: ClassVar[dict[tuple[type[object], str], object]] = {}

    name: str = ""

    # Ideally, we would like to use `Callable[[type[T]], Any]` here,
    # however, `mypy` is unable to see this as a **class** property, and thinks
    # that this callable receives an **instance** of the object, failing the
    # type check, for example:
    # >>> class Album:
    # >>>     @cached_classproperty
    # >>>     def foo(cls):
    # >>>         reveal_type(cls)  # mypy: revealed type is "Album"
    # >>>         return cls.bar
    #
    #   Argument 1 to "cached_classproperty" has incompatible type
    #   "Callable[[Album], ...]"; expected "Callable[[type[Album]], ...]"
    #
    # Therefore, we just use `Any` here, which is not ideal, but works.
    def __init__(self, getter: Callable[..., T]) -> None:
        """Initialize the descriptor with the property getter function."""
        self.getter: Callable[..., T] = getter

    def __set_name__(self, owner: object, name: str) -> None:
        """Capture the attribute name this descriptor is assigned to."""
        self.name = name

    def __get__(self, instance: object, owner: type[object]) -> T:
        """Compute and cache if needed, and return the property value."""
        key: tuple[type[object], str] = owner, self.name
        if key not in self.cache:
            self.cache[key] = self.getter(owner)

        return cast(T, self.cache[key])


class LazySharedInstance(Generic[T]):
    """A descriptor that provides access to a lazily-created shared instance of
    the containing class, while calling the class constructor to construct a
    new object works as usual.

    ```
    ID: int = 0

    class Foo:
        def __init__():
            global ID

            self.id = ID
            ID += 1

        def func(self):
            print(self.id)

        shared: LazySharedInstance[Foo] = LazySharedInstance()

    a0 = Foo()
    a1 = Foo.shared
    a2 = Foo()
    a3 = Foo.shared

    a0.func()  # 0
    a1.func()  # 1
    a2.func()  # 2
    a3.func()  # 1
    ```
    """

    _instance: T | None = None

    def __get__(self, instance: T | None, owner: type[T]) -> T:
        if instance is not None:
            raise RuntimeError(
                "shared instances must be obtained from the class property, "
                "not an instance"
            )

        if self._instance is None:
            self._instance = owner()

        return self._instance


def unique_list(elements: Iterable[T]) -> list[T]:
    """Return a list with unique elements in the original order."""
    return list(dict.fromkeys(elements))


def deprecate_imports(
    old_module: str, new_module_by_name: dict[str, str], name: str, version: str
) -> str:
    """Handle deprecated module imports by redirecting to new locations.

    Facilitates gradual migration of module structure by intercepting import
    attempts for relocated functionality. Issues deprecation warnings while
    transparently providing access to the moved implementation, allowing
    existing code to continue working during transition periods.
    """
    new_module: str | None
    if new_module := new_module_by_name.get(name):
        warnings.warn(
            (
                f"'{old_module}.{name}' is deprecated and will be removed"
                f" in {version}. Use '{new_module}.{name}' instead."
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        return getattr(import_module(new_module), name)
    raise AttributeError(f"module '{old_module}' has no attribute '{name}'")
