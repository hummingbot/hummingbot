# A single source of truth for constant variables related to the exchange


EXCHANGE_NAME = "bitmax"
REST_URL = "https://bitmax.io/api/pro/v1"
WS_URL = "wss://bitmax.io/1/api/pro/v1/stream"
PONG_PAYLOAD = {"op": "pong"}


def getRestUrlPriv(accountId: int) -> str:
    return f"https://bitmax.io/{accountId}/api/pro/v1"


def getWsUrlPriv(accountId: int) -> str:
    return f"wss://bitmax.io/{accountId}/api/pro/v1"
