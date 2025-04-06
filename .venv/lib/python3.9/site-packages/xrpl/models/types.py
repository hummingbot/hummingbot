"""
Internal helper types for xrpl.models

:meta private:
"""

from typing import Any, Dict, List, Union

# The type of a parsed model in python, after it is loaded from a JSON string
# but before it is loaded into a model. Internal representations use
# snake_cased keys for the dictionary prior to loading into a model, but those
# keys must be PascalCased when sent to/received from a validator.
#
# TODO these Anys can be resolved if/when mypy supports recursive types. The
# correct type of this should be:
# _XRPL_VALUE_TYPE = Union[
#   str,
#   int,
#   List[_XRPL_VALUE_TYPE],
#   Dict[str, _XRPL_VALUE_TYPE]
# ]
# Here is their GH issue https://github.com/python/mypy/issues/731
XRPL_VALUE_TYPE = Union[str, int, List[Any], Dict[str, Any]]
