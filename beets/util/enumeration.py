# This file is part of beets.
# Copyright 2011, Adrian Sampson.
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

"""A metaclass for enumerated types that really are types.

You can create enumerations with `enum(values, [name])` and they work
how you would expect them to.

    >>> from enumeration import enum
    >>> Direction = enum('north east south west', name='Direction')
    >>> Direction.west
    Direction.west
    >>> Direction.west == Direction.west
    True
    >>> Direction.west == Direction.east
    False
    >>> isinstance(Direction.west, Direction)
    True
    >>> Direction[3]
    Direction.west
    >>> Direction['west']
    Direction.west
    >>> Direction.west.name
    'west'
    >>> Direction.north < Direction.west
    True
    
Enumerations are classes; their instances represent the possible values
of the enumeration. Because Python classes must have names, you may
provide a `name` parameter to `enum`; if you don't, a meaningless one
will be chosen for you.
"""
import random

class Enumeration(type):
    """A metaclass whose classes are enumerations.
    
    The `values` attribute of the class is used to populate the
    enumeration. Values may either be a list of enumerated names or a
    string containing a space-separated list of names. When the class
    is created, it is instantiated for each name value in `values`.
    Each such instance is the name of the enumerated item as the sole
    argument.
    
    The `Enumerated` class is a good choice for a superclass.
    """
    
    def __init__(cls, name, bases, dic):
        super(Enumeration, cls).__init__(name, bases, dic)
        
        if 'values' not in dic:
            # Do nothing if no values are provided (i.e., with
            # Enumerated itself).
            return
        
        # May be called with a single string, in which case we split on
        # whitespace for convenience.
        values = dic['values']
        if isinstance(values, basestring):
            values = values.split()
        
        # Create the Enumerated instances for each value. We have to use
        # super's __setattr__ here because we disallow setattr below.
        super(Enumeration, cls).__setattr__('_items_dict', {})
        super(Enumeration, cls).__setattr__('_items_list', [])
        for value in values:
            item = cls(value, len(cls._items_list))
            cls._items_dict[value] = item
            cls._items_list.append(item)
    
    def __getattr__(cls, key):
        try:
            return cls._items_dict[key]
        except KeyError:
            raise AttributeError("enumeration '" + cls.__name__ +
                                 "' has no item '" + key + "'")
    
    def __setattr__(cls, key, val):
        raise TypeError("enumerations do not support attribute assignment")
    
    def __getitem__(cls, key):
        if isinstance(key, int):
            return cls._items_list[key]
        else:
            return getattr(cls, key)
    
    def __len__(cls):
        return len(cls._items_list)
            
    def __iter__(cls):
        return iter(cls._items_list)
    
    def __nonzero__(cls):
        # Ensures that __len__ doesn't get called before __init__ by
        # pydoc.
        return True
            
class Enumerated(object):
    """An item in an enumeration.
    
    Contains instance methods inherited by enumerated objects. The
    metaclass is preset to `Enumeration` for your convenience.
    
    Instance attributes: 
    name -- The name of the item.
    index -- The index of the item in its enumeration.
    
        >>> from enumeration import Enumerated
        >>> class Garment(Enumerated):
        ...     values = 'hat glove belt poncho lederhosen suspenders'
        ...     def wear(self):
        ...         print 'now wearing a ' + self.name
        ...
        >>> Garment.poncho.wear()
        now wearing a poncho
    """
    
    __metaclass__ = Enumeration
    
    def __init__(self, name, index):
        self.name = name
        self.index = index

    def __str__(self):
        return type(self).__name__ + '.' + self.name

    def __repr__(self):
        return str(self)

    def __cmp__(self, other):
        if type(self) is type(other):
            # Note that we're assuming that the items are direct
            # instances of the same Enumeration (i.e., no fancy
            # subclassing), which is probably okay.
            return cmp(self.index, other.index)
        else:
            return NotImplemented

def enum(*values, **kwargs):
    """Shorthand for creating a new Enumeration class.
    
    Call with enumeration values as a list, a space-delimited string, or
    just an argument list. To give the class a name, pass it as the
    `name` keyword argument. Otherwise, a name will be chosen for you.
    
    The following are all equivalent:
    
        enum('pinkie ring middle index thumb')
        enum('pinkie', 'ring', 'middle', 'index', 'thumb')
        enum(['pinkie', 'ring', 'middle', 'index', 'thumb'])
    """
    
    if ('name' not in kwargs) or kwargs['name'] is None:
        # Create a probably-unique name. It doesn't really have to be
        # unique, but getting distinct names each time helps with
        # identification in debugging.
        name = 'Enumeration' + hex(random.randint(0,0xfffffff))[2:].upper()
    else:
        name = kwargs['name']
    
    if len(values) == 1:
        # If there's only one value, we have a couple of alternate calling
        # styles.
        if isinstance(values[0], basestring) or hasattr(values[0], '__iter__'):
            values = values[0]
        
    return type(name, (Enumerated,), {'values': values})
