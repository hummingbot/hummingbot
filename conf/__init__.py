#!/usr/bin/env python

import logging as _logging
import os

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

# whether to enable api mocking in unit test cases
mock_api_enabled = os.getenv("MOCK_API_ENABLED")

"""
# AscendEX Tests
ascend_ex_api_key = os.getenv("ASCEND_EX_KEY")
ascend_ex_secret_key = os.getenv("ASCEND_EX_SECRET")

# Binance Tests
binance_api_key = os.getenv("BINANCE_API_KEY")
binance_api_secret = os.getenv("BINANCE_API_SECRET")

# Binance Perpetuals Tests
binance_perpetuals_api_key = os.getenv("BINANCE_PERPETUALS_API_KEY")
binance_perpetuals_api_secret = os.getenv("BINANCE_PERPETUALS_API_SECRET")

# Coinbase Advanced Trade Tests
coinbase_advanced_trade_api_key = os.getenv("COINBASE_ADVANCED_TRADE_API_KEY")
coinbase_advanced_trade_secret_key = os.getenv("COINBASE_ADVANCED_TRADE_SECRET_KEY")


# Htx Tests
htx_api_key = os.getenv("HTX_API_KEY")
htx_secret_key = os.getenv("HTX_SECRET_KEY")

# Bittrex Tests
bittrex_api_key = os.getenv("BITTREX_API_KEY")
bittrex_secret_key = os.getenv("BITTREX_SECRET_KEY")

# KuCoin Tests
kucoin_api_key = os.getenv("KUCOIN_API_KEY")
kucoin_secret_key = os.getenv("KUCOIN_SECRET_KEY")
kucoin_passphrase = os.getenv("KUCOIN_PASSPHRASE")

test_web3_provider_list = [os.getenv("WEB3_PROVIDER")]

# Kraken Tests
kraken_api_key = os.getenv("KRAKEN_API_KEY")
kraken_secret_key = os.getenv("KRAKEN_SECRET_KEY")

# OKX Test
okx_api_key = os.getenv("OKX_API_KEY")
okx_secret_key = os.getenv("OKX_SECRET_KEY")
okx_passphrase = os.getenv("OKX_PASSPHRASE")

# BitMart Test
bitmart_api_key = os.getenv("BITMART_API_KEY")
bitmart_secret_key = os.getenv("BITMART_SECRET_KEY")
bitmart_memo = os.getenv("BITMART_MEMO")

# BTC Markets Test
btc_markets_api_key = os.getenv("BTC_MARKETS_API_KEY")
btc_markets_secret_key = os.getenv("BTC_MARKETS_SECRET_KEY")

# HitBTC Tests
hitbtc_api_key = os.getenv("HITBTC_API_KEY")
hitbtc_secret_key = os.getenv("HITBTC_SECRET_KEY")

# Gate.io Tests
gate_io_api_key = os.getenv("GATE_IO_API_KEY")
gate_io_secret_key = os.getenv("GATE_IO_SECRET_KEY")

# Wallet Tests
test_erc20_token_address = os.getenv("TEST_ERC20_TOKEN_ADDRESS")
web3_test_private_key_a = os.getenv("TEST_WALLET_PRIVATE_KEY_A")
web3_test_private_key_b = os.getenv("TEST_WALLET_PRIVATE_KEY_B")
web3_test_private_key_c = os.getenv("TEST_WALLET_PRIVATE_KEY_C")

coinalpha_order_book_api_username = "***REMOVED***"
coinalpha_order_book_api_password = "***REMOVED***"
"""
