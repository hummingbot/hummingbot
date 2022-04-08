#!/usr/bin/env python

from typing import NamedTuple


class CancellationResult(NamedTuple):
    order_id: str
    success: bool
