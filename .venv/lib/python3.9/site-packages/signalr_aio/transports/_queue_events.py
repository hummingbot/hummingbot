#!/usr/bin/python
# -*- coding: utf-8 -*-

# signalr_aio/transports/_queue_events.py
# Stanislav Lazarov

class Event(object):
    """
    Event is base class providing an interface
    for all subsequent(inherited) events.
    """


class InvokeEvent(Event):
    def __init__(self, message):
        self.type = 'INVOKE'
        self.message = message


class CloseEvent(Event):
    def __init__(self):
        self.type = 'CLOSE'
