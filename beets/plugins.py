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
import traceback
from collections import defaultdict
from functools import wraps
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Sequence,
    TypedDict,
    TypeVar,
)

import mediafile

import beets
from beets import logging

if sys.version_info >= (3, 10):
    from typing import ParamSpec
else:
    from typing_extensions import ParamSpec


if TYPE_CHECKING:
    from collections.abc import Iterator

    from confuse import ConfigView

    from beets.autotag import AlbumInfo, Distance, TrackInfo
    from beets.dbcore import Query
    from beets.dbcore.db import FieldQueryType, SQLiteType
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
    Listener = Callable[..., None]
    IterF = Callable[P, Iterator[Ret]]


PLUGIN_NAMESPACE = "beetsplug"

# Plugins using the Last.fm API can share the same API key.
LASTFM_KEY = "2dc3914abf35f0d9c92d97d8f8e42b43"

# Global logger.
log = logging.getLogger("beets")


class PluginConflictError(Exception):
    """Indicates that the services provided by one plugin conflict with
    those of another.

    For example two plugins may define different types for flexible fields.
    """


class PluginLogFilter(logging.Filter):
    """A logging filter that identifies the plugin that emitted a log
    message.
    """

    def __init__(self, plugin):
        self.prefix = f"{plugin.name}: "

    def filter(self, record):
        if hasattr(record.msg, "msg") and isinstance(record.msg.msg, str):
            # A _LogMessage from our hacked-up Logging replacement.
            record.msg.msg = self.prefix + record.msg.msg
        elif isinstance(record.msg, str):
            record.msg = self.prefix + record.msg
        return True


# Managing the plugins themselves.


class BeetsPlugin:
    """The base class for all beets plugins. Plugins provide
    functionality by defining a subclass of BeetsPlugin and overriding
    the abstract methods defined here.
    """

    name: str
    config: ConfigView
    early_import_stages: list[ImportStageFunc]
    import_stages: list[ImportStageFunc]

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

    def track_distance(
        self,
        item: Item,
        info: TrackInfo,
    ) -> Distance:
        """Should return a Distance object to be added to the
        distance for every track comparison.
        """
        from beets.autotag.hooks import Distance

        return Distance()

    def album_distance(
        self,
        items: list[Item],
        album_info: AlbumInfo,
        mapping: dict[Item, TrackInfo],
    ) -> Distance:
        """Should return a Distance object to be added to the
        distance for every album-level comparison.
        """
        from beets.autotag.hooks import Distance

        return Distance()

    def candidates(
        self,
        items: list[Item],
        artist: str,
        album: str,
        va_likely: bool,
        extra_tags: dict[str, Any] | None = None,
    ) -> Iterator[AlbumInfo]:
        """Return :py:class:`AlbumInfo` candidates that match the given album.

        :param items: List of items in the album
        :param artist: Album artist
        :param album: Album name
        :param va_likely: Whether the album is likely to be by various artists
        :param extra_tags: is a an optional dictionary of extra tags to search.
            Only relevant to :py:class:`MusicBrainzPlugin` autotagger and can be
            ignored by other plugins
        """
        yield from ()

    def item_candidates(
        self, item: Item, artist: str, title: str
    ) -> Iterator[TrackInfo]:
        """Return :py:class:`TrackInfo` candidates that match the given track.

        :param item: Track item
        :param artist: Track artist
        :param title: Track title
        """
        yield from ()

    def album_for_id(self, album_id: str) -> AlbumInfo | None:
        """Return an AlbumInfo object or None if no matching release was
        found.
        """
        return None

    def track_for_id(self, track_id: str) -> TrackInfo | None:
        """Return a TrackInfo object or None if no matching release was
        found.
        """
        return None

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

    _raw_listeners: dict[str, list[Listener]] | None = None
    listeners: dict[str, list[Listener]] | None = None

    def register_listener(self, event: str, func: Listener) -> None:
        """Add a function as a listener for the specified event."""
        wrapped_func = self._set_log_level_and_params(logging.WARNING, func)

        cls = self.__class__

        if cls.listeners is None or cls._raw_listeners is None:
            cls._raw_listeners = defaultdict(list)
            cls.listeners = defaultdict(list)
        if func not in cls._raw_listeners[event]:
            cls._raw_listeners[event].append(func)
            cls.listeners[event].append(wrapped_func)

    template_funcs: TFuncMap[str] | None = None
    template_fields: TFuncMap[Item] | None = None
    album_template_fields: TFuncMap[Album] | None = None

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


_classes: set[type[BeetsPlugin]] = set()


def load_plugins(names: Sequence[str] = ()) -> None:
    """Imports the modules for a sequence of plugin names. Each name
    must be the name of a Python module under the "beetsplug" namespace
    package in sys.path; the module indicated should contain the
    BeetsPlugin subclasses desired.
    """
    for name in names:
        modname = f"{PLUGIN_NAMESPACE}.{name}"
        try:
            try:
                namespace = __import__(modname, None, None)
            except ImportError as exc:
                # Again, this is hacky:
                if exc.args[0].endswith(" " + name):
                    log.warning("** plugin {0} not found", name)
                else:
                    raise
            else:
                for obj in getattr(namespace, name).__dict__.values():
                    if (
                        isinstance(obj, type)
                        and issubclass(obj, BeetsPlugin)
                        and obj != BeetsPlugin
                        and obj != MetadataSourcePlugin
                        and obj not in _classes
                    ):
                        _classes.add(obj)

        except Exception:
            log.warning(
                "** error loading plugin {}:\n{}",
                name,
                traceback.format_exc(),
            )


_instances: dict[type[BeetsPlugin], BeetsPlugin] = {}


def find_plugins() -> list[BeetsPlugin]:
    """Returns a list of BeetsPlugin subclass instances from all
    currently loaded beets plugins. Loads the default plugin set
    first.
    """
    if _instances:
        # After the first call, use cached instances for performance reasons.
        # See https://github.com/beetbox/beets/pull/3810
        return list(_instances.values())

    load_plugins()
    plugins = []
    for cls in _classes:
        # Only instantiate each plugin class once.
        if cls not in _instances:
            _instances[cls] = cls()
        plugins.append(_instances[cls])
    return plugins


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


def types(model_cls: type[AnyModel]) -> dict[str, type[SQLiteType]]:
    # Gives us `item_types` and `album_types`
    attr_name = f"{model_cls.__name__.lower()}_types"
    types: dict[str, type[SQLiteType]] = {}
    for plugin in find_plugins():
        plugin_types = getattr(plugin, attr_name, {})
        for field in plugin_types:
            if field in types and plugin_types[field] != types[field]:
                raise PluginConflictError(
                    "Plugin {} defines flexible field {} "
                    "which has already been defined with "
                    "another type.".format(plugin.name, field)
                )
        types.update(plugin_types)
    return types


def named_queries(model_cls: type[AnyModel]) -> dict[str, FieldQueryType]:
    # Gather `item_queries` and `album_queries` from the plugins.
    attr_name = f"{model_cls.__name__.lower()}_queries"
    queries: dict[str, FieldQueryType] = {}
    for plugin in find_plugins():
        plugin_queries = getattr(plugin, attr_name, {})
        queries.update(plugin_queries)
    return queries


def track_distance(item: Item, info: TrackInfo) -> Distance:
    """Gets the track distance calculated by all loaded plugins.
    Returns a Distance object.
    """
    from beets.autotag.hooks import Distance

    dist = Distance()
    for plugin in find_plugins():
        dist.update(plugin.track_distance(item, info))
    return dist


def album_distance(
    items: list[Item],
    album_info: AlbumInfo,
    mapping: dict[Item, TrackInfo],
) -> Distance:
    """Returns the album distance calculated by plugins."""
    from beets.autotag.hooks import Distance

    dist = Distance()
    for plugin in find_plugins():
        dist.update(plugin.album_distance(items, album_info, mapping))
    return dist


def notify_info_yielded(event: str) -> Callable[[IterF[P, Ret]], IterF[P, Ret]]:
    """Makes a generator send the event 'event' every time it yields.
    This decorator is supposed to decorate a generator, but any function
    returning an iterable should work.
    Each yielded value is passed to plugins using the 'info' parameter of
    'send'.
    """

    def decorator(generator: IterF[P, Ret]) -> IterF[P, Ret]:
        def decorated(*args: P.args, **kwargs: P.kwargs) -> Iterator[Ret]:
            for v in generator(*args, **kwargs):
                send(event, info=v)
                yield v

        return decorated

    return decorator


@notify_info_yielded("albuminfo_received")
def candidates(*args, **kwargs) -> Iterator[AlbumInfo]:
    """Return matching album candidates from all plugins."""
    for plugin in find_plugins():
        yield from plugin.candidates(*args, **kwargs)


@notify_info_yielded("trackinfo_received")
def item_candidates(*args, **kwargs) -> Iterator[TrackInfo]:
    """Return matching track candidates from all plugins."""
    for plugin in find_plugins():
        yield from plugin.item_candidates(*args, **kwargs)


def album_for_id(_id: str) -> AlbumInfo | None:
    """Get AlbumInfo object for the given ID string.

    A single ID can yield just a single album, so we return the first match.
    """
    for plugin in find_plugins():
        if info := plugin.album_for_id(_id):
            send("albuminfo_received", info=info)
            return info

    return None


def track_for_id(_id: str) -> TrackInfo | None:
    """Get TrackInfo object for the given ID string.

    A single ID can yield just a single track, so we return the first match.
    """
    for plugin in find_plugins():
        if info := plugin.track_for_id(_id):
            send("trackinfo_received", info=info)
            return info

    return None


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


def event_handlers() -> dict[str, list[Listener]]:
    """Find all event handlers from plugins as a dictionary mapping
    event names to sequences of callables.
    """
    all_handlers: dict[str, list[Listener]] = defaultdict(list)
    for plugin in find_plugins():
        if plugin.listeners:
            for event, handlers in plugin.listeners.items():
                all_handlers[event] += handlers
    return all_handlers


def send(event: str, **arguments: Any) -> list[Any]:
    """Send an event to all assigned event listeners.

    `event` is the name of  the event to send, all other named arguments
    are passed along to the handlers.

    Return a list of non-None values returned from the handlers.
    """
    log.debug("Sending event: {0}", event)
    results: list[Any] = []
    for handler in event_handlers()[event]:
        result = handler(**arguments)
        if result is not None:
            results.append(result)
    return results


def feat_tokens(for_artist: bool = True) -> str:
    """Return a regular expression that matches phrases like "featuring"
    that separate a main artist or a song title from secondary artists.
    The `for_artist` option determines whether the regex should be
    suitable for matching artist fields (the default) or title fields.
    """
    feat_words = ["ft", "featuring", "feat", "feat.", "ft."]
    if for_artist:
        feat_words += ["with", "vs", "and", "con", "&"]
    return r"(?<=[\s(\[])(?:{})(?=\s)".format(
        "|".join(re.escape(x) for x in feat_words)
    )


def sanitize_choices(
    choices: Sequence[str], choices_all: Sequence[str]
) -> list[str]:
    """Clean up a stringlist configuration attribute: keep only choices
    elements present in choices_all, remove duplicate elements, expand '*'
    wildcard while keeping original stringlist order.
    """
    seen: set[str] = set()
    others = [x for x in choices_all if x not in choices]
    res: list[str] = []
    for s in choices:
        if s not in seen:
            if s in list(choices_all):
                res.append(s)
            elif s == "*":
                res.extend(others)
        seen.add(s)
    return res


def sanitize_pairs(
    pairs: Sequence[tuple[str, str]], pairs_all: Sequence[tuple[str, str]]
) -> list[tuple[str, str]]:
    """Clean up a single-element mapping configuration attribute as returned
    by Confuse's `Pairs` template: keep only two-element tuples present in
    pairs_all, remove duplicate elements, expand ('str', '*') and ('*', '*')
    wildcards while keeping the original order. Note that ('*', '*') and
    ('*', 'whatever') have the same effect.

    For example,

    >>> sanitize_pairs(
    ...     [('foo', 'baz bar'), ('key', '*'), ('*', '*')],
    ...     [('foo', 'bar'), ('foo', 'baz'), ('foo', 'foobar'),
    ...      ('key', 'value')]
    ...     )
    [('foo', 'baz'), ('foo', 'bar'), ('key', 'value'), ('foo', 'foobar')]
    """
    pairs_all: list[tuple[str, str]] = list(pairs_all)
    seen: set[tuple[str, str]] = set()
    others = [x for x in pairs_all if x not in pairs]
    res: list[tuple[str, str]] = []
    for k, values in pairs:
        for v in values.split():
            x = (k, v)
            if x in pairs_all:
                if x not in seen:
                    seen.add(x)
                    res.append(x)
            elif k == "*":
                new = [o for o in others if o not in seen]
                seen.update(new)
                res.extend(new)
            elif v == "*":
                new = [o for o in others if o not in seen and o[0] == k]
                seen.update(new)
                res.extend(new)
    return res


def get_distance(
    config: ConfigView, data_source: str, info: AlbumInfo | TrackInfo
) -> Distance:
    """Returns the ``data_source`` weight and the maximum source weight
    for albums or individual tracks.
    """
    from beets.autotag.hooks import Distance

    dist = Distance()
    if info.data_source == data_source:
        dist.add("source", config["source_weight"].as_number())
    return dist


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


class Response(TypedDict):
    """A dictionary with the response of a plugin API call.

    May be extended by plugins to include additional information, but `id`
    is required.
    """

    id: str


class RegexDict(TypedDict):
    """A dictionary containing a regex pattern and the number of the
    match group.
    """

    pattern: str
    match_group: int


R = TypeVar("R", bound=Response)


class MetadataSourcePlugin(Generic[R], BeetsPlugin, metaclass=abc.ABCMeta):
    def __init__(self):
        super().__init__()
        self.config.add({"source_weight": 0.5})

    @property
    @abc.abstractmethod
    def id_regex(self) -> RegexDict:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def data_source(self) -> str:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def search_url(self) -> str:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def album_url(self) -> str:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def track_url(self) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def _search_api(
        self,
        query_type: str,
        filters: dict[str, str] | None,
        keywords: str = "",
    ) -> Sequence[R]:
        raise NotImplementedError

    @abc.abstractmethod
    def album_for_id(self, album_id: str) -> AlbumInfo | None:
        raise NotImplementedError

    @abc.abstractmethod
    def track_for_id(self, track_id: str) -> TrackInfo | None:
        raise NotImplementedError

    @staticmethod
    def get_artist(
        artists,
        id_key: str | int = "id",
        name_key: str | int = "name",
        join_key: str | int | None = None,
    ) -> tuple[str, str | None]:
        """Returns an artist string (all artists) and an artist_id (the main
        artist) for a list of artist object dicts.

        For each artist, this function moves articles (such as 'a', 'an',
        and 'the') to the front and strips trailing disambiguation numbers. It
        returns a tuple containing the comma-separated string of all
        normalized artists and the ``id`` of the main/first artist.
        Alternatively a keyword can be used to combine artists together into a
        single string by passing the join_key argument.

        :param artists: Iterable of artist dicts or lists returned by API.
        :type artists: list[dict] or list[list]
        :param id_key: Key or index corresponding to the value of ``id`` for
            the main/first artist. Defaults to 'id'.
        :param name_key: Key or index corresponding to values of names
            to concatenate for the artist string (containing all artists).
            Defaults to 'name'.
        :param join_key: Key or index corresponding to a field containing a
            keyword to use for combining artists into a single string, for
            example "Feat.", "Vs.", "And" or similar. The default is None
            which keeps the default behaviour (comma-separated).
        :return: Normalized artist string.
        """
        artist_id = None
        artist_string = ""
        artists = list(artists)  # In case a generator was passed.
        total = len(artists)
        for idx, artist in enumerate(artists):
            if not artist_id:
                artist_id = artist[id_key]
            name = artist[name_key]
            # Strip disambiguation number.
            name = re.sub(r" \(\d+\)$", "", name)
            # Move articles to the front.
            name = re.sub(r"^(.*?), (a|an|the)$", r"\2 \1", name, flags=re.I)
            # Use a join keyword if requested and available.
            if idx < (total - 1):  # Skip joining on last.
                if join_key and artist.get(join_key, None):
                    name += f" {artist[join_key]} "
                else:
                    name += ", "
            artist_string += name

        return artist_string, artist_id

    @staticmethod
    def _get_id(url_type: str, id_: str, id_regex: RegexDict) -> str | None:
        """Parse an ID from its URL if necessary.

        :param url_type: Type of URL. Either 'album' or 'track'.
        :param id_: Album/track ID or URL.
        :param id_regex: A dictionary containing a regular expression
            extracting an ID from an URL (if it's not an ID already) in
            'pattern' and the number of the match group in 'match_group'.
        :return: Album/track ID.
        """
        log.debug("Extracting {} ID from '{}'", url_type, id_)
        match = re.search(id_regex["pattern"].format(url_type), str(id_))
        if match:
            id_ = match.group(id_regex["match_group"])
            if id_:
                return id_
        return None

    def candidates(
        self,
        items: list[Item],
        artist: str,
        album: str,
        va_likely: bool,
        extra_tags: dict[str, Any] | None = None,
    ) -> Iterator[AlbumInfo]:
        query_filters = {"album": album}
        if not va_likely:
            query_filters["artist"] = artist
        for result in self._search_api("album", query_filters):
            if info := self.album_for_id(result["id"]):
                yield info

    def item_candidates(
        self, item: Item, artist: str, title: str
    ) -> Iterator[TrackInfo]:
        for result in self._search_api(
            "track", {"artist": artist}, keywords=title
        ):
            if info := self.track_for_id(result["id"]):
                yield info

    def album_distance(
        self,
        items: list[Item],
        album_info: AlbumInfo,
        mapping: dict[Item, TrackInfo],
    ) -> Distance:
        return get_distance(
            data_source=self.data_source, info=album_info, config=self.config
        )

    def track_distance(self, item: Item, info: TrackInfo) -> Distance:
        return get_distance(
            data_source=self.data_source, info=info, config=self.config
        )
