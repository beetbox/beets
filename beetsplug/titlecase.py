# This file is part of beets.
# Copyright 2025, Henry Oberholtzer
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

"""Apply NYT manual of style title case rules, to text.
Title case logic is derived from the python-titlecase library.
Provides a template function and a tag modification function."""

import re
from typing import Optional

from titlecase import titlecase

from beets import ui
from beets.autotag.hooks import AlbumInfo, Info
from beets.importer import ImportSession, ImportTask
from beets.library import Item
from beets.plugins import BeetsPlugin

__author__ = "henryoberholtzer@gmail.com"
__version__ = "1.0"


class TitlecasePlugin(BeetsPlugin):
    preserve: dict[str, str] = {}
    preserve_phrases: dict[str, re.Pattern[str]] = {}
    force_lowercase: bool = True
    fields_to_process: set[str] = set()
    the_artist: bool = True
    the_artist_regexp = re.compile(r"\bthe\b")

    def __init__(self) -> None:
        super().__init__()

        # Register template function
        self.template_funcs["titlecase"] = self.titlecase  # type: ignore

        self.config.add(
            {
                "auto": True,
                "preserve": [],
                "fields": [],
                "replace": [],
                "force_lowercase": False,
                "small_first_last": True,
                "the_artist": True,
                "after_choice": False,
            }
        )

        """
        auto - Automatically apply titlecase to new import metadata.
        preserve - Provide a list of strings with specific case requirements.
        fields - Fields to apply titlecase to.
        replace - List of pairs, first is the target, second is the replacement
        force_lowercase - Lowercases the string before titlecasing.
        small_first_last - If small characters should be cased at the start of strings.
        the_artist - If the plugin infers the field to be an artist field
        (e.g. the field contains "artist")
        It will capitalize a lowercase The, helpful for the artist names
        that start with 'The', like 'The Who' or 'The Talking Heads' when
        they are not at the start of a string. Superceded by preserved phrases.
        """

        # Register UI subcommands
        self._command = ui.Subcommand(
            "titlecase",
            help="Apply titlecasing to metadata specified in config.",
        )

        self._get_config()
        if self.config["auto"]:
            if self.config["after_choice"].get(bool):
                self.import_stages = [self.imported]
            else:
                self.register_listener(
                    "trackinfo_received", self.received_info_handler
                )
                self.register_listener(
                    "albuminfo_received", self.received_info_handler
                )

    def _get_config(self):
        self.force_lowercase = self.config["force_lowercase"].get(bool)
        self.replace = self.config["replace"].as_pairs()
        self.the_artist = self.config["the_artist"].get(bool)
        self._preserve_words(self.config["preserve"].as_str_seq())
        self._initialize_fields(
            self.config["fields"].as_str_seq(),
        )

    def _initialize_fields(self, fields: list[str]) -> None:
        """Creates the set for fields to process in tagging."""
        if fields:
            self.fields_to_process = set(fields)
            self._log.debug(
                f"set fields to process: {', '.join(self.fields_to_process)}"
            )
        else:
            self._log.debug("no fields specified!")

    def _preserve_words(self, preserve: list[str]) -> None:
        for word in preserve:
            if " " in word:
                self.preserve_phrases[word] = re.compile(
                    rf"\b{re.escape(word)}\b", re.IGNORECASE
                )
            else:
                self.preserve[word.upper()] = word

    def _preserved(self, word, **kwargs) -> Optional[str]:
        """Callback function for words to preserve case of."""
        if preserved_word := self.preserve.get(word.upper(), ""):
            return preserved_word
        return None

    def received_info_handler(self, info: Info):
        """Calls titlecase fields for AlbumInfo or TrackInfo
        Processes the tracks field for AlbumInfo
        """
        self.titlecase_fields(info)
        if isinstance(info, AlbumInfo):
            for track in info.tracks:
                self.titlecase_fields(track)

    def commands(self) -> list[ui.Subcommand]:
        def func(lib, opts, args):
            write = ui.should_write()
            for item in lib.items(args):
                self._log.info(f"titlecasing {item.title}:")
                self.titlecase_fields(item)
                item.store()
                if write:
                    item.try_write()

        self._command.func = func
        return [self._command]

    def titlecase_fields(self, item: Item | Info):
        """Applies titlecase to fields, except
        those excluded by the default exclusions and the
        set exclude lists.
        """
        for field in self.fields_to_process:
            init_field = getattr(item, field, "")
            if init_field:
                if isinstance(init_field, list) and isinstance(
                    init_field[0], str
                ):
                    cased_list: list[str] = [
                        self.titlecase(i, field) for i in init_field
                    ]
                    if cased_list != init_field:
                        setattr(item, field, cased_list)
                        self._log.info(
                            f"{field}: {', '.join(init_field)} ->",
                            f"{', '.join(cased_list)}",
                        )
                elif isinstance(init_field, str):
                    cased: str = self.titlecase(init_field, field)
                    if cased != init_field:
                        setattr(item, field, cased)
                        self._log.info(f"{field}: {init_field} -> {cased}")
                else:
                    self._log.debug(f"{field}: no string present")
            else:
                self._log.debug(f"{field}: does not exist on {type(item)}")

    def titlecase(self, text: str, field: str = "") -> str:
        """Titlecase the given text."""
        # Any necessary replacements go first, mainly punctuation.
        titlecased = text.lower() if self.force_lowercase else text
        for pair in self.replace:
            target, replacement = pair
            titlecased = titlecased.replace(target, replacement)
        # General titlecase operation
        titlecased = titlecase(
            titlecased,
            small_first_last=self.config["small_first_last"],
            callback=self._preserved,
        )
        # Apply "The Artist" feature
        if self.the_artist and "artist" in field:
            titlecased = self.the_artist_regexp.sub("The", titlecased)
        # More complicated phrase replacements.
        for phrase, regexp in self.preserve_phrases.items():
            titlecased = regexp.sub(phrase, titlecased)
        return titlecased

    def imported(self, session: ImportSession, task: ImportTask) -> None:
        """Import hook for titlecasing on import."""
        for item in task.imported_items():
            try:
                self._log.debug(f"titlecasing {item.title}:")
                self.titlecase_fields(item)
                item.store()
            except Exception as e:
                self._log.debug(f"titlecasing exception {e}")
