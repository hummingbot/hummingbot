from bidict import bidict

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState

CONNECTOR_NAME = "xrpl"

BASE_PATH_URL = {
    "mainnet": "https://xrplcluster.com/",
    "testnet": "api.dexalot-test.com/privapi",
    "devnet": "https://s.devnet.rippletest.net:51234/",
    "amm-devnet": "https://amm.devnet.rippletest.net:51234/"
}

WS_PATH_URL = {
    "mainnet": "wss://xrplcluster.com/",
    "testnet": "wss://s.altnet.rippletest.net/",
    "devnet": "wss://s.devnet.rippletest.net:51233/",
    "amm-devnet": "wss://amm.devnet.rippletest.net:51233/	"
}

HEARTBEAT_TIME_INTERVAL = 30.0

ORDER_SIDE_MAP = bidict(
    {
        "BUY": TradeType.BUY,
        "SELL": TradeType.SELL
    }
)

ORDER_TYPE_MAP = bidict(
    {
        0: OrderType.MARKET,
        1: OrderType.LIMIT,
        2: OrderType.LIMIT_MAKER,
    }
)

HB_TO_DEXALOT_NUMERIC_STATUS_MAP = {
    OrderState.OPEN: 0,
    OrderState.FAILED: 1,
    OrderState.PARTIALLY_FILLED: 2,
    OrderState.FILLED: 3,
    OrderState.CANCELED: 4,
}
HB_TO_DEXALOT_STATUS_MAP = {
    OrderState.OPEN: "NEW",
    OrderState.FAILED: "REJECTED",
    OrderState.PARTIALLY_FILLED: "PARTIAL",
    OrderState.FILLED: "FILLED",
    OrderState.CANCELED: "CANCELED",
}
DEXALOT_TO_HB_NUMERIC_STATUS_MAP = {
    0: OrderState.OPEN,
    1: OrderState.FAILED,
    2: OrderState.PARTIALLY_FILLED,
    3: OrderState.FILLED,
    4: OrderState.CANCELED,
    6: OrderState.CANCELED,
    7: OrderState.FILLED,
}
XRPL_TO_HB_STATUS_MAP = {
    "NEW": OrderState.OPEN,
    "REJECTED": OrderState.FAILED,
    "PARTIAL": OrderState.PARTIALLY_FILLED,
    "FILLED": OrderState.FILLED,
    "CANCELED": OrderState.CANCELED,
    "KILLED": OrderState.FAILED,
    "CANCEL_REJECT": OrderState.FILLED,
}
