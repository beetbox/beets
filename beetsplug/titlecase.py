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

"""Apply NYT manual of style title case rules, to paths and tag text.
   Title case logic is derived from the python-titlecase library."""

from beets.plugins import BeetsPlugin
from beets import ui
from titlecase import titlecase
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from beets.importer import ImportSession, ImportTask
    from beets.library import Item

__author__ = "henryoberholtzer@gmail.com"
__version__ = "1.0"

class TitlecasePlugin(BeetsPlugin):
    preserve: dict[str, str] = {}
    def __init__(self) -> None:
        super().__init__()

        self.config.add(
            {
                "preserve": [],
                "small_first_last": True,
                "titlecase_metadata": True,
                "include_fields": [],
                "exclude_fields": []
            }
        )
        """ 
        preserve - provide a list of words/acronyms with specific case requirements
        small_first_last - if small characters should be title cased at beginning
        titlecase_metadata - if metadata fields should have title case applied
        exclude_fields - fields to exclude from titlecase to, default is none
        include_fields - fields to apply titlecase to, default is all 
        titlecase will not interact with possibly case sensitive fields like id,
        path or album_id
        """
        # Register template function
        self.template_funcs["titlecase"] = self.titlecase
        # Register UI subcommands
        self._command = ui.Subcommand(
                "titlecase",
                help="apply NYT manual of style titlecase rules"
        )

        self._command.parser.add_option(
                "-p",
                "--preserve",
                help="preserve the case of the given word"
                )

        for word in self.config["preserve"].as_str_seq():
            self.preserve[word.upper()] = word

    def __preserved__(self, word, **kwargs) -> str | None:
        """ Callback function for words to preserve case of."""
        if (preserved_word := self.preserve.get(word.upper(), "")):
            return preserved_word
        return None

    def titlecase_fields(self, text: str) -> str:
        return titlecase(text)

    def titlecase(self, text: str) -> str:
        """ Titlecase the given text """
        return titlecase(text, 
                small_first_last=self.config["small_first_last"],
                callback=self.__preserved__)

    def imported(self, session: ImportSession, task: ImportTask) -> None:
         """ Import hook for titlecasing on import """
         return
