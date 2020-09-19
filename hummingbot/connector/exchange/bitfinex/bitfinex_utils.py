import math

from typing import Dict, List
from decimal import Decimal


# deeply merge two dictionaries
def merge_dicts(source: Dict, destination: Dict) -> Dict:
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            merge_dicts(value, node)
        else:
            destination[key] = value

    return destination


# join paths
def join_paths(*paths: List[str]) -> str:
    return "/".join(paths)


# get precision decimal from a number
def get_precision(precision: int) -> Decimal:
    return Decimal(1) / Decimal(math.pow(10, precision))
