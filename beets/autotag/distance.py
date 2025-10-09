from __future__ import annotations

import datetime
import re
from functools import cache, total_ordering
from typing import TYPE_CHECKING, Any

from jellyfish import levenshtein_distance
from unidecode import unidecode

from beets import config, metadata_plugins
from beets.util import as_string, cached_classproperty, get_most_common_tags

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from beets.library import Item

    from .hooks import AlbumInfo, TrackInfo

# Candidate distance scoring.

# Artist signals that indicate "various artists". These are used at the
# album level to determine whether a given release is likely a VA
# release and also on the track level to to remove the penalty for
# differing artists.
VA_ARTISTS = ("", "various artists", "various", "va", "unknown")

# Parameters for string distance function.
# Words that can be moved to the end of a string using a comma.
SD_END_WORDS = ["the", "a", "an"]
# Reduced weights for certain portions of the string.
SD_PATTERNS = [
    (r"^the ", 0.1),
    (r"[\[\(]?(ep|single)[\]\)]?", 0.0),
    (r"[\[\(]?(featuring|feat|ft)[\. :].+", 0.1),
    (r"\(.*?\)", 0.3),
    (r"\[.*?\]", 0.3),
    (r"(, )?(pt\.|part) .+", 0.2),
]
# Replacements to use before testing distance.
SD_REPLACE = [
    (r"&", "and"),
]


def _string_dist_basic(str1: str, str2: str) -> float:
    """Basic edit distance between two strings, ignoring
    non-alphanumeric characters and case. Comparisons are based on a
    transliteration/lowering to ASCII characters. Normalized by string
    length.
    """
    assert isinstance(str1, str)
    assert isinstance(str2, str)
    str1 = as_string(unidecode(str1))
    str2 = as_string(unidecode(str2))
    str1 = re.sub(r"[^a-z0-9]", "", str1.lower())
    str2 = re.sub(r"[^a-z0-9]", "", str2.lower())
    if not str1 and not str2:
        return 0.0
    return levenshtein_distance(str1, str2) / float(max(len(str1), len(str2)))


def string_dist(str1: str | None, str2: str | None) -> float:
    """Gives an "intuitive" edit distance between two strings. This is
    an edit distance, normalized by the string length, with a number of
    tweaks that reflect intuition about text.
    """
    if str1 is None and str2 is None:
        return 0.0
    if str1 is None or str2 is None:
        return 1.0

    str1 = str1.lower()
    str2 = str2.lower()

    # Don't penalize strings that move certain words to the end. For
    # example, "the something" should be considered equal to
    # "something, the".
    for word in SD_END_WORDS:
        if str1.endswith(f", {word}"):
            str1 = f"{word} {str1[: -len(word) - 2]}"
        if str2.endswith(f", {word}"):
            str2 = f"{word} {str2[: -len(word) - 2]}"

    # Perform a couple of basic normalizing substitutions.
    for pat, repl in SD_REPLACE:
        str1 = re.sub(pat, repl, str1)
        str2 = re.sub(pat, repl, str2)

    # Change the weight for certain string portions matched by a set
    # of regular expressions. We gradually change the strings and build
    # up penalties associated with parts of the string that were
    # deleted.
    base_dist = _string_dist_basic(str1, str2)
    penalty = 0.0
    for pat, weight in SD_PATTERNS:
        # Get strings that drop the pattern.
        case_str1 = re.sub(pat, "", str1)
        case_str2 = re.sub(pat, "", str2)

        if case_str1 != str1 or case_str2 != str2:
            # If the pattern was present (i.e., it is deleted in the
            # the current case), recalculate the distances for the
            # modified strings.
            case_dist = _string_dist_basic(case_str1, case_str2)
            case_delta = max(0.0, base_dist - case_dist)
            if case_delta == 0.0:
                continue

            # Shift our baseline strings down (to avoid rematching the
            # same part of the string) and add a scaled distance
            # amount to the penalties.
            str1 = case_str1
            str2 = case_str2
            base_dist = case_dist
            penalty += weight * case_delta

    return base_dist + penalty


@total_ordering
class Distance:
    """Keeps track of multiple distance penalties. Provides a single
    weighted distance for all penalties as well as a weighted distance
    for each individual penalty.
    """

    def __init__(self) -> None:
        self._penalties: dict[str, list[float]] = {}
        self.tracks: dict[TrackInfo, Distance] = {}

    @cached_classproperty
    def _weights(cls) -> dict[str, float]:
        """A dictionary from keys to floating-point weights."""
        weights_view = config["match"]["distance_weights"]
        weights = {}
        for key in weights_view.keys():
            weights[key] = weights_view[key].as_number()
        return weights

    # Access the components and their aggregates.

    @property
    def distance(self) -> float:
        """Return a weighted and normalized distance across all
        penalties.
        """
        dist_max = self.max_distance
        if dist_max:
            return self.raw_distance / self.max_distance
        return 0.0

    @property
    def max_distance(self) -> float:
        """Return the maximum distance penalty (normalization factor)."""
        dist_max = 0.0
        for key, penalty in self._penalties.items():
            dist_max += len(penalty) * self._weights[key]
        return dist_max

    @property
    def raw_distance(self) -> float:
        """Return the raw (denormalized) distance."""
        dist_raw = 0.0
        for key, penalty in self._penalties.items():
            dist_raw += sum(penalty) * self._weights[key]
        return dist_raw

    def items(self) -> list[tuple[str, float]]:
        """Return a list of (key, dist) pairs, with `dist` being the
        weighted distance, sorted from highest to lowest. Does not
        include penalties with a zero value.
        """
        list_ = []
        for key in self._penalties:
            dist = self[key]
            if dist:
                list_.append((key, dist))
        # Convert distance into a negative float we can sort items in
        # ascending order (for keys, when the penalty is equal) and
        # still get the items with the biggest distance first.
        return sorted(
            list_, key=lambda key_and_dist: (-key_and_dist[1], key_and_dist[0])
        )

    def __hash__(self) -> int:
        return id(self)

    def __eq__(self, other) -> bool:
        return self.distance == other

    # Behave like a float.

    def __lt__(self, other) -> bool:
        return self.distance < other

    def __float__(self) -> float:
        return self.distance

    def __sub__(self, other) -> float:
        return self.distance - other

    def __rsub__(self, other) -> float:
        return other - self.distance

    def __str__(self) -> str:
        return f"{self.distance:.2f}"

    # Behave like a dict.

    def __getitem__(self, key) -> float:
        """Returns the weighted distance for a named penalty."""
        dist = sum(self._penalties[key]) * self._weights[key]
        dist_max = self.max_distance
        if dist_max:
            return dist / dist_max
        return 0.0

    def __iter__(self) -> Iterator[tuple[str, float]]:
        return iter(self.items())

    def __len__(self) -> int:
        return len(self.items())

    def keys(self) -> list[str]:
        return [key for key, _ in self.items()]

    def update(self, dist: Distance):
        """Adds all the distance penalties from `dist`."""
        if not isinstance(dist, Distance):
            raise ValueError(
                f"`dist` must be a Distance object, not {type(dist)}"
            )
        for key, penalties in dist._penalties.items():
            self._penalties.setdefault(key, []).extend(penalties)

    # Adding components.

    def _eq(self, value1: re.Pattern[str] | Any, value2: Any) -> bool:
        """Returns True if `value1` is equal to `value2`. `value1` may
        be a compiled regular expression, in which case it will be
        matched against `value2`.
        """
        if isinstance(value1, re.Pattern):
            return bool(value1.match(value2))
        return value1 == value2

    def add(self, key: str, dist: float):
        """Adds a distance penalty. `key` must correspond with a
        configured weight setting. `dist` must be a float between 0.0
        and 1.0, and will be added to any existing distance penalties
        for the same key.
        """
        if not 0.0 <= dist <= 1.0:
            raise ValueError(f"`dist` must be between 0.0 and 1.0, not {dist}")
        self._penalties.setdefault(key, []).append(dist)

    def add_equality(
        self,
        key: str,
        value: Any,
        options: list[Any] | tuple[Any, ...] | Any,
    ):
        """Adds a distance penalty of 1.0 if `value` doesn't match any
        of the values in `options`. If an option is a compiled regular
        expression, it will be considered equal if it matches against
        `value`.
        """
        if not isinstance(options, (list, tuple)):
            options = [options]
        for opt in options:
            if self._eq(opt, value):
                dist = 0.0
                break
        else:
            dist = 1.0
        self.add(key, dist)

    def add_expr(self, key: str, expr: bool):
        """Adds a distance penalty of 1.0 if `expr` evaluates to True,
        or 0.0.
        """
        if expr:
            self.add(key, 1.0)
        else:
            self.add(key, 0.0)

    def add_number(self, key: str, number1: int, number2: int):
        """Adds a distance penalty of 1.0 for each number of difference
        between `number1` and `number2`, or 0.0 when there is no
        difference. Use this when there is no upper limit on the
        difference between the two numbers.
        """
        diff = abs(number1 - number2)
        if diff:
            for i in range(diff):
                self.add(key, 1.0)
        else:
            self.add(key, 0.0)

    def add_priority(
        self,
        key: str,
        value: Any,
        options: list[Any] | tuple[Any, ...] | Any,
    ):
        """Adds a distance penalty that corresponds to the position at
        which `value` appears in `options`. A distance penalty of 0.0
        for the first option, or 1.0 if there is no matching option. If
        an option is a compiled regular expression, it will be
        considered equal if it matches against `value`.
        """
        if not isinstance(options, (list, tuple)):
            options = [options]
        unit = 1.0 / (len(options) or 1)
        for i, opt in enumerate(options):
            if self._eq(opt, value):
                dist = i * unit
                break
        else:
            dist = 1.0
        self.add(key, dist)

    def add_ratio(
        self,
        key: str,
        number1: int | float,
        number2: int | float,
    ):
        """Adds a distance penalty for `number1` as a ratio of `number2`.
        `number1` is bound at 0 and `number2`.
        """
        number = float(max(min(number1, number2), 0))
        if number2:
            dist = number / number2
        else:
            dist = 0.0
        self.add(key, dist)

    def add_string(self, key: str, str1: str | None, str2: str | None):
        """Adds a distance penalty based on the edit distance between
        `str1` and `str2`.
        """
        dist = string_dist(str1, str2)
        self.add(key, dist)


@cache
def get_track_length_grace() -> float:
    """Get cached grace period for track length matching."""
    return config["match"]["track_length_grace"].as_number()


@cache
def get_track_length_max() -> float:
    """Get cached maximum track length for track length matching."""
    return config["match"]["track_length_max"].as_number()


def track_index_changed(item: Item, track_info: TrackInfo) -> bool:
    """Returns True if the item and track info index is different. Tolerates
    per disc and per release numbering.
    """
    return item.track not in (track_info.medium_index, track_info.index)


def track_distance(
    item: Item,
    track_info: TrackInfo,
    incl_artist: bool = False,
) -> Distance:
    """Determines the significance of a track metadata change. Returns a
    Distance object. `incl_artist` indicates that a distance component should
    be included for the track artist (i.e., for various-artist releases).

    ``track_length_grace`` and ``track_length_max`` configuration options are
    cached because this function is called many times during the matching
    process and their access comes with a performance overhead.
    """
    dist = Distance()

    # Length.
    if info_length := track_info.length:
        diff = abs(item.length - info_length) - get_track_length_grace()
        dist.add_ratio("track_length", diff, get_track_length_max())

    # Title.
    dist.add_string("track_title", item.title, track_info.title)

    # Artist. Only check if there is actually an artist in the track data.
    if (
        incl_artist
        and track_info.artist
        and item.artist.lower() not in VA_ARTISTS
    ):
        dist.add_string("track_artist", item.artist, track_info.artist)

    # Track index.
    if track_info.index and item.track:
        dist.add_expr("track_index", track_index_changed(item, track_info))

    # Track ID.
    if item.mb_trackid:
        dist.add_expr("track_id", item.mb_trackid != track_info.track_id)

    # Penalize mismatching disc numbers.
    if track_info.medium and item.disc:
        dist.add_expr("medium", item.disc != track_info.medium)

    # Plugins.
    if (actual := track_info.data_source) != item.get("data_source"):
        dist.add("data_source", metadata_plugins.get_penalty(actual))

    return dist


def distance(
    items: Sequence[Item],
    album_info: AlbumInfo,
    mapping: dict[Item, TrackInfo],
) -> Distance:
    """Determines how "significant" an album metadata change would be.
    Returns a Distance object. `album_info` is an AlbumInfo object
    reflecting the album to be compared. `items` is a sequence of all
    Item objects that will be matched (order is not important).
    `mapping` is a dictionary mapping Items to TrackInfo objects; the
    keys are a subset of `items` and the values are a subset of
    `album_info.tracks`.
    """
    likelies, _ = get_most_common_tags(items)

    dist = Distance()

    # Artist, if not various.
    if not album_info.va:
        dist.add_string("artist", likelies["artist"], album_info.artist)

    # Album.
    dist.add_string("album", likelies["album"], album_info.album)

    preferred_config = config["match"]["preferred"]
    # Current or preferred media.
    if album_info.media:
        # Preferred media options.
        media_patterns: Sequence[str] = preferred_config["media"].as_str_seq()
        options = [
            re.compile(rf"(\d+x)?({pat})", re.I) for pat in media_patterns
        ]
        if options:
            dist.add_priority("media", album_info.media, options)
        # Current media.
        elif likelies["media"]:
            dist.add_equality("media", album_info.media, likelies["media"])

    # Mediums.
    if likelies["disctotal"] and album_info.mediums:
        dist.add_number("mediums", likelies["disctotal"], album_info.mediums)

    # Prefer earliest release.
    if album_info.year and preferred_config["original_year"]:
        # Assume 1889 (earliest first gramophone discs) if we don't know the
        # original year.
        original = album_info.original_year or 1889
        diff = abs(album_info.year - original)
        diff_max = abs(datetime.date.today().year - original)
        dist.add_ratio("year", diff, diff_max)
    # Year.
    elif likelies["year"] and album_info.year:
        if likelies["year"] in (album_info.year, album_info.original_year):
            # No penalty for matching release or original year.
            dist.add("year", 0.0)
        elif album_info.original_year:
            # Prefer matchest closest to the release year.
            diff = abs(likelies["year"] - album_info.year)
            diff_max = abs(
                datetime.date.today().year - album_info.original_year
            )
            dist.add_ratio("year", diff, diff_max)
        else:
            # Full penalty when there is no original year.
            dist.add("year", 1.0)

    # Preferred countries.
    country_patterns: Sequence[str] = preferred_config["countries"].as_str_seq()
    options = [re.compile(pat, re.I) for pat in country_patterns]
    if album_info.country and options:
        dist.add_priority("country", album_info.country, options)
    # Country.
    elif likelies["country"] and album_info.country:
        dist.add_string("country", likelies["country"], album_info.country)

    # Label.
    if likelies["label"] and album_info.label:
        dist.add_string("label", likelies["label"], album_info.label)

    # Catalog number.
    if likelies["catalognum"] and album_info.catalognum:
        dist.add_string(
            "catalognum", likelies["catalognum"], album_info.catalognum
        )

    # Disambiguation.
    if likelies["albumdisambig"] and album_info.albumdisambig:
        dist.add_string(
            "albumdisambig", likelies["albumdisambig"], album_info.albumdisambig
        )

    # Album ID.
    if likelies["mb_albumid"]:
        dist.add_equality(
            "album_id", likelies["mb_albumid"], album_info.album_id
        )

    # Tracks.
    dist.tracks = {}
    for item, track in mapping.items():
        dist.tracks[track] = track_distance(item, track, album_info.va)
        dist.add("tracks", dist.tracks[track].distance)

    # Missing tracks.
    for _ in range(len(album_info.tracks) - len(mapping)):
        dist.add("missing_tracks", 1.0)

    # Unmatched tracks.
    for _ in range(len(items) - len(mapping)):
        dist.add("unmatched_tracks", 1.0)

    # Plugins.
    if (data_source := album_info.data_source) != likelies["data_source"]:
        dist.add("data_source", metadata_plugins.get_penalty(data_source))
    return dist
