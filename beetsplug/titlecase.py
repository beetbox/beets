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
from functools import cached_property
from typing import TypedDict

from titlecase import titlecase

from beets import ui
from beets.autotag.hooks import AlbumInfo, Info
from beets.importer import ImportSession, ImportTask
from beets.library import Item
from beets.plugins import BeetsPlugin

__author__ = "henryoberholtzer@gmail.com"
__version__ = "1.0"


class PreservedText(TypedDict):
    words: dict[str, str]
    phrases: dict[str, re.Pattern[str]]


class TitlecasePlugin(BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()

        self.config.add(
            {
                "auto": True,
                "preserve": [],
                "fields": [],
                "replace": [],
                "seperators": [],
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
        seperators - Other characters to treat like periods.
        force_lowercase - Lowercases the string before titlecasing.
        small_first_last - If small characters should be cased at the start of strings.
        the_artist - If the plugin infers the field to be an artist field
        (e.g. the field contains "artist")
        It will capitalize a lowercase The, helpful for the artist names
        that start with 'The', like 'The Who' or 'The Talking Heads' when
        they are not at the start of a string. Superceded by preserved phrases.
        """
        # Register template function
        self.template_funcs["titlecase"] = self.titlecase

        # Register UI subcommands
        self._command = ui.Subcommand(
            "titlecase",
            help="Apply titlecasing to metadata specified in config.",
        )

        if self.config["auto"].get(bool):
            if self.config["after_choice"].get(bool):
                self.import_stages = [self.imported]
            else:
                self.register_listener(
                    "trackinfo_received", self.received_info_handler
                )
                self.register_listener(
                    "albuminfo_received", self.received_info_handler
                )

    @cached_property
    def force_lowercase(self) -> bool:
        return self.config["force_lowercase"].get(bool)

    @cached_property
    def replace(self) -> list[tuple[str, str]]:
        return self.config["replace"].as_pairs()

    @cached_property
    def the_artist(self) -> bool:
        return self.config["the_artist"].get(bool)

    @cached_property
    def fields_to_process(self) -> set[str]:
        fields = set(self.config["fields"].as_str_seq())
        self._log.debug(f"fields: {', '.join(fields)}")
        return fields

    @cached_property
    def preserve(self) -> PreservedText:
        strings = self.config["preserve"].as_str_seq()
        preserved: PreservedText = {"words": {}, "phrases": {}}
        for s in strings:
            if " " in s:
                preserved["phrases"][s] = re.compile(
                    rf"\b{re.escape(s)}\b", re.IGNORECASE
                )
            else:
                preserved["words"][s.upper()] = s
        return preserved

    @cached_property
    def seperators(self) -> re.Pattern[str] | None:
        if seperators := "".join(
            dict.fromkeys(self.config["seperators"].as_str_seq())
        ):
            return re.compile(rf"(.*?[{re.escape(seperators)}]+)(\s*)(?=.)")
        return None

    @cached_property
    def small_first_last(self) -> bool:
        return self.config["small_first_last"].get(bool)

    @cached_property
    def the_artist_regexp(self) -> re.Pattern[str]:
        return re.compile(r"\bthe\b")

    def titlecase_callback(self, word, **kwargs) -> str | None:
        """Callback function for words to preserve case of."""
        if preserved_word := self.preserve["words"].get(word.upper(), ""):
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

    def titlecase_fields(self, item: Item | Info) -> None:
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
        # Check we should split this into two substrings.
        if self.seperators:
            if len(splits := self.seperators.findall(text)):
                print(splits)
                split_cased = "".join(
                    [self.titlecase(s[0], field) + s[1] for s in splits]
                )
                # Add on the remaining portion
                return split_cased + self.titlecase(
                    text[len(split_cased) :], field
                )
        # Any necessary replacements go first, mainly punctuation.
        titlecased = text.lower() if self.force_lowercase else text
        for pair in self.replace:
            target, replacement = pair
            titlecased = titlecased.replace(target, replacement)
        # General titlecase operation
        titlecased = titlecase(
            titlecased,
            small_first_last=self.small_first_last,
            callback=self.titlecase_callback,
        )
        # Apply "The Artist" feature
        if self.the_artist and "artist" in field:
            titlecased = self.the_artist_regexp.sub("The", titlecased)
        # More complicated phrase replacements.
        for phrase, regexp in self.preserve["phrases"].items():
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
