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
