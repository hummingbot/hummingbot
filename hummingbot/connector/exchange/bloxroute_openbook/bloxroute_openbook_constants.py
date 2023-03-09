import bxsolana.provider.constants as constants
import bxsolana_trader_proto as proto

EXCHANGE_NAME = "bloxroute_openbook"
SPOT_ORDERBOOK_PROJECT = proto.Project.P_OPENBOOK

TESTNET_PROVIDER_ENDPOINT = constants.TESTNET_API_WS
MAINNET_PROVIDER_ENDPOINT = constants.MAINNET_API_WS

CLIENT_ORDER_ID_MAX_LENGTH = 10
ORDERBOOK_LIMIT = 5
HUMMINGBOT_LOG_DECIMALS = 5
