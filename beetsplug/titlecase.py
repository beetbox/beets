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
from titlecase import titlecase

__author__ = "henryoberholtzer@gmail.com"
__version__ = "1.0"

class TitlecasePlugin(BeetsPlugin):
    preserve: dict[str, str] = {}
    def __init__(self) -> None:
        super().__init__()
        # Register template function
        self.template_funcs["titlecase"] = self.titlecase

        self.config.add(
            {
                "preserve": [],
                "small_first_last": True
            }
        )
        print(self.config)
        for word in self.config["preserve"].as_str_seq():
            self.preserve[word.upper()] = word

    def __preserved__(self, word, **kwargs) -> str | None:
        """ Callback function for words to preserve case of."""
        if (preserved_word := self.preserve.get(word.upper(), "")):
            return preserved_word
        return None

    def titlecase(self, text: str) -> str:
        """ Titlecase the given text """
        return titlecase(text, 
                small_first_last=self.config["small_first_last"],
                callback=self.__preserved__)
