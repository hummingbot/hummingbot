import math
import time
import random
from typing import Dict, List


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


# get timestamp in milliseconds
def get_ms_timestamp() -> int:
    return math.floor(time.time() * 1e3)


# convert milliseconds timestamp to seconds
def ms_timestamp_to_s(ms: int) -> int:
    return math.floor(ms / 1e3)


# Request ID class
class RequestId():
    """
    Generate request ids
    """
    _request_id: int = 0

    def generate_request_id(self) -> int:
        self._request_id += 1
        # return self._request_id
        return math.floor(random.random() * 1e18)
