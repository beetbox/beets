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
from typing import Optional, Pattern

from titlecase import titlecase

from beets import ui
from beets.importer import ImportSession, ImportTask
from beets.library import Item
from beets.plugins import BeetsPlugin

__author__ = "henryoberholtzer@gmail.com"
__version__ = "1.0"


class TitlecasePlugin(BeetsPlugin):
    preserve: dict[str, str] = {}
    preserve_phrases: dict[str, Pattern[str]] = {}
    force_lowercase: bool = True
    fields_to_process: set[str] = set()
    the_artist: bool = True

    def __init__(self) -> None:
        super().__init__()

        # Register template function
        self.template_funcs["titlecase"] = self.titlecase  # type: ignore

        self.config.add(
            {
                "auto": True,
                "preserve": [],
                "fields": [],
                "force_lowercase": False,
                "small_first_last": True,
                "the_artist": True,
            }
        )

        """
        auto - Automatically apply titlecase to new import metadata.
        preserve - Provide a list of strings with specific case requirements.
        fields - Fields to apply titlecase to.
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

        self.__get_config_file__()
        if self.config["auto"]:
            self.import_stages = [self.imported]

    def __get_config_file__(self):
        self.force_lowercase = self.config["force_lowercase"].get(bool)
        self.__preserve_words__(self.config["preserve"].as_str_seq())
        self.the_artist = self.config["the_artist"].get(bool)
        self.__init_fields_to_process__(
            self.config["fields"].as_str_seq(),
        )

    def __init_fields_to_process__(self, fields: list[str]) -> None:
        """Creates the set for fields to process in tagging."""
        if fields:
            self.fields_to_process = set(fields)
            self._log.info(
                f"set fields to process: {', '.join(self.fields_to_process)}"
            )
        else:
            self._log.info("no fields specified!")

    def __preserve_words__(self, preserve: list[str]) -> None:
        for word in preserve:
            if " " in word:
                self.preserve_phrases[word] = re.compile(
                    re.escape(word), re.IGNORECASE
                )
            else:
                self.preserve[word.upper()] = word

    def __preserved__(self, word, **kwargs) -> Optional[str]:
        """Callback function for words to preserve case of."""
        if preserved_word := self.preserve.get(word.upper(), ""):
            return preserved_word
        return None

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

    def titlecase_fields(self, item: Item):
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
                        self.titlecase(i) for i in init_field
                    ]
                    setattr(item, field, cased_list)
                    self._log.info(
                        (
                            f"{field}: {', '.join(init_field)} -> "
                            f"{', '.join(cased_list)}"
                        )
                    )
                elif isinstance(init_field, str):
                    cased: str = self.titlecase(init_field)
                    setattr(item, field, cased)
                    self._log.info(f"{field}: {init_field} -> {cased}")
                else:
                    self._log.info(f"{field}: no string present")
            else:
                self._log.info(f"{field}: does not exist on {item}")

    def titlecase(self, text: str, field: str = "") -> str:
        """Titlecase the given text."""
        titlecased = titlecase(
            text.lower() if self.force_lowercase else text,
            small_first_last=self.config["small_first_last"],
            callback=self.__preserved__,
        )
        if self.the_artist and "artist" in field:
            titlecased = titlecased.replace("the", "The")
        for phrase, regexp in self.preserve_phrases.items():
            titlecased = regexp.sub(phrase, titlecased)
        return titlecased

    def imported(self, session: ImportSession, task: ImportTask) -> None:
        """Import hook for titlecasing on import."""
        for item in task.imported_items():
            try:
                self._log.info(f"titlecasing {item.title}:")
                self.titlecase_fields(item)
                item.store()
            except Exception as e:
                self._log.info(f"titlecasing exception {e}")
