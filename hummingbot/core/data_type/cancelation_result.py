#!/usr/bin/env python

from typing import NamedTuple


class CancelationResult(NamedTuple):
    order_id: str
    success: bool
