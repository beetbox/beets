# This file is part of beets.
# Copyright 2010, Adrian Sampson.
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

#All the handlers for the event system.
#Each key of the dictionary should contain a list of functions to be called
#for any event. Functions will be called in the order they were added.
handlers = { }

def addEventListener(event, function):
    """Adds an event listener to call function() when the specified event
    (as a string) happens. The parameters passed to function will vary
    depending on what event occured.

    The function should respond to named parameters. function(**kwargs) will
    trap all arguments in a dictionary."""
    global handlers
    
    if event not in handlers:
        handlers[event] = [ ] #Empty list to store the handlers
    handlers[event].append(function)

def send(event, **arguments):
    """Sends an event to all assigned event listeners. Event is the name of 
    the event to send, all other named arguments go to the event handler(s).

    Returns the number of handlers called."""

    if event in handlers:
        for handler in handlers[event]:
            handler(**arguments)
        return len(handlers[event])
    else:
        return 0

def listen(event):
    """Decorator method for creating an event listener.

    @events.listen("imported")
    def importListener(**kwargs):
        pass"""
    def helper(funct):
        addEventListener(event, funct)
        return funct

    return helper
