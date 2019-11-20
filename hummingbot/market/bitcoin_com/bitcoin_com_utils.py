import enum
from typing import Dict, Any


# convert message received from exchange to a normalized message
# TODO: use TypedDict once it's supported
def raw_msg_to_msg(raw_msg: Dict[str, Any]) -> Dict:
    id = raw_msg.get("id", None)
    method = raw_msg.get("method", None)
    data = raw_msg.get("params", raw_msg.get("result", None))
    error = raw_msg.get("error", None)

    return {
        "id": id,
        "method": method,
        "data": data,
        "error": error
    }


class EventTypes(enum.Enum):
    OrderbookSnapshot = "OrderbookSnapshot",
    OrderbookUpdate = "OrderbookUpdate",
    TradesSnapshot = "TradesSnapshot",
    TradesUpdate = "TradesUpdate",
    ActiveOrdersSnapshot = "ActiveOrdersSnapshot",
    ActiveOrdersUpdate = "ActiveOrdersUpdate",
    BalanceSnapshot = "BalanceSnapshot",
    BalanceUpdate = "BalanceUpdate"


# convert normalized message to event
# TODO: use TypedDict once it's supported
def add_event_type(type: EventTypes, data: Dict) -> Dict:
    data["event_type"] = type
    return data


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
