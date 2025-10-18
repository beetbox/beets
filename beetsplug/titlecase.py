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
from beets.dbcore import types
from beets import ui
from titlecase import titlecase
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from beets.importer import ImportSession, ImportTask
    from beets.library import Item

__author__ = "henryoberholtzer@gmail.com"
__version__ = "1.0"

# These fields are excluded to avoid modifying anything
# that may be case sensistive, or important to database
# function
EXCLUDED_INFO_FIELDS = set([
        'id',
        'mb_workid', 
        'mb_trackid', 
        'mb_albumid',
        'mb_artistid',
        'mb_albumartistid',
        'mb_albumartistids',
        'mb_releasetrackid',
        'acoustid_fingerprint',
        'acoustid_id',
        'mb_releasegroupid',
        'asin',
        'isrc',
        'bitrate_mode',
        'encoder_info',
        'encoder_settings'
        ])

class TitlecasePlugin(BeetsPlugin):
    preserve: dict[str, str] = {}
    fields_to_process: set[str] = []
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
        include_fields - fields to apply titlecase to, default is all, except select excluded fields
        exclude_fields - fields to exclude from titlecase to, default is none
        NOTE: titlecase will not interact with possibly case sensitive fields like id,
        path or album_id. Paths are best modified in path config.
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
                help="preserve the case of the given word, in addition to those configured."
                )

        self._command.parser.add_option(
                "-f",
                "--field",
                help="apply to the following fields."
                )

        for word in self.config["preserve"].as_str_seq():
            self.preserve[word.upper()] = word
        self.__init_field_list__() 

    def __init_field_list__(self) -> None:
        """ Creates the set for fields to process in tagging.
        If we have include_fields from config, the shared fields will be used.
        Then, any fields specified to be excluded will be removed. 
        This will result in exclude_fields overriding include_fields.
        Last, the EXCLUDED_INFO_FIELDS are removed to prevent unitentional modification.
        """
        initial_field_list = set([
            k for k, v in Item()._fields.items() if 
            isinstance(v, types.STRING) or 
            isinstance(v, types.SEMICOLONS_SPACE_DSV) or
            isinstance(v, types.MULTI_VALUE_DSV)
            )
        if (incl := self.config["include_fields"].as_str_seq()):
            initial_field_list = initial_field_list.intersection(set(incl))
        if (excl := self.config["exclude_fields"].as_str_seq()):
            initial_field_list -= set(excl)
        initial_field_list -= set(EXCLUDED_INFO_FIELDS)
        self.fields_to_process = basic_fields_list

    def __preserved__(self, word, **kwargs) -> str | None:
        """ Callback function for words to preserve case of."""
        if (preserved_word := self.preserve.get(word.upper(), "")):
            return preserved_word
        return None

    def commands(self) -> list[ui.Subcommand]:
        def func(lib, opts, args):
            self.config.set_args(opts)

    def titlecase_fields(self, item: Item):
        """ Applies titlecase to fields, except 
        those excluded by the default exclusions and the
        set exclude lists. 
        """
        for field in self.fields_to_process:
            init_str = getattr(item, field, "")
            if init_str:
                cased = self.titlecase(old_str) 
                self._log.info(f"{field}: {init_str} -> {cased}")
                setattr(item, field, cased)
            else:
                self._log.info(f"{field}: no string present")

    def titlecase(self, text: str) -> str:
        """ Titlecase the given text. """
        return titlecase(text, 
            small_first_last=self.config["small_first_last"],
            callback=self.__preserved__)

    def imported(self, session: ImportSession, task: ImportTask) -> None:
         """ Import hook for titlecasing on import. """
         for item in task.imported_items():
            self._log.info(f"titlecasing {item.title}:")
            self.titlecase_fields(item)
            item.store()


