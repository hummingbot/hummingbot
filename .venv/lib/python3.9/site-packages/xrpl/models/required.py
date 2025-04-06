"""
A sentinel object used to determine if a given field is not set. Using this
allows us to not worry about argument ordering and treat all arguments to
__init__ as kwargs.
"""

from typing_extensions import Final

REQUIRED: Final[object] = object()
