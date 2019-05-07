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

test_web3_provider_list = [os.getenv("WEB3_PROVIDER")]

# Wallet Tests
test_erc20_token_address = os.getenv("TEST_ERC20_TOKEN_ADDRESS")
web3_test_private_key_a = "***REMOVED***"
web3_test_private_key_b = "***REMOVED***"
web3_test_private_key_c = "***REMOVED***"

coinalpha_order_book_api_username = "***REMOVED***"
coinalpha_order_book_api_password = "***REMOVED***"

kafka_2 = {
    "bootstrap_servers": "***REMOVED***",
    "zookeeper_servers":  "***REMOVED***"
}


try:
    from .config_local import *
except ModuleNotFoundError:
    pass

try:
    from .web3_wallet_secret import *
except ModuleNotFoundError:
    pass

try:
    from .binance_secret import *
except ModuleNotFoundError:
    pass

try:
    from .coinbase_pro_secrets import *
except ModuleNotFoundError:
    pass
