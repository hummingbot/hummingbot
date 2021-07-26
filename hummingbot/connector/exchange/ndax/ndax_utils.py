from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-CAD"

# NDAX fees: https://ndax.io/fees
# Fees have to be expressed as percent value
DEFAULT_FEES = [2, 2]


# USE_ETHEREUM_WALLET not required because default value is false
# FEE_TYPE not required because default value is Percentage
# FEE_TOKEN not required because the fee is not flat


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "")


KEYS = {
    "ndax_username":
        ConfigVar(key="ndax_username",
                  prompt="Enter your NDAX user name >>> ",
                  required_if=using_exchange("ndax"),
                  is_secure=False,
                  is_connect_key=True),
    "ndax_uid":
        ConfigVar(key="ndax_uid",
                  prompt="Enter your NDAX user ID (uid) >>> ",
                  required_if=using_exchange("ndax"),
                  is_secure=False,
                  is_connect_key=True),
    "ndax_api_key":
        ConfigVar(key="ndax_api_key",
                  prompt="Enter your NDAX API key >>> ",
                  required_if=using_exchange("ndax"),
                  is_secure=True,
                  is_connect_key=True),
    "ndax_secret_key":
        ConfigVar(key="ndax_secret_key",
                  prompt="Enter your NDAX secret key >>> ",
                  required_if=using_exchange("ndax"),
                  is_secure=True,
                  is_connect_key=True),
}

# OTHER_DOMAINS = ["ndax_testnet"]
# OTHER_DOMAINS_PARAMETER = {"ndax_testnet": "ndax_testnet"}
# OTHER_DOMAINS_EXAMPLE_PAIR = {"ndax_testnet": "BTC-CAD"}
# OTHER_DOMAINS_DEFAULT_FEES = {"ndax_testnet": [2, 2]}
# OTHER_DOMAINS_KEYS = {
#     "ndax_testnet": {
#         "ndax_testnet_uid":
#             ConfigVar(key="ndax_testnet_uid",
#                       prompt="Enter your NDAX user ID (uid) >>> ",
#                       required_if=using_exchange("ndax"),
#                       is_secure=False,
#                       is_connect_key=True),
#         "ndax_testnet_api_key":
#             ConfigVar(key="ndax_testnet_api_key",
#                       prompt="Enter your NDAX API key >>> ",
#                       required_if=using_exchange("ndax"),
#                       is_secure=True,
#                       is_connect_key=True),
#         "ndax_testnet_secret_key":
#             ConfigVar(key="ndax_testnet_secret_key",
#                       prompt="Enter your NDAX secret key >>> ",
#                       required_if=using_exchange("ndax"),
#                       is_secure=True,
#                       is_connect_key=True),
#     }
# }
