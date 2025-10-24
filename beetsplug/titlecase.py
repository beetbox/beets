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

from titlecase import titlecase

from beets import ui
from beets.dbcore import types
from beets.importer import ImportSession, ImportTask
from beets.library import Item
from beets.plugins import BeetsPlugin

__author__ = "henryoberholtzer@gmail.com"
__version__ = "1.0"

# These fields are excluded to avoid modifying anything
# that may be case sensistive, or important to database
# function
EXCLUDED_INFO_FIELDS = set(
    [
        "id",
        "mb_workid",
        "mb_trackid",
        "mb_albumid",
        "mb_artistid",
        "mb_albumartistid",
        "mb_albumartistids",
        "mb_releasetrackid",
        "acoustid_fingerprint",
        "acoustid_id",
        "mb_releasegroupid",
        "asin",
        "isrc",
        "format",
        "bitrate_mode",
        "encoder_info",
        "encoder_settings",
    ]
)


class TitlecasePlugin(BeetsPlugin):
    preserve: dict[str, str] = {}
    force_lowercase: bool = True
    fields_to_process: set[str] = set([])

    def __init__(self) -> None:
        super().__init__()

        self.template_funcs["titlecase"] = self.titlecase

        self.config.add(
            {
                "auto": True,
                "preserve": [],
                "include": [],
                "exclude": [],
                "force_lowercase": True,
                "small_first_last": True,
            }
        )

        """
        auto - Automatically apply titlecase to new import metadata.
        preserve - Provide a list of words/acronyms with specific case requirements.
        include - Fields to apply titlecase to, default is all.
        exclude - Fields to exclude from titlecase to, default is none.
        force_lowercase - Lowercases the string before titlecasing.
        small_first_last - If small characters should be cased at the start of strings.
        NOTE: Titlecase will not interact with possibly case sensitive fields.
        """

        # Register UI subcommands
        self._command = ui.Subcommand(
            "titlecase",
            help="Apply titlecasing to metadata following the NYT manual of style.",
        )

        self._command.parser.add_option(
            "-f",
            "--force-off",
            dest="force_lowercase",
            action="store_false",
            help="Turn off forcing lowercase first.",
        )

        self._command.parser.add_option(
            "-p",
            "--preserve",
            dest="preserve",
            action="store",
            help="Preserve the case of the given words.",
        )

        self._command.parser.add_option(
            "-i",
            "--include",
            dest="include",
            action="store",
            help="""Metadata fields to titlecase to, default is all.
            Always ignores case sensitive fields.""",
        )

        self._command.parser.add_option(
            "-e",
            "--exclude",
            dest="exclude",
            action="store",
            help="""Metadata fields to skip, default is none.
            Always ignores case sensitive fields.""",
        )
        self.__get_config_file__()
        if self.config["auto"]:
            self.register_listener(
                    "import_task_before_choice",
                    self.on_import_task_before_choice
                    )
        # Register template function

    def __get_config_file__(self):
        self.force_lowercase = self.config["force_lowercase"].get(bool)
        self.__preserve_words__(self.config["preserve"].as_str_seq())
        self.__init_field_list__(
            self.config["include"].as_str_seq(),
            self.config["exclude"].as_str_seq(),
        )

    def __init_field_list__(
        self, include: list[str], exclude: list[str]
    ) -> None:
        """Creates the set for fields to process in tagging.
        If we have include_fields from config, the shared fields will be used.
        Then, any fields specified to be excluded will be removed.
        This will result in exclude_fields overriding include_fields.
        Last, the EXCLUDED_INFO_FIELDS are removed to prevent unitentional modification.
        """
        initial_field_list = set(
            [
                k
                for k, v in Item()._fields.items()
                if isinstance(v, types.String)
                or isinstance(v, types.DelimitedString)
            ]
        )
        if include:
            initial_field_list = initial_field_list.intersection(set(include))
        if exclude:
            initial_field_list -= set(exclude)
        initial_field_list -= set(EXCLUDED_INFO_FIELDS)
        self.fields_to_process = initial_field_list

    def __preserve_words__(self, preserve: list[str]) -> None:
        for word in preserve:
            self.preserve[word.upper()] = word

    def __preserved__(self, word, **kwargs) -> str | None:
        """Callback function for words to preserve case of."""
        if preserved_word := self.preserve.get(word.upper(), ""):
            return preserved_word
        return None

    def commands(self) -> list[ui.Subcommand]:
        def split_if_exists(string: str):
            return string.split() if string else []

        def func(lib, opts, args):
            opts = opts.__dict__
            preserve = split_if_exists(opts["preserve"])
            excl = split_if_exists(opts["exclude"])
            incl = split_if_exists(opts["include"])
            if opts["force_lowercase"] is not None:
                self.force_lowercase = False
            self.__preserve_words__(preserve)
            self.__init_field_list__(incl, excl)
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
            init_str = getattr(item, field, "")
            if init_str:
                cased = self.titlecase(init_str)
                self._log.info(f"{field}: {init_str} -> {cased}")
                setattr(item, field, cased)
            else:
                self._log.info(f"{field}: no string present")

    def titlecase(self, text: str) -> str:
        """Titlecase the given text."""
        return titlecase(
            text.lower() if self.force_lowercase else text,
            small_first_last=self.config["small_first_last"],
            callback=self.__preserved__,
        )

    def on_import_task_before_choice(self, task: ImportTask, session: ImportSession) -> None:
        """Maps imported to on_import_task_before_choice"""
        return imported(session, task)

    def imported(self, session: ImportSession, task: ImportTask) -> None:
        """Import hook for titlecasing on import."""
        for item in task.imported_items():
            self._log.info(f"titlecasing {item.title}:")
            self.titlecase_fields(item)
            item.store()
