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

import itertools
from typing import Iterable, Sequence

from typing_extensions import override

import beetsplug.musicbrainz as mbplugin  # avoid implicit loading of main plugin
from beets.autotag import AlbumInfo, Distance
from beets.autotag.distance import distance
from beets.autotag.hooks import V, TrackInfo
from beets.autotag.match import assign_items
from beets.library import Item
from beets.metadata_plugins import MetadataSourcePlugin
from beets.plugins import find_plugins
from beetsplug._typing import JSONDict


class MusicBrainzPseudoReleasePlugin(MetadataSourcePlugin):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config.add({"scripts": [], "include_official_releases": False})
        self._scripts = self.config["scripts"].as_str_seq()
        self._mb = mbplugin.MusicBrainzPlugin()
        self._pseudo_release_ids: dict[str, list[str]] = {}
        self._intercepted_candidates: dict[str, AlbumInfo] = {}

        self.register_listener("mb_album_extract", self._intercept_mb_releases)
        self.register_listener(
            "albuminfo_received", self._intercept_mb_candidates
        )

        self._log.debug("Desired scripts: {0}", self._scripts)

    def _intercept_mb_releases(self, data: JSONDict):
        album_id = data["id"] if ("id" in data) else None
        if (
            not isinstance(album_id, str)
            or album_id in self._pseudo_release_ids
        ):
            return None

        pseudo_release_ids = (
            self._wanted_pseudo_release_id(rel)
            for rel in data.get("release-relation-list", [])
        )
        pseudo_release_ids = [
            rel for rel in pseudo_release_ids if rel is not None
        ]

        if len(pseudo_release_ids) > 0:
            self._log.debug("Intercepted release with album id {0}", album_id)
            self._pseudo_release_ids[album_id] = pseudo_release_ids

        return None

    def _wanted_pseudo_release_id(
        self,
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
        script = release.get("text-representation", {}).get(
            "script", self._scripts[0]
        )

        if "id" in release and script in self._scripts:
            return release["id"]
        else:
            return None

    def _intercept_mb_candidates(self, info: AlbumInfo):
        if (
            not isinstance(info, PseudoAlbumInfo)
            and info.album_id in self._pseudo_release_ids
            and info.album_id not in self._intercepted_candidates
        ):
            self._log.debug(
                "Intercepted candidate with album id {0.album_id}", info
            )
            self._intercepted_candidates[info.album_id] = info.copy()

    def candidates(
        self,
        items: Sequence[Item],
        artist: str,
        album: str,
        va_likely: bool,
    ) -> Iterable[AlbumInfo]:
        if len(self._scripts) == 0:
            return []

        try:
            item_paths = {item.path for item in items}
            official_release_id = next(
                key
                for key, info in self._intercepted_candidates.items()
                if "mapping" in info
                and all(
                    mapping_key.path in item_paths
                    for mapping_key in info.mapping.keys()
                )
            )
            pseudo_release_ids = self._pseudo_release_ids[official_release_id]
            self._log.debug(
                "Processing pseudo-releases for {0}: {1}",
                official_release_id,
                pseudo_release_ids,
            )
        except StopIteration:
            official_release_id = None
            pseudo_release_ids = []

        if official_release_id is not None:
            pseudo_releases = self._get_pseudo_releases(
                items, official_release_id, pseudo_release_ids
            )
            del self._pseudo_release_ids[official_release_id]
            del self._intercepted_candidates[official_release_id]
            return pseudo_releases

        if any(
            isinstance(plugin, mbplugin.MusicBrainzPlugin)
            for plugin in find_plugins()
        ):
            self._log.debug("No releases found by main MusicBrainz plugin")
            return []

        # musicbrainz plugin isn't enabled
        self._log.debug("Searching for official releases")
        official_candidates = list(
            self._mb.candidates(items, artist, album, va_likely)
        )

        recursion = self._mb_plugin_simulation_matched(
            items, official_candidates
        )

        if not self.config.get().get("include_official_releases"):
            official_candidates = []

        if recursion:
            return itertools.chain(
                self.candidates(items, artist, album, va_likely),
                iter(official_candidates),
            )
        else:
            return iter(official_candidates)

    def _get_pseudo_releases(
        self,
        items: Sequence[Item],
        official_release_id: str,
        pseudo_release_ids: list[str],
    ) -> list[AlbumInfo]:
        pseudo_releases: list[AlbumInfo] = []
        for pri in pseudo_release_ids:
            if match := self._mb.album_for_id(pri):
                pseudo_album_info = PseudoAlbumInfo(
                    pseudo_release=match,
                    official_release=self._intercepted_candidates[
                        official_release_id
                    ],
                    data_source=self.data_source,
                )
                self._log.debug(
                    "Using {0} release for distance calculations for album {1}",
                    pseudo_album_info.determine_best_ref(items),
                    pri,
                )
                pseudo_releases.append(pseudo_album_info)
        return pseudo_releases

    def _mb_plugin_simulation_matched(
        self,
        items: Sequence[Item],
        official_candidates: list[AlbumInfo],
    ) -> bool:
        recursion = False
        for official_candidate in official_candidates:
            if official_candidate.album_id in self._pseudo_release_ids:
                self._intercept_mb_candidates(official_candidate)
            if official_candidate.album_id in self._intercepted_candidates:
                intercepted = self._intercepted_candidates[
                    official_candidate.album_id
                ]
                intercepted.mapping, _, _ = assign_items(
                    items, intercepted.tracks
                )
                recursion = True
        return recursion

    @override
    def album_distance(
        self,
        items: Sequence[Item],
        album_info: AlbumInfo,
        mapping: dict[Item, TrackInfo],
    ) -> Distance:
        if isinstance(album_info, PseudoAlbumInfo):
            if not isinstance(mapping, ImmutableMapping):
                self._log.debug(
                    "Switching {0.album_id} to pseudo-release source for final proposal",
                    album_info,
                )
                album_info.use_pseudo_as_ref()
                new_mappings, _, _ = assign_items(items, album_info.tracks)
                mapping.update(new_mappings)

        elif album_info.album_id in self._intercepted_candidates:
            self._log.debug("Storing mapping for {0.album_id}", album_info)
            self._intercepted_candidates[album_info.album_id].mapping = mapping

        return super().album_distance(items, album_info, mapping)

    def album_for_id(self, album_id: str) -> AlbumInfo | None:
        pass

    def track_for_id(self, track_id: str) -> TrackInfo | None:
        pass

    def item_candidates(
        self,
        item: Item,
        artist: str,
        title: str,
    ) -> Iterable[TrackInfo]:
        return []


class PseudoAlbumInfo(AlbumInfo):
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
        return distance(items, self, ImmutableMapping(mapping))

    def use_pseudo_as_ref(self):
        self.__dict__["_pseudo_source"] = True

    def use_official_as_ref(self):
        self.__dict__["_pseudo_source"] = False

    def __getattr__(self, attr: str) -> V:
        # ensure we don't duplicate an official release's id by always returning pseudo's
        if self.__dict__["_pseudo_source"] or attr == "album_id":
            return super().__getattr__(attr)
        else:
            return self.__dict__["_official_release"].__getattr__(attr)


class ImmutableMapping(dict[Item, TrackInfo]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
