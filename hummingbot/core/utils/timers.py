"""Implements a dictionary-like class that records a Timer activity

This module set aliases:
              _NANOSECONDS: int
              _SECONDS: Decimal

Classes:
    TimeError: Exception related to the Timers
    Timers: Custom dictionary

Timers class: useful functions provided by this class
    add() Adds an entry to a named Timer, typically a timing event
    clear() Removes all the records of all Timers
    apply() Applies a function to the collection of timing event for a named Timer
    count() Enumerates the count of events of a named Timer

    and total(), min(), max(), mean(), median(), stddev()

This dictionary prevents to set values of items\n'
"""

# Standard library imports
import collections
import math
import statistics
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Union

# Annotate generic UserDict
if TYPE_CHECKING:
    UserDict = collections.UserDict[str, float]  # pragma: no cover
else:
    UserDict = collections.UserDict

_NANOSECONDS = int
_SECONDS = Decimal

_ALLOWED_TIME_UNITS = Union[(_NANOSECONDS, _SECONDS)]


class Timers(UserDict):
    """Custom dictionary that stores information about timers"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Add a private dictionary keeping track of all timings"""
        super().__init__(*args, **kwargs)
        self._timings: Dict[str, List[_NANOSECONDS]] = collections.defaultdict(list)

    def add(self, name: str, value: _NANOSECONDS) -> None:
        """Add a timing value to the given timer"""
        self._timings[name].append(value)
        self.data.setdefault(name, 0)
        self.data[name] += value

    def clear(self) -> None:
        """Clear timers"""
        self.data.clear()
        self._timings.clear()

    def __setitem__(self, name: str, value: _NANOSECONDS) -> None:
        """Disallow setting of timer values"""
        raise TypeError(
            f"{self.__class__.__name__!r} does not support item assignment. "
            "Use '.add()' to update values."
        )

    def apply(self, func: Callable[[List[_NANOSECONDS]], _NANOSECONDS], name: str) -> _NANOSECONDS:
        """Apply a function to the results of one named timer"""
        if name in self._timings:
            return func(self._timings[name])
        raise KeyError(name)

    def count(self, name: str) -> _NANOSECONDS:
        """Number of timings"""
        return self.apply(len, name=name)

    def total(self, name: str) -> _NANOSECONDS:
        """Total time for timers"""
        return self.apply(sum, name=name)

    def min(self, name: str) -> _NANOSECONDS:
        """Minimal value of timings"""
        return self.apply(lambda values: min(values or [0]), name=name)

    def max(self, name: str) -> _NANOSECONDS:
        """Maximal value of timings"""
        return self.apply(lambda values: max(values or [0]), name=name)

    def mean(self, name: str) -> _NANOSECONDS:
        """Mean value of timings"""
        return self.apply(lambda values: statistics.mean(values or [0]), name=name)

    def median(self, name: str) -> _NANOSECONDS:
        """Median value of timings"""
        return self.apply(lambda values: statistics.median(values or [0]), name=name)

    def stdev(self, name: str) -> _NANOSECONDS:
        """Standard deviation of timings"""
        if name in self._timings:
            value = self._timings[name]
            return statistics.stdev(value) if len(value) >= 2 else math.nan
        raise KeyError(name)
