# This file is part of beets.
# Copyright 2025, Alexis Sarda-Espinosa.
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

"""Adds pseudo-releases from MusicBrainz as candidates during import."""

from __future__ import annotations

import itertools
import traceback
from copy import deepcopy
from typing import TYPE_CHECKING, Any

import mediafile
import musicbrainzngs
from typing_extensions import override

from beets import config
from beets.autotag.distance import Distance, distance
from beets.autotag.hooks import AlbumInfo
from beets.autotag.match import assign_items
from beets.plugins import find_plugins
from beets.util.id_extractors import extract_release_id
from beetsplug.musicbrainz import (
    RELEASE_INCLUDES,
    MusicBrainzAPIError,
    MusicBrainzPlugin,
    _merge_pseudo_and_actual_album,
    _preferred_alias,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from beets.autotag import AlbumMatch
    from beets.library import Item
    from beetsplug._typing import JSONDict

_STATUS_PSEUDO = "Pseudo-Release"


class MusicBrainzPseudoReleasePlugin(MusicBrainzPlugin):
    def __init__(self) -> None:
        super().__init__()

        self._release_getter = musicbrainzngs.get_release_by_id

        self.config.add(
            {
                "scripts": [],
                "custom_tags_only": False,
                "album_custom_tags": {
                    "album_transl": "album",
                    "album_artist_transl": "artist",
                },
                "track_custom_tags": {
                    "title_transl": "title",
                    "artist_transl": "artist",
                },
            }
        )

        self._scripts = self.config["scripts"].as_str_seq()
        self._log.debug("Desired scripts: {0}", self._scripts)

        album_custom_tags = self.config["album_custom_tags"].get().keys()
        track_custom_tags = self.config["track_custom_tags"].get().keys()
        self._log.debug(
            "Custom tags for albums and tracks: {0} + {1}",
            album_custom_tags,
            track_custom_tags,
        )
        for custom_tag in album_custom_tags | track_custom_tags:
            if not isinstance(custom_tag, str):
                continue

            media_field = mediafile.MediaField(
                mediafile.MP3DescStorageStyle(custom_tag),
                mediafile.MP4StorageStyle(
                    f"----:com.apple.iTunes:{custom_tag}"
                ),
                mediafile.StorageStyle(custom_tag),
                mediafile.ASFStorageStyle(custom_tag),
            )
            try:
                self.add_media_field(custom_tag, media_field)
            except ValueError:
                # ignore errors due to duplicates
                pass

        self.register_listener("pluginload", self._on_plugins_loaded)
        self.register_listener("album_matched", self._adjust_final_album_match)

    # noinspection PyMethodMayBeStatic
    def _on_plugins_loaded(self):
        for plugin in find_plugins():
            if isinstance(plugin, MusicBrainzPlugin) and not isinstance(
                plugin, MusicBrainzPseudoReleasePlugin
            ):
                raise RuntimeError(
                    "The musicbrainz plugin should not be enabled together with"
                    " the mbpseudo plugin"
                )

    @override
    def candidates(
        self,
        items: Sequence[Item],
        artist: str,
        album: str,
        va_likely: bool,
    ) -> Iterable[AlbumInfo]:
        if len(self._scripts) == 0:
            yield from super().candidates(items, artist, album, va_likely)
        else:
            for album_info in super().candidates(
                items, artist, album, va_likely
            ):
                if isinstance(album_info, PseudoAlbumInfo):
                    self._log.debug(
                        "Using {0} release for distance calculations for album {1}",
                        album_info.determine_best_ref(items),
                        album_info.album_id,
                    )
                    yield album_info  # first yield pseudo to give it priority
                    yield album_info.get_official_release()
                else:
                    yield album_info

    @override
    def album_info(self, release: JSONDict) -> AlbumInfo:
        official_release = super().album_info(release)

        if release.get("status") == _STATUS_PSEUDO:
            return official_release
        elif pseudo_release_ids := self._intercept_mb_release(release):
            album_id = self._extract_id(pseudo_release_ids[0])
            try:
                raw_pseudo_release = self._release_getter(
                    album_id, RELEASE_INCLUDES
                )["release"]
                pseudo_release = super().album_info(raw_pseudo_release)

                if self.config["custom_tags_only"].get(bool):
                    self._replace_artist_with_alias(
                        raw_pseudo_release, pseudo_release
                    )
                    self._add_custom_tags(official_release, pseudo_release)
                    return official_release
                else:
                    return PseudoAlbumInfo(
                        pseudo_release=_merge_pseudo_and_actual_album(
                            pseudo_release, official_release
                        ),
                        official_release=official_release,
                    )
            except musicbrainzngs.MusicBrainzError as exc:
                raise MusicBrainzAPIError(
                    exc,
                    "get pseudo-release by ID",
                    album_id,
                    traceback.format_exc(),
                )
        else:
            return official_release

    def _intercept_mb_release(self, data: JSONDict) -> list[str]:
        album_id = data["id"] if "id" in data else None
        if self._has_desired_script(data) or not isinstance(album_id, str):
            return []

        return [
            pr_id
            for rel in data.get("release-relation-list", [])
            if (pr_id := self._wanted_pseudo_release_id(album_id, rel))
            is not None
        ]

    def _has_desired_script(self, release: JSONDict) -> bool:
        if len(self._scripts) == 0:
            return False
        elif script := release.get("text-representation", {}).get("script"):
            return script in self._scripts
        else:
            return False

    def _wanted_pseudo_release_id(
        self,
        album_id: str,
        relation: JSONDict,
    ) -> str | None:
        if (
            len(self._scripts) == 0
            or relation.get("type", "") != "transl-tracklisting"
            or relation.get("direction", "") != "forward"
            or "release" not in relation
        ):
            return None

        release = relation["release"]
        if "id" in release and self._has_desired_script(release):
            self._log.debug(
                "Adding pseudo-release {0} for main release {1}",
                release["id"],
                album_id,
            )
            return release["id"]
        else:
            return None

    def _replace_artist_with_alias(
        self,
        raw_pseudo_release: JSONDict,
        pseudo_release: AlbumInfo,
    ):
        """Use the pseudo-release's language to search for artist
        alias if the user hasn't configured import languages."""

        if len(config["import"]["languages"].as_str_seq()) > 0:
            return

        lang = raw_pseudo_release.get("text-representation", {}).get("language")
        artist_credits = raw_pseudo_release.get("release-group", {}).get(
            "artist-credit", []
        )
        aliases = [
            artist_credit.get("artist", {}).get("alias-list", [])
            for artist_credit in artist_credits
        ]

        if lang and len(lang) >= 2 and len(aliases) > 0:
            locale = lang[0:2]
            aliases_flattened = list(itertools.chain.from_iterable(aliases))
            self._log.debug(
                "Using locale '{0}' to search aliases {1}",
                locale,
                aliases_flattened,
            )
            if alias_dict := _preferred_alias(aliases_flattened, [locale]):
                if alias := alias_dict.get("alias"):
                    self._log.debug("Got alias '{0}'", alias)
                    pseudo_release.artist = alias
                    for track in pseudo_release.tracks:
                        track.artist = alias

    def _add_custom_tags(
        self,
        official_release: AlbumInfo,
        pseudo_release: AlbumInfo,
    ):
        for tag_key, pseudo_key in (
            self.config["album_custom_tags"].get().items()
        ):
            official_release[tag_key] = pseudo_release[pseudo_key]

        track_custom_tags = self.config["track_custom_tags"].get().items()
        for track, pseudo_track in zip(
            official_release.tracks, pseudo_release.tracks
        ):
            for tag_key, pseudo_key in track_custom_tags:
                track[tag_key] = pseudo_track[pseudo_key]

    def _adjust_final_album_match(self, match: AlbumMatch):
        album_info = match.info
        if isinstance(album_info, PseudoAlbumInfo):
            self._log.debug(
                "Switching {0} to pseudo-release source for final proposal",
                album_info.album_id,
            )
            album_info.use_pseudo_as_ref()
            mapping = match.mapping
            new_mappings, _, _ = assign_items(
                list(mapping.keys()), album_info.tracks
            )
            mapping.update(new_mappings)

        if album_info.data_source == self.data_source:
            album_info.data_source = "MusicBrainz"

    @override
    def _extract_id(self, url: str) -> str | None:
        return extract_release_id("MusicBrainz", url)


class PseudoAlbumInfo(AlbumInfo):
    """This is a not-so-ugly hack.

    We want the pseudo-release to result in a distance that is lower or equal to that of
    the official release, otherwise it won't qualify as a good candidate. However, if
    the input is in a script that's different from the pseudo-release (and we want to
    translate/transliterate it in the library), it will receive unwanted penalties.

    This class is essentially a view of the ``AlbumInfo`` of both official and
    pseudo-releases, where it's possible to change the details that are exposed to other
    parts of the auto-tagger, enabling a "fair" distance calculation based on the
    current input's script but still preferring the translation/transliteration in the
    final proposal.
    """

    def __init__(
        self,
        pseudo_release: AlbumInfo,
        official_release: AlbumInfo,
        **kwargs,
    ):
        super().__init__(pseudo_release.tracks, **kwargs)
        self.__dict__["_pseudo_source"] = True
        self.__dict__["_official_release"] = official_release
        for k, v in pseudo_release.items():
            if k not in kwargs:
                self[k] = v

    def get_official_release(self) -> AlbumInfo:
        return self.__dict__["_official_release"]

    def determine_best_ref(self, items: Sequence[Item]) -> str:
        self.use_pseudo_as_ref()
        pseudo_dist = self._compute_distance(items)

        self.use_official_as_ref()
        official_dist = self._compute_distance(items)

        if official_dist < pseudo_dist:
            self.use_official_as_ref()
            return "official"
        else:
            self.use_pseudo_as_ref()
            return "pseudo"

    def _compute_distance(self, items: Sequence[Item]) -> Distance:
        mapping, _, _ = assign_items(items, self.tracks)
        return distance(items, self, mapping)

    def use_pseudo_as_ref(self):
        self.__dict__["_pseudo_source"] = True

    def use_official_as_ref(self):
        self.__dict__["_pseudo_source"] = False

    def __getattr__(self, attr: str) -> Any:
        # ensure we don't duplicate an official release's id, always return pseudo's
        if self.__dict__["_pseudo_source"] or attr == "album_id":
            return super().__getattr__(attr)
        else:
            return self.__dict__["_official_release"].__getattr__(attr)

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)

        memo[id(self)] = result
        result.__dict__.update(self.__dict__)
        for k, v in self.items():
            result[k] = deepcopy(v, memo)

        return result
