#!/usr/bin/env python

from typing import Callable

from wings.event_listener import EventListener


class EventForwarder(EventListener):
    def __init__(self, to_function: Callable):
        super().__init__()
        self._to_function = to_function

    def __call__(self, arg: any):
        self._to_function(arg)
