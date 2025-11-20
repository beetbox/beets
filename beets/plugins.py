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

"""Support for beets plugins."""

from __future__ import annotations

import abc
import inspect
import re
import sys
import warnings
from collections import defaultdict
from functools import cached_property, wraps
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypeVar

import mediafile
from typing_extensions import ParamSpec

import beets
from beets import logging
from beets.util import unique_list

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from confuse import ConfigView

    from beets.dbcore import Query
    from beets.dbcore.db import FieldQueryType
    from beets.dbcore.types import Type
    from beets.importer import ImportSession, ImportTask
    from beets.library import Album, Item, Library
    from beets.ui import Subcommand

    # TYPE_CHECKING guard is needed for any derived type
    # which uses an import from `beets.library` and `beets.imported`
    ImportStageFunc = Callable[[ImportSession, ImportTask], None]
    T = TypeVar("T", Album, Item, str)
    TFunc = Callable[[T], str]
    TFuncMap = dict[str, TFunc[T]]

    AnyModel = TypeVar("AnyModel", Album, Item)

    P = ParamSpec("P")
    Ret = TypeVar("Ret", bound=Any)
    Listener = Callable[..., Any]
    IterF = Callable[P, Iterable[Ret]]


PLUGIN_NAMESPACE = "beetsplug"

# Plugins using the Last.fm API can share the same API key.
LASTFM_KEY = "2dc3914abf35f0d9c92d97d8f8e42b43"

EventType = Literal[
    "after_write",
    "album_imported",
    "album_removed",
    "albuminfo_received",
    "album_matched",
    "before_choose_candidate",
    "before_item_moved",
    "cli_exit",
    "database_change",
    "import",
    "import_begin",
    "import_task_apply",
    "import_task_before_choice",
    "import_task_choice",
    "import_task_created",
    "import_task_files",
    "import_task_start",
    "item_copied",
    "item_hardlinked",
    "item_imported",
    "item_linked",
    "item_moved",
    "item_reflinked",
    "item_removed",
    "library_opened",
    "mb_album_extract",
    "mb_track_extract",
    "pluginload",
    "trackinfo_received",
    "write",
]
# Global logger.
log = logging.getLogger("beets")


class PluginConflictError(Exception):
    """Indicates that the services provided by one plugin conflict with
    those of another.

    For example two plugins may define different types for flexible fields.
    """


class PluginImportError(ImportError):
    """Indicates that a plugin could not be imported.

    This is a subclass of ImportError so that it can be caught separately
    from other errors.
    """

    def __init__(self, name: str):
        super().__init__(f"Could not import plugin {name}")


class PluginLogFilter(logging.Filter):
    """A logging filter that identifies the plugin that emitted a log
    message.
    """

    def __init__(self, plugin):
        self.prefix = f"{plugin.name}: "

    def filter(self, record):
        if hasattr(record.msg, "msg") and isinstance(record.msg.msg, str):
            # A _LogMessage from our hacked-up Logging replacement.
            record.msg.msg = f"{self.prefix}{record.msg.msg}"
        elif isinstance(record.msg, str):
            record.msg = f"{self.prefix}{record.msg}"
        return True


# Managing the plugins themselves.


class BeetsPlugin(metaclass=abc.ABCMeta):
    """The base class for all beets plugins. Plugins provide
    functionality by defining a subclass of BeetsPlugin and overriding
    the abstract methods defined here.
    """

    _raw_listeners: ClassVar[dict[EventType, list[Listener]]] = defaultdict(
        list
    )
    listeners: ClassVar[dict[EventType, list[Listener]]] = defaultdict(list)
    template_funcs: TFuncMap[str] | None = None
    template_fields: TFuncMap[Item] | None = None
    album_template_fields: TFuncMap[Album] | None = None

    name: str
    config: ConfigView
    early_import_stages: list[ImportStageFunc]
    import_stages: list[ImportStageFunc]

    def __init_subclass__(cls) -> None:
        """Enable legacy metadata‐source plugins to work with the new interface.

        When a plugin subclass of BeetsPlugin defines a `data_source` attribute
        but does not inherit from MetadataSourcePlugin, this hook:

        1. Skips abstract classes.
        2. Warns that the class should extend MetadataSourcePlugin (deprecation).
        3. Copies any nonabstract methods from MetadataSourcePlugin onto the
           subclass to provide the full plugin API.

        This compatibility layer will be removed in the v3.0.0 release.
        """
        # TODO: Remove in v3.0.0
        if inspect.isabstract(cls):
            return

        from beets.metadata_plugins import MetadataSourcePlugin

        if issubclass(cls, MetadataSourcePlugin) or not hasattr(
            cls, "data_source"
        ):
            return

        warnings.warn(
            f"{cls.__name__} is used as a legacy metadata source. "
            "It should extend MetadataSourcePlugin instead of BeetsPlugin. "
            "Support for this will be removed in the v3.0.0 release!",
            DeprecationWarning,
            stacklevel=3,
        )

        method: property | cached_property[Any] | Callable[..., Any]
        for name, method in inspect.getmembers(
            MetadataSourcePlugin,
            predicate=lambda f: (  # type: ignore[arg-type]
                (
                    isinstance(f, (property, cached_property))
                    and not hasattr(
                        BeetsPlugin,
                        getattr(f, "attrname", None) or f.fget.__name__,  # type: ignore[union-attr]
                    )
                )
                or (
                    inspect.isfunction(f)
                    and f.__name__
                    and not getattr(f, "__isabstractmethod__", False)
                    and not hasattr(BeetsPlugin, f.__name__)
                )
            ),
        ):
            setattr(cls, name, method)

    def __init__(self, name: str | None = None):
        """Perform one-time plugin setup."""

        self.name = name or self.__module__.split(".")[-1]
        self.config = beets.config[self.name]

        # Set class attributes if they are not already set
        # for the type of plugin.
        if not self.template_funcs:
            self.template_funcs = {}
        if not self.template_fields:
            self.template_fields = {}
        if not self.album_template_fields:
            self.album_template_fields = {}

        self.early_import_stages = []
        self.import_stages = []

        self._log = log.getChild(self.name)
        self._log.setLevel(logging.NOTSET)  # Use `beets` logger level.
        if not any(isinstance(f, PluginLogFilter) for f in self._log.filters):
            self._log.addFilter(PluginLogFilter(self))

        # In order to verify the config we need to make sure the plugin is fully
        # configured (plugins usually add the default configuration *after*
        # calling super().__init__()).
        self.register_listener("pluginload", self._verify_config)

    def _verify_config(self, *_, **__) -> None:
        """Verify plugin configuration.

        If deprecated 'source_weight' option is explicitly set by the user, they
        will see a warning in the logs. Otherwise, this must be configured by
        a third party plugin, thus we raise a deprecation warning which won't be
        shown to user but will be visible to plugin developers.
        """
        # TODO: Remove in v3.0.0
        if (
            not hasattr(self, "data_source")
            or "source_weight" not in self.config
        ):
            return

        message = (
            "'source_weight' configuration option is deprecated and will be"
            " removed in v3.0.0. Use 'data_source_mismatch_penalty' instead"
        )
        for source in self.config.root().sources:
            if "source_weight" in (source.get(self.name) or {}):
                if source.filename:  # user config
                    self._log.warning(message)
                else:  # 3rd-party plugin config
                    warnings.warn(message, DeprecationWarning, stacklevel=0)

    def commands(self) -> Sequence[Subcommand]:
        """Should return a list of beets.ui.Subcommand objects for
        commands that should be added to beets' CLI.
        """
        return ()

    def _set_stage_log_level(
        self,
        stages: list[ImportStageFunc],
    ) -> list[ImportStageFunc]:
        """Adjust all the stages in `stages` to WARNING logging level."""
        return [
            self._set_log_level_and_params(logging.WARNING, stage)
            for stage in stages
        ]

    def get_early_import_stages(self) -> list[ImportStageFunc]:
        """Return a list of functions that should be called as importer
        pipelines stages early in the pipeline.

        The callables are wrapped versions of the functions in
        `self.early_import_stages`. Wrapping provides some bookkeeping for the
        plugin: specifically, the logging level is adjusted to WARNING.
        """
        return self._set_stage_log_level(self.early_import_stages)

    def get_import_stages(self) -> list[ImportStageFunc]:
        """Return a list of functions that should be called as importer
        pipelines stages.

        The callables are wrapped versions of the functions in
        `self.import_stages`. Wrapping provides some bookkeeping for the
        plugin: specifically, the logging level is adjusted to WARNING.
        """
        return self._set_stage_log_level(self.import_stages)

    def _set_log_level_and_params(
        self,
        base_log_level: int,
        func: Callable[P, Ret],
    ) -> Callable[P, Ret]:
        """Wrap `func` to temporarily set this plugin's logger level to
        `base_log_level` + config options (and restore it to its previous
        value after the function returns). Also determines which params may not
        be sent for backwards-compatibility.
        """
        argspec = inspect.getfullargspec(func)

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Ret:
            assert self._log.level == logging.NOTSET

            verbosity = beets.config["verbose"].get(int)
            log_level = max(logging.DEBUG, base_log_level - 10 * verbosity)
            self._log.setLevel(log_level)
            if argspec.varkw is None:
                kwargs = {k: v for k, v in kwargs.items() if k in argspec.args}  # type: ignore[assignment]

            try:
                return func(*args, **kwargs)
            finally:
                self._log.setLevel(logging.NOTSET)

        return wrapper

    def queries(self) -> dict[str, type[Query]]:
        """Return a dict mapping prefixes to Query subclasses."""
        return {}

    def add_media_field(
        self, name: str, descriptor: mediafile.MediaField
    ) -> None:
        """Add a field that is synchronized between media files and items.

        When a media field is added ``item.write()`` will set the name
        property of the item's MediaFile to ``item[name]`` and save the
        changes. Similarly ``item.read()`` will set ``item[name]`` to
        the value of the name property of the media file.
        """
        # Defer import to prevent circular dependency
        from beets import library

        mediafile.MediaFile.add_field(name, descriptor)
        library.Item._media_fields.add(name)

    def register_listener(self, event: EventType, func: Listener) -> None:
        """Add a function as a listener for the specified event."""
        if func not in self._raw_listeners[event]:
            self._raw_listeners[event].append(func)
            self.listeners[event].append(
                self._set_log_level_and_params(logging.WARNING, func)
            )

    @classmethod
    def template_func(cls, name: str) -> Callable[[TFunc[str]], TFunc[str]]:
        """Decorator that registers a path template function. The
        function will be invoked as ``%name{}`` from path format
        strings.
        """

        def helper(func: TFunc[str]) -> TFunc[str]:
            if cls.template_funcs is None:
                cls.template_funcs = {}
            cls.template_funcs[name] = func
            return func

        return helper

    @classmethod
    def template_field(cls, name: str) -> Callable[[TFunc[Item]], TFunc[Item]]:
        """Decorator that registers a path template field computation.
        The value will be referenced as ``$name`` from path format
        strings. The function must accept a single parameter, the Item
        being formatted.
        """

        def helper(func: TFunc[Item]) -> TFunc[Item]:
            if cls.template_fields is None:
                cls.template_fields = {}
            cls.template_fields[name] = func
            return func

        return helper


def get_plugin_names() -> list[str]:
    """Discover and return the set of plugin names to be loaded.

    Configures the plugin search paths and resolves the final set of plugins
    based on configuration settings, inclusion filters, and exclusion rules.
    Automatically includes the musicbrainz plugin when enabled in configuration.
    """
    paths = [
        str(Path(p).expanduser().absolute())
        for p in beets.config["pluginpath"].as_str_seq(split=False)
    ]
    log.debug("plugin paths: {}", paths)

    # Extend the `beetsplug` package to include the plugin paths.
    import beetsplug

    beetsplug.__path__ = paths + list(beetsplug.__path__)

    # For backwards compatibility, also support plugin paths that
    # *contain* a `beetsplug` package.
    sys.path += paths
    plugins = unique_list(beets.config["plugins"].as_str_seq())
    # TODO: Remove in v3.0.0
    if (
        "musicbrainz" not in plugins
        and "musicbrainz" in beets.config
        and beets.config["musicbrainz"].get().get("enabled")
    ):
        plugins.append("musicbrainz")

    beets.config.add({"disabled_plugins": []})
    disabled_plugins = set(beets.config["disabled_plugins"].as_str_seq())
    return [p for p in plugins if p not in disabled_plugins]


def _get_plugin(name: str) -> BeetsPlugin | None:
    """Dynamically load and instantiate a plugin class by name.

    Attempts to import the plugin module, locate the appropriate plugin class
    within it, and return an instance. Handles import failures gracefully and
    logs warnings for missing plugins or loading errors.

    Note we load the *last* plugin class found in the plugin namespace. This
    allows plugins to define helper classes that inherit from BeetsPlugin
    without those being loaded as the main plugin class.

    Returns None if the plugin could not be loaded for any reason.
    """
    try:
        try:
            namespace = import_module(f"{PLUGIN_NAMESPACE}.{name}")
        except Exception as exc:
            raise PluginImportError(name) from exc

        for obj in reversed(namespace.__dict__.values()):
            if (
                inspect.isclass(obj)
                and issubclass(obj, BeetsPlugin)
                and obj != BeetsPlugin
                and not inspect.isabstract(obj)
                # Only consider this plugin's module or submodules to avoid
                # conflicts when plugins import other BeetsPlugin classes
                and (
                    obj.__module__ == namespace.__name__
                    or obj.__module__.startswith(f"{namespace.__name__}.")
                )
            ):
                return obj()

    except Exception:
        log.warning("** error loading plugin {}", name, exc_info=True)

    return None


_instances: list[BeetsPlugin] = []


def load_plugins() -> None:
    """Initialize the plugin system by loading all configured plugins.

    Performs one-time plugin discovery and instantiation, storing loaded plugin
    instances globally. Emits a pluginload event after successful initialization
    to notify other components.
    """
    if not _instances:
        names = get_plugin_names()
        log.debug("Loading plugins: {}", ", ".join(sorted(names)))
        _instances.extend(filter(None, map(_get_plugin, names)))

        send("pluginload")


def find_plugins() -> Iterable[BeetsPlugin]:
    return _instances


# Communication with plugins.


def commands() -> list[Subcommand]:
    """Returns a list of Subcommand objects from all loaded plugins."""
    out: list[Subcommand] = []
    for plugin in find_plugins():
        out += plugin.commands()
    return out


def queries() -> dict[str, type[Query]]:
    """Returns a dict mapping prefix strings to Query subclasses all loaded
    plugins.
    """
    out: dict[str, type[Query]] = {}
    for plugin in find_plugins():
        out.update(plugin.queries())
    return out


def types(model_cls: type[AnyModel]) -> dict[str, Type]:
    """Return mapping between flex field names and types for the given model."""
    attr_name = f"{model_cls.__name__.lower()}_types"
    types: dict[str, Type] = {}
    for plugin in find_plugins():
        plugin_types = getattr(plugin, attr_name, {})
        for field in plugin_types:
            if field in types and plugin_types[field] != types[field]:
                raise PluginConflictError(
                    f"Plugin {plugin.name} defines flexible field {field} "
                    "which has already been defined with "
                    "another type."
                )
        types.update(plugin_types)
    return types


def named_queries(model_cls: type[AnyModel]) -> dict[str, FieldQueryType]:
    """Return mapping between field names and queries for the given model."""
    attr_name = f"{model_cls.__name__.lower()}_queries"
    return {
        field: query
        for plugin in find_plugins()
        for field, query in getattr(plugin, attr_name, {}).items()
    }


def notify_info_yielded(
    event: EventType,
) -> Callable[[IterF[P, Ret]], IterF[P, Ret]]:
    """Makes a generator send the event 'event' every time it yields.
    This decorator is supposed to decorate a generator, but any function
    returning an iterable should work.
    Each yielded value is passed to plugins using the 'info' parameter of
    'send'.
    """

    def decorator(func: IterF[P, Ret]) -> IterF[P, Ret]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Iterable[Ret]:
            for v in func(*args, **kwargs):
                send(event, info=v)
                yield v

        return wrapper

    return decorator


def template_funcs() -> TFuncMap[str]:
    """Get all the template functions declared by plugins as a
    dictionary.
    """
    funcs: TFuncMap[str] = {}
    for plugin in find_plugins():
        if plugin.template_funcs:
            funcs.update(plugin.template_funcs)
    return funcs


def early_import_stages() -> list[ImportStageFunc]:
    """Get a list of early import stage functions defined by plugins."""
    stages: list[ImportStageFunc] = []
    for plugin in find_plugins():
        stages += plugin.get_early_import_stages()
    return stages


def import_stages() -> list[ImportStageFunc]:
    """Get a list of import stage functions defined by plugins."""
    stages: list[ImportStageFunc] = []
    for plugin in find_plugins():
        stages += plugin.get_import_stages()
    return stages


# New-style (lazy) plugin-provided fields.

F = TypeVar("F")


def _check_conflicts_and_merge(
    plugin: BeetsPlugin, plugin_funcs: dict[str, F] | None, funcs: dict[str, F]
) -> None:
    """Check the provided template functions for conflicts and merge into funcs.

    Raises a `PluginConflictError` if a plugin defines template functions
    for fields that another plugin has already defined template functions for.
    """
    if plugin_funcs:
        if not plugin_funcs.keys().isdisjoint(funcs.keys()):
            conflicted_fields = ", ".join(plugin_funcs.keys() & funcs.keys())
            raise PluginConflictError(
                f"Plugin {plugin.name} defines template functions for "
                f"{conflicted_fields} that conflict with another plugin."
            )
        funcs.update(plugin_funcs)


def item_field_getters() -> TFuncMap[Item]:
    """Get a dictionary mapping field names to unary functions that
    compute the field's value.
    """
    funcs: TFuncMap[Item] = {}
    for plugin in find_plugins():
        _check_conflicts_and_merge(plugin, plugin.template_fields, funcs)
    return funcs


def album_field_getters() -> TFuncMap[Album]:
    """As above, for album fields."""
    funcs: TFuncMap[Album] = {}
    for plugin in find_plugins():
        _check_conflicts_and_merge(plugin, plugin.album_template_fields, funcs)
    return funcs


# Event dispatch.


def send(event: EventType, **arguments: Any) -> list[Any]:
    """Send an event to all assigned event listeners.

    `event` is the name of  the event to send, all other named arguments
    are passed along to the handlers.

    Return a list of non-None values returned from the handlers.
    """
    log.debug("Sending event: {}", event)
    return [
        r
        for handler in BeetsPlugin.listeners[event]
        if (r := handler(**arguments)) is not None
    ]


def feat_tokens(
    for_artist: bool = True, custom_words: list[str] | None = None
) -> str:
    """Return a regular expression that matches phrases like "featuring"
    that separate a main artist or a song title from secondary artists.
    The `for_artist` option determines whether the regex should be
    suitable for matching artist fields (the default) or title fields.
    """
    feat_words = ["ft", "featuring", "feat", "feat.", "ft."]
    if isinstance(custom_words, list):
        feat_words += custom_words
    if for_artist:
        feat_words += ["with", "vs", "and", "con", "&"]
    return (
        rf"(?<=[\s(\[])(?:{'|'.join(re.escape(x) for x in feat_words)})(?=\s)"
    )


def apply_item_changes(
    lib: Library, item: Item, move: bool, pretend: bool, write: bool
) -> None:
    """Store, move, and write the item according to the arguments.

    :param lib: beets library.
    :param item: Item whose changes to apply.
    :param move: Move the item if it's in the library.
    :param pretend: Return without moving, writing, or storing the item's
        metadata.
    :param write: Write the item's metadata to its media file.
    """
    if pretend:
        return

    from beets import util

    # Move the item if it's in the library.
    if move and lib.directory in util.ancestry(item.path):
        item.move(with_album=False)

    if write:
        item.try_write()

    item.store()
