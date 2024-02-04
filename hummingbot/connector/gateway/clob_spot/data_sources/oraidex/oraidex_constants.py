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

TIMEOUT = 60

NUMBER_OF_RETRIES = 3
DELAY_BETWEEN_RETRIES = 3
TIMEOUT = 60
