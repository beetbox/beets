# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Thomas Scholtes.
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

from __future__ import division, absolute_import, print_function

from beets.plugins import BeetsPlugin
from beets.dbcore import types
from confuse import ConfigValueError
from beets import library


class TypesPlugin(BeetsPlugin):

    @property
    def item_types(self):
        return self._types()

    @property
    def album_types(self):
        return self._types()

    def _types(self):
        if not self.config.exists():
            return {}

        mytypes = {}
        for key, value in self.config.items():
            if value.get() == 'int':
                mytypes[key] = types.INTEGER
            elif value.get() == 'float':
                mytypes[key] = types.FLOAT
            elif value.get() == 'bool':
                mytypes[key] = types.BOOLEAN
            elif value.get() == 'date':
                mytypes[key] = library.DateType()
            else:
                raise ConfigValueError(
                    u"unknown type '{0}' for the '{1}' field"
                    .format(value, key))
        return mytypes
