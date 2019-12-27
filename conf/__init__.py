#!/usr/bin/env python

import os

import logging as _logging
_logger = _logging.getLogger(__name__)

master_host = "***REMOVED***"
master_user = "***REMOVED***"
master_password = "***REMOVED***"
master_db = "***REMOVED***"

slave_host = "127.0.0.1"
slave_user = "reader"
slave_password = "falcon"
slave_db = "falcon"

mysql_master_server = "***REMOVED***"
mysql_slave_server = "***REMOVED***"

mysql_user = "***REMOVED***"
mysql_password = "***REMOVED***"
mysql_db = "***REMOVED***"

order_book_db = "***REMOVED***"
sparrow_db = "***REMOVED***"

order_books_db_2 = {
    "host": "***REMOVED***",
    "user": "***REMOVED***",
    "password": "***REMOVED***",
    "db": "**REMOVED***",
}

kafka_bootstrap_server = "***REMOVED***"

# Binance Tests
binance_api_key = os.getenv("BINANCE_API_KEY")
binance_api_secret = os.getenv("BINANCE_API_SECRET")

# Coinbase Pro Tests
coinbase_pro_api_key = os.getenv("COINBASE_PRO_API_KEY")
coinbase_pro_secret_key = os.getenv("COINBASE_PRO_SECRET_KEY")
coinbase_pro_passphrase = os.getenv("COINBASE_PRO_PASSPHRASE")

# IDEX Tests
idex_api_key = os.getenv("IDEX_API_KEY")
test_idex_erc20_token_address_1 = os.getenv("IDEX_TOKEN_ADDRESS_1")
test_idex_erc20_token_address_2 = os.getenv("IDEX_TOKEN_ADDRESS_2")
web3_test_private_key_idex = os.getenv("IDEX_WALLET_PRIVATE_KEY")

# Huobi Tests
huobi_api_key = os.getenv("HUOBI_API_KEY")
huobi_secret_key = os.getenv("HUOBI_SECRET_KEY")

# Dolomite Tests
dolomite_test_web3_private_key = os.getenv("DOLOMITE_TEST_PK")
dolomite_test_web3_address = os.getenv("DOLOMITE_TEST_ADDR")

# Bittrex Tests
bittrex_api_key = os.getenv("BITTREX_API_KEY")
bittrex_secret_key = os.getenv("BITTREX_SECRET_KEY")


# KuCoin Tests
kucoin_api_key = os.getenv("KUCOIN_API_KEY")
kucoin_secret_key = os.getenv("KUCOIN_SECRET_KEY")
kucoin_passphrase = os.getenv("KUCOIN_PASSPHRASE")

# Bitcoin_com Tests
bitcoin_com_api_key = os.getenv("BITCOIN_COM_API_KEY")
bitcoin_com_secret_key = os.getenv("BITCOIN_COM_SECRET_KEY")

test_web3_provider_list = [os.getenv("WEB3_PROVIDER")]

# Liquid Tests
liquid_api_key = os.getenv("LIQUID_API_KEY")
liquid_secret_key = os.getenv("LIQUID_SECRET_KEY")

# Wallet Tests
test_erc20_token_address = os.getenv("TEST_ERC20_TOKEN_ADDRESS")
web3_test_private_key_a = os.getenv("TEST_WALLET_PRIVATE_KEY_A")
web3_test_private_key_b = os.getenv("TEST_WALLET_PRIVATE_KEY_B")
web3_test_private_key_c = os.getenv("TEST_WALLET_PRIVATE_KEY_C")

coinalpha_order_book_api_username = "***REMOVED***"
coinalpha_order_book_api_password = "***REMOVED***"

kafka_2 = {
    "bootstrap_servers": "***REMOVED***",
    "zookeeper_servers": "***REMOVED***"
}


try:
    from .config_local import *             # noqa: F401, F403
except ModuleNotFoundError:
    pass

try:
    from .web3_wallet_secret import *       # noqa: F401, F403
except ModuleNotFoundError:
    pass

try:
    from .binance_secret import *           # noqa: F401, F403
except ModuleNotFoundError:
    pass

try:
    from .coinbase_pro_secrets import *     # noqa: F401, F403
except ModuleNotFoundError:
    pass
