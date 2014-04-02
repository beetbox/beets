# This file is part of beets.
# Copyright 2013, Adrian Sampson.
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

from enum import Enum, EnumMeta

class OrderedEnum(Enum):
    """
    An Enum subclass that allows comparison of members.
    """
    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self._value_ >= other._value_
        return NotImplemented
    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self._value_ > other._value_
        return NotImplemented
    def __le__(self, other):
        if self.__class__ is other.__class__:
            return self._value_ <= other._value_
        return NotImplemented
    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self._value_ < other._value_
        return NotImplemented

class IndexableEnumMeta(EnumMeta):
    """
    Metaclass for Enums that support indexing by value
    """
    def __getitem__(obj, x):
        if isinstance(x, int):
            return obj._value2member_map_[x]
        #import code; code.interact(local=locals())
        return super(IndexableEnumMeta, obj).__getitem__(x)

class IndexableEnum(Enum):
    """
    An Enum subclass that suports indexing by value.
    """
    __metaclass__ = IndexableEnumMeta

