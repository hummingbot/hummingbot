from bidict import bidict

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.in_flight_order import OrderState

CONNECTOR_NAME = "xrpl"

MAX_ID_HEX_DIGITS = 16
MAX_ID_BIT_COUNT = MAX_ID_HEX_DIGITS * 4

BASE_PATH_URL = {
    "mainnet": "https://xrplcluster.com/",
    "testnet": "https://s.altnet.rippletest.net:51234/",
    "devnet": "https://s.devnet.rippletest.net:51234/",
    "amm-devnet": "https://amm.devnet.rippletest.net:51234/"
}

WS_PATH_URL = {
    "mainnet": "wss://xrplcluster.com/",
    "testnet": "wss://s.altnet.rippletest.net/",
    "devnet": "wss://s.devnet.rippletest.net:51233/",
    "amm-devnet": "wss://amm.devnet.rippletest.net:51233/	"
}

ORDER_SIDE_MAP = bidict(
    {
        "BUY": TradeType.BUY,
        "SELL": TradeType.SELL
    }
)

XRPL_TO_HB_STATUS_MAP = {
    "OPEN": OrderState.OPEN,
    "PENDING_OPEN": OrderState.PENDING_CREATE,
    "PENDING_CANCEL": OrderState.PENDING_CANCEL,
    "OFFER_EXPIRED_OR_UNFUNDED": OrderState.CANCELED,
    "UNKNOWN": OrderState.FAILED,
    "FAILED": OrderState.FAILED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "FILLED": OrderState.FILLED,
    "CANCELED": OrderState.CANCELED,
}
