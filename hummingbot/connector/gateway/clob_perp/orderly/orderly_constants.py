from typing import Dict

EXCHANGE_NAME: str = "orderly"
DEFAULT_DOMAIN: str = "orderly_testnet"

# Orderly requires a broker ID
BROKER_ID: str = "hummingbot"

REST_URLS: Dict[str, str] = {
    "orderly_testnet": "https://testnet-api-evm.orderly.org",
    "orderly_mainnet": "https://api-evm.orderly.org"
}

WSS_URLS: Dict[str, str] = {
    "orderly_testnet": "wss://testnet-ws-evm.orderly.org/ws/v2",
    "orderly_mainnet": "wss://ws-evm.orderly.org/ws/v2"
}

# Orderly specific headers
MESSAGE_TYPES = {
    "AUTH": "auth",
    "SUBSCRIBE": "subscribe",
    "UNSUBSCRIBE": "unsubscribe"
}