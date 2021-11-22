# A single source of truth for constant variables related to the exchange

EXCHANGE_NAME = "southxchange"
REST_URL = "https://www.southxchange.com/api/v4/"
WS_URL = "wss://www.southxchange.com/api/v4/connect"
PUBLIC_WS_URL = WS_URL
PRIVATE_WS_URL = WS_URL + '?token={access_token}'
PONG_PAYLOAD = {"op": "pong"}
