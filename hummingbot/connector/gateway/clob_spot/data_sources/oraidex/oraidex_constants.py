from dotmap import DotMap

ORAICHAIN_NATIVE_TOKEN = DotMap(
    {
        "id": "orai",
        "name": "orai",
        "symbol": "ORAI",
        "decimals": "6",
    },
    _dynamic=False,
)

CONNECTOR_NAME = "oraidex"

MARKETS_UPDATE_INTERVAL = 8 * 60 * 60
UPDATE_ORDER_STATUS_INTERVAL = 1

NUMBER_OF_RETRIES = 3
DELAY_BETWEEN_RETRIES = 3
TIMEOUT = 60
