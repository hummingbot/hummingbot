import json


class FixtureLiquid:
    """
    FixtureLiquid helps to store metadata that can be used to mimic
    API response payload returned from pinging Liquid API.
    The purpose of explcitly displaying fixtures:
    1. Make adhoc unittest mocking eaiser.
    2. Serve as a reference for future lookup the data structure passing among stages.
    """

    MARKETS = [
        {
            'id': '418',
            'product_type': 'CurrencyPair',
            'code': 'CASH',
            'name': None,
            'market_ask': None,
            'market_bid': None,
            'indicator': None,
            'currency': 'QASH',
            'currency_pair_code': 'MITHQASH',
            'symbol': 'MITH',
            'btc_minimum_withdraw': None,
            'fiat_minimum_withdraw': None,
            'pusher_channel': 'product_cash_mithqash_418',
            'taker_fee': '0.001',
            'maker_fee': '0.001',
            'low_market_bid': '0.0',
            'high_market_ask': '0.0',
            'volume_24h': '0.0',
            'last_price_24h': None,
            'last_traded_price': None,
            'last_traded_quantity': None,
            'quoted_currency': 'QASH',
            'base_currency': 'MITH',
            'disabled': True,
            'margin_enabled': False,
            'cfd_enabled': False,
            'last_event_timestamp': None
        }, {
            'id': '506',
            'product_type': 'CurrencyPair',
            'code': 'CASH',
            'name': None,
            'market_ask': 1.15e-06,
            'market_bid': 1.12e-06,
            'indicator': 1,
            'currency': 'BTC',
            'currency_pair_code': 'WLOBTC',
            'symbol': None,
            'btc_minimum_withdraw': None,
            'fiat_minimum_withdraw': None,
            'pusher_channel': 'product_cash_wlobtc_506',
            'taker_fee': '0.001',
            'maker_fee': '0.001',
            'low_market_bid': '0.00000105',
            'high_market_ask': '0.00000132',
            'volume_24h': '3147.2676282',
            'last_price_24h': '0.00000114',
            'last_traded_price': '0.00000113',
            'last_traded_quantity': '915.9778978',
            'quoted_currency': 'BTC',
            'base_currency': 'WLO',
            'disabled': False,
            'margin_enabled': False,
            'cfd_enabled': False,
            'last_event_timestamp': '1571981938.3873937'
        }, {
            'id': '538',
            'product_type': 'CurrencyPair',
            'code': 'CASH',
            'name': None,
            'market_ask': 5e-08,
            'market_bid': 3e-08,
            'indicator': -1,
            'currency': 'BTC',
            'currency_pair_code': 'LCXBTC',
            'symbol': None,
            'btc_minimum_withdraw': None,
            'fiat_minimum_withdraw': None,
            'pusher_channel': 'product_cash_lcxbtc_538',
            'taker_fee': '0.001',
            'maker_fee': '0.001',
            'low_market_bid': '3.0e-08',
            'high_market_ask': '5.0e-08',
            'volume_24h': '628660.0',
            'last_price_24h': '0.00000003',
            'last_traded_price': '0.00000004',
            'last_traded_quantity': '4867.0',
            'quoted_currency': 'BTC',
            'base_currency': 'LCX',
            'disabled': False,
            'margin_enabled': False,
            'cfd_enabled': False,
            'last_event_timestamp': '1571979656.7983565'
        }, {
            'id': '206',
            'product_type': 'CurrencyPair',
            'code': 'CASH',
            'name': None,
            'market_ask': 4.3e-07,
            'market_bid': 4.1e-07,
            'indicator': -1,
            'currency': 'ETH',
            'currency_pair_code': 'STACETH',
            'symbol': 'STAC',
            'btc_minimum_withdraw': None,
            'fiat_minimum_withdraw': None,
            'pusher_channel': 'product_cash_staceth_206',
            'taker_fee': '0.001',
            'maker_fee': '0.001',
            'low_market_bid': '0.00000034',
            'high_market_ask': '0.00000046',
            'volume_24h': '2092391.82350436',
            'last_price_24h': '0.00000043',
            'last_traded_price': '0.00000042',
            'last_traded_quantity': '7183.5833',
            'quoted_currency': 'ETH',
            'base_currency': 'STAC',
            'disabled': False,
            'margin_enabled': False,
            'cfd_enabled': False,
            'last_event_timestamp': '1571981852.7042925'
        }, {
            'id': '443',
            'product_type': 'CurrencyPair',
            'code': 'CASH',
            'name': None,
            'market_ask': 7491.83,
            'market_bid': 7448.43061967,
            'indicator': 1,
            'currency': 'USDC',
            'currency_pair_code': 'BTCUSDC',
            'symbol': None,
            'btc_minimum_withdraw': None,
            'fiat_minimum_withdraw': None,
            'pusher_channel': 'product_cash_btcusdc_443',
            'taker_fee': '0.001',
            'maker_fee': '0.001',
            'low_market_bid': '7357.91403631',
            'high_market_ask': '7550.41866211',
            'volume_24h': '0.177332',
            'last_price_24h': '7443.88002595',
            'last_traded_price': '7455.83',
            'last_traded_quantity': '0.038666',
            'quoted_currency': 'USDC',
            'base_currency': 'BTC',
            'disabled': False,
            'margin_enabled': False,
            'cfd_enabled': False,
            'last_event_timestamp': '1571995384.0727158'
        }, {
            'id': '1',
            'product_type': 'CurrencyPair',
            'code': 'CASH',
            'name': ' CASH Trading',
            'market_ask': 7479.253,
            'market_bid': 7473.12828,
            'indicator': 1,
            'currency': 'USD',
            'currency_pair_code': 'BTCUSD',
            'symbol': '$',
            'btc_minimum_withdraw': None,
            'fiat_minimum_withdraw': None,
            'pusher_channel': 'product_cash_btcusd_1',
            'taker_fee': '0.001',
            'maker_fee': '0.001',
            'low_market_bid': '7393.21607',
            'high_market_ask': '7523.722',
            'volume_24h': '356.45875936',
            'last_price_24h': '7468.53554',
            'last_traded_price': '7470.49746',
            'last_traded_quantity': '0.002',
            'quoted_currency': 'USD',
            'base_currency': 'BTC',
            'disabled': False,
            'margin_enabled': True,
            'cfd_enabled': True,
            'last_event_timestamp': '1571995384.0727158'
        }, {
            'id': '444',
            'product_type': 'CurrencyPair',
            'code': 'CASH',
            'name': None,
            'market_ask': 163.41541555,
            'market_bid': 162.14389286,
            'indicator': 1,
            'currency': 'USDC',
            'currency_pair_code': 'ETHUSDC',
            'symbol': None,
            'btc_minimum_withdraw': None,
            'fiat_minimum_withdraw': None,
            'pusher_channel': 'product_cash_ethusdc_444',
            'taker_fee': '0.001',
            'maker_fee': '0.001',
            'low_market_bid': '158.65627936',
            'high_market_ask': '165.33195762',
            'volume_24h': '5.10523492',
            'last_price_24h': '160.94835717',
            'last_traded_price': '162.27969704',
            'last_traded_quantity': '2.53608974',
            'quoted_currency': 'USDC',
            'base_currency': 'ETH',
            'disabled': False,
            'margin_enabled': False,
            'cfd_enabled': False,
            'last_event_timestamp': '1571995382.111739'
        }, {
            'id': '27',
            'product_type': 'CurrencyPair',
            'code': 'CASH',
            'name': ' CASH Trading',
            'market_ask': 162.88941,
            'market_bid': 162.70211,
            'indicator': 1,
            'currency': 'USD',
            'currency_pair_code': 'ETHUSD',
            'symbol': '$',
            'btc_minimum_withdraw': None,
            'fiat_minimum_withdraw': None,
            'pusher_channel': 'product_cash_ethusd_27',
            'taker_fee': '0.001',
            'maker_fee': '0.001',
            'low_market_bid': '159.8',
            'high_market_ask': '163.991',
            'volume_24h': '577.3217041',
            'last_price_24h': '161.63163',
            'last_traded_price': '162.572',
            'last_traded_quantity': '4.0',
            'quoted_currency': 'USD',
            'base_currency': 'ETH',
            'disabled': False,
            'margin_enabled': True,
            'cfd_enabled': False,
            'last_event_timestamp': '1571995382.9368947'
        }
    ]

    # Sample snapshot for trading pair LCXBTC with id = 538
    SNAPSHOT_1 = {
        'buy_price_levels': [
            ['0.00000002', '1000.00000000'],  # [price, amount]
            ['0.00000001', '731578.70194909']
        ],
        'sell_price_levels': [
            ['0.00000005', '191705.80611121'],
            ['0.00000006', '3500.00000000'],
            ['0.00000013', '128995.14809078'],
            ['0.00000014', '394682.62366021'],
            ['0.00000017', '225000.00000000'],
            ['0.00000026', '2065.33260000'],
            ['0.00000044', '80591.90728052'],
            ['0.00000045', '1995.23960000'],
            ['0.00000047', '8888.00000000'],
            ['0.00000049', '870270.27283500'],
            ['0.00000099', '239533.71737500'],
            ['0.00000120', '300000.00000000'],
            ['0.00000159', '400000.00000000'],
            ['0.00000189', '509868.71330000'],
            ['0.00000239', '467777.00000000'],
            ['0.00000300', '915226.47257143'],
            ['0.00000333', '24000.00000000'],
            ['0.00000358', '1053936.00000000'],
            ['0.00000477', '1500000.00000000'],
            ['0.00000585', '2333.00000000']
        ]
    }

    # Sample snaphost for trading pair ETHUSD with id = 27
    SNAPSHOT_2 = {
        'buy_price_levels': [
            ['181.95138', '0.69772000'],  # [price, amount]
            ['181.92711', '10.00000000'],
            ['181.87900', '4.58360000'],
            ['179.03010', '278.44851000'],
            ['178.75183', '0.14000000'],
            ['178.70000', '30.12000000'],
            ['178.65989', '0.30000000'],
            ['145.83493', '2000.00000000'],
            ['87.29805', '1.00000000'],
            ['84.89838', '15.00000000'],
            ['83.76751', '0.30000000'],
            ['83.32619', '30.00000000'],
            ['82.74696', '5.05000000'],
            ['79.67613', '20.00000000'],
            ['79.63016', '0.10000000'],
            ['79.49565', '20.00000000'],
            ['79.06932', '5.00000000'],
            ['78.75672', '5.83703010'],
            ['78.74753', '5.00000000'],
            ['78.14991', '1.05000000'],
            ['77.95683', '32.40000000'],
            ['4.80000', '1.00140384'],
            ['4.71000', '2.00000000'],
            ['4.60624', '3.00000000'],
            ['4.59705', '502.00000000'],
            ['4.08218', '3.00000000'],
            ['3.90000', '0.99900000'],
            ['2.12383', '0.47376416'],
            ['0.00001', '93958.39792500'],
            ['0.00000', '1302758.00491772']
        ],
        'sell_price_levels': [
            ['182.11620', '0.32400000'],
            ['182.11637', '40.00000000'],
            ['182.13780', '10.00000000'],
            ['182.16718', '0.56177000'],
            ['182.56700', '8.03190000'],
            ['195.18677', '5.00000000'],
            ['195.90417', '1.00000000'],
            ['196.53970', '7.47687012'],
            ['196.58865', '53.64700000'],
            ['197.28377', '0.01020100'],
            ['197.32200', '0.84601190'],
            ['197.53210', '1.00000000'],
            ['197.72525', '1.00000000'],
            ['197.74364', '0.20000000'],
            ['202.13408', '36.67302000'],
            ['202.27550', '2000.00000000'],
            ['202.33313', '0.10000000'],
            ['202.34233', '4.50000000'],
            ['203.00000', '0.06000000'],
            ['308.11219', '0.15000000'],
            ['309.95166', '0.10000000'],
            ['329.26616', '0.10000000'],
            ['330.00000', '8.59212286'],
            ['330.18590', '0.10000000'],
            ['334.78459', '0.10000000'],
            ['335.70432', '0.15000000'],
            ['387.00000', '1.00000000'],
            ['388.33173', '0.25000000'],
            ['395.00000', '16.00000299'],
            ['395.48729', '0.38169999'],
            ['397.54000', '0.21503973'],
            ['399.00000', '1.00000000'],
            ['199298.00338', '0.01093111'],
            ['200000.60400', '0.01000001'],
            ['247000.00000', '0.10000000']
        ]
    }

    # Sample buy action diff snapshot for trading pair LCXBTC with id = 538
    DIFF_BUY_1 = json.dumps(
        {
            "channel": "price_ladders_cash_lcxbtc_buy",
            "data": json.dumps(
                [
                    ["0.00000001", "1383755.33583919"]
                ]
            ),
            "event": "updated"
        }
    )

    # Sample sell action diff snapshot for trading pair LCXBTC with id = 538
    DIFF_SELL_1 = json.dumps(
        {
            "channel": "price_ladders_cash_lcxbtc_sell",
            "data": json.dumps(
                [
                    ["0.00000003", "375928.38713356"],
                    ["0.00000004", "350000.00000000"],
                    ["0.00000006", "349178.00000000"],
                    ["0.00000009", "353995.00000000"],
                    ["0.00000010", "9500000.00000000"],
                    ["0.00000011", "999990.00000000"],
                    ["0.00000019", "141998.98597671"],
                    ["0.00000022", "141998.98597671"],
                    ["0.00000026", "2065.33260000"],
                    ["0.00000044", "80591.90728052"],
                    ["0.00000045", "1995.23960000"],
                    ["0.00000047", "8888.00000000"],
                    ["0.00000048", "3000000.00000000"],
                    ["0.00000049", "870270.27283500"],
                    ["0.00000099", "239533.71737500"],
                    ["0.00000120", "300000.00000000"],
                    ["0.00000159", "400000.00000000"],
                    ["0.00000189", "509868.71330000"],
                    ["0.00000239", "467777.00000000"],
                    ["0.00000300", "915226.47257143"],
                    ["0.00000333", "24000.00000000"],
                    ["0.00000358", "1053936.00000000"],
                    ["0.00000477", "1500000.00000000"],
                    ["0.00000585", "2333.00000000"],
                    ["0.00000586", "4666.00000000"],
                    ["0.00000587", "3333.00000000"],
                    ["0.00000590", "50000.00000000"],
                    ["0.00000594", "1000000.00000000"],
                    ["0.00000595", "72354.00000000"],
                    ["0.00000596", "12323.00000000"],
                    ["0.00000599", "20000.00000000"],
                    ["0.00000600", "23222.00000000"],
                    ["0.00000610", "23232.00000000"],
                    ["0.00000620", "12555.00000000"],
                    ["0.00000630", "37676.00000000"],
                    ["0.00000640", "12455.00000000"],
                    ["0.00000650", "19898.00000000"],
                    ["0.00000660", "26665.00000000"],
                    ["0.00000670", "29021.00000000"],
                    ["0.00000680", "16642.00000000"]
                ]
            ),
            "event": "updated"
        }
    )

    # Sample buy action diff snapshot for trading pair ETHUSD with id = 27
    DIFF_BUY_2 = json.dumps({
        'channel': 'price_ladders_cash_ethusd_buy',
        'data': json.dumps(
            [
                ["184.81275", "1.24990000"],
                ["184.61510", "3.24800000"],
                ["184.61501", "1.33050000"],
                ["184.61500", "6.02540000"],
                ["184.59376", "0.55230000"],
                ["184.58241", "0.19207100"],
                ["184.53469", "29.21400000"],
                ["184.46948", "2.78646253"],
                ["184.44140", "0.20000000"],
                ["184.41930", "1.30660746"],
                ["184.41010", "1.14500000"],
                ["184.40255", "0.48300000"],
                ["184.38790", "11.29232000"],
                ["184.29203", "0.86680000"],
                ["184.28562", "0.88198300"],
                ["184.20040", "0.99700000"],
                ["184.20039", "5.00000000"],
                ["184.05753", "16.71948013"],
                ["184.05744", "37.12750000"],
                ["183.96590", "1.19400000"],
                ["183.96581", "38.16974000"],
                ["183.78190", "1.03500000"],
                ["183.50730", "14.00000000"],
                ["183.50725", "56.38600000"],
                ["183.50718", "17.85000000"],
                ["183.50669", "551.62751000"],
                ["183.49041", "373.07825000"],
                ["183.32356", "17.68000000"],
                ["183.14023", "19.44800000"],
                ["182.95265", "185.00000000"],
                ["182.94265", "321.00000000"],
                ["182.94173", "240.00000000"],
                ["182.90000", "30.12000000"],
                ["182.80594", "224.83304619"],
                ["182.80428", "69.83796839"],
                ["182.19789", "37.94100000"],
                ["182.00161", "0.10988910"],
                ["182.00000", "2.00000000"],
                ["181.89691", "97.89201000"],
                ["181.89673", "270.46800000"]
            ]
        ),
        'event': 'updated'
    })

    # Sample sell action diff snapshot for trading pair ETHUSD with id = 27
    DIFF_SELL_2 = json.dumps(
        {
            'channel': 'price_ladders_cash_ethusd_sell',
            'data': json.dumps(
                [
                    ["184.86314", "19.71400000"],
                    ["184.94590", "0.48700000"],
                    ["184.94604", "16.99300000"],
                    ["184.99744", "1.25000000"],
                    ["184.99840", "0.49350000"],
                    ["185.00861", "4.64960000"],
                    ["185.13290", "0.16700000"],
                    ["185.13300", "6.02540000"],
                    ["185.20921", "1.01180000"],
                    ["185.21568", "16.68150000"],
                    ["185.27519", "0.52493193"],
                    ["185.30093", "1.05529686"],
                    ["185.32010", "0.17900000"],
                    ["185.32025", "2.14700000"],
                    ["185.32026", "31.47275456"],
                    ["185.32035", "58.69600000"],
                    ["185.62000", "0.33030000"],
                    ["185.63980", "0.15400000"],
                    ["185.67379", "11.29231000"],
                    ["185.67452", "12.00000000"],
                    ["185.67455", "38.16973000"],
                    ["185.67456", "5.04200000"],
                    ["185.82550", "0.15300000"],
                    ["185.84188", "551.12750000"],
                    ["185.86023", "2.50200000"],
                    ["185.92867", "2.21200000"],
                    ["186.04247", "188.00000000"],
                    ["186.05247", "352.00000000"],
                    ["186.05338", "37.50000000"],
                    ["186.05447", "373.07824000"],
                    ["186.12857", "2.18900000"],
                    ["186.12858", "5.00000000"],
                    ["186.14691", "10.00000000"],
                    ["186.31470", "2.46700000"],
                    ["186.40889", "4.25277422"],
                    ["186.53451", "270.46800000"],
                    ["186.67924", "183.08962000"],
                    ["186.89400", "14.49633789"],
                    ["187.00000", "10.00000000"],
                    ["187.04556", "11.49633789"]
                ]
            ),
            'event': 'updated'
        }
    )
    # Sample response of successful subscription to a order book diff ws channel
    WS_PUSHER_SUBSCRIPTION_SUCCESS_RESPONSE = json.dumps(
        {
            'channel': 'price_ladders_cash_lcxbtc_sell',
            'data': json.dumps({}),
            'event': 'pusher_internal:subscription_succeeded'
        }
    )

    # Sample response when socket client is successfully established
    WS_CLIENT_CONNECTION_SUCCESS_RESPONSE = json.dumps(
        {
            'data': json.dumps(
                {
                    "activity_timeout": 120,
                    "socket_id": "3000276318.8566049469"
                }
            ),
            'event': 'pusher:connection_established'
        }
    )

    FIAT_ACCOUNTS = [
        {
            "id": 4695,
            "balance": 10000.1773,
            "reserved_balance": 0.0,
            "currency": "USD",
            "currency_symbol": "$",
            "pusher_channel": "user_3020_account_usd",
            "lowest_offer_interest_rate": 0.00020,
            "highest_offer_interest_rate": 0.00060,
            "currency_type": "fiat",
            "exchange_rate": 1.0
        }
    ]

    CRYPTO_ACCOUNTS = [
        {
            "id": 4668,
            "balance": 5,
            "reserved_balance": 0.0,
            "currency": "ETH",
            "currency_symbol": "",
            "pusher_channel": "user_3020_account_btc",
            "minimum_withdraw": 0.02,
            "lowest_offer_interest_rate": 0.00049,
            "highest_offer_interest_rate": 0.05000,
            "currency_type": "crypto",
            "address": "1F25zWAQ1BAAmppNxLV3KtK6aTNhxNg5Hg"
        }
    ]
    ORDERS_GET = {
        "models": [
            {"id": 2017991459, "order_type": "market", "quantity": "1.0", "disc_quantity": "0.0",
             "iceberg_total_quantity": "0.0", "side": "buy", "filled_quantity": "1.0", "price": "0.00079",
             "created_at": 1579499313, "updated_at": 1579499313, "status": "filled", "leverage_level": 1,
             "source_exchange": None, "product_id": 500, "margin_type": None, "take_profit": None,
             "stop_loss": None, "trading_type": "spot", "product_code": "CASH", "funding_currency": "ETH",
             "crypto_account_id": None, "currency_pair_code": "CELETH", "average_price": "0.00079",
             "target": "spot", "order_fee": "0.00000079", "source_action": "manual", "unwound_trade_id": None,
             "trade_id": None, "client_order_id": "buy-CEL-ETH-1579499312988332", "settings": None,
             "trailing_stop_type": None, "trailing_stop_value": None, "executions": [
                 {"id": 253095921, "quantity": "1.0", "price": "0.00079", "taker_side": "buy",
                  "created_at": 1579499313, "my_side": "buy"}], "stop_triggered_time": None}],
        "current_page": 1,
        "total_pages": 1
    }

    BUY_MARKET_ORDER = {
        "id": 2017991459, "order_type": "market", "quantity": "1.0", "disc_quantity": "0.0",
        "iceberg_total_quantity": "0.0", "side": "buy", "filled_quantity": "1.0", "price": 0.00079,
        "created_at": 1579499313, "updated_at": 1579499313, "status": "filled", "leverage_level": 1,
        "source_exchange": "QUOINE", "product_id": 500, "margin_type": None, "take_profit": None,
        "stop_loss": None, "trading_type": "spot", "product_code": "CASH", "funding_currency": "ETH",
        "crypto_account_id": None, "currency_pair_code": "CELETH", "average_price": 0.0, "target": "spot",
        "order_fee": 0.0, "source_action": "manual", "unwound_trade_id": None, "trade_id": None,
        "client_order_id": "buy-CEL-ETH-1579499312988332"}

    ORDERS_GET_AFTER_BUY = ORDERS_GET

    SELL_MARKET_ORDER = {
        "id": 2017991755, "order_type": "market", "quantity": "1.0", "disc_quantity": "0.0",
        "iceberg_total_quantity": "0.0", "side": "sell", "filled_quantity": "1.0", "price": 0.00078,
        "created_at": 1579499322, "updated_at": 1579499322, "status": "filled", "leverage_level": 1,
        "source_exchange": "QUOINE", "product_id": 500, "margin_type": None, "take_profit": None,
        "stop_loss": None, "trading_type": "spot", "product_code": "CASH", "funding_currency": "ETH",
        "crypto_account_id": None, "currency_pair_code": "CELETH", "average_price": 0.0, "target": "spot",
        "order_fee": 0.0, "source_action": "manual", "unwound_trade_id": None, "trade_id": None,
        "client_order_id": "sell-CEL-ETH-1579499322010384"}

    ORDERS_GET_AFTER_MARKET_SELL = {
        "models": [
            {
                "id": 2017991755, "order_type": "market", "quantity": "1.0", "disc_quantity": "0.0",
                "iceberg_total_quantity": "0.0", "side": "sell", "filled_quantity": "1.0", "price": "0.00078",
                "created_at": 1579499322, "updated_at": 1579499322, "status": "filled", "leverage_level": 1,
                "source_exchange": None, "product_id": 500, "margin_type": None, "take_profit": None, "stop_loss": None,
                "trading_type": "spot", "product_code": "CASH", "funding_currency": "ETH", "crypto_account_id": None,
                "currency_pair_code": "CELETH", "average_price": "0.00078", "target": "spot", "order_fee": "0.00000078",
                "source_action": "manual", "unwound_trade_id": None, "trade_id": None,
                "client_order_id": "sell-CEL-ETH-1579499322010384", "settings": None, "trailing_stop_type": None,
                "trailing_stop_value": None, "executions": [
                    {
                        "id": 253095951, "quantity": "1.0", "price": "0.00078",
                        "taker_side": "sell", "created_at": 1579499322, "my_side": "sell"
                    }
                ],
                "stop_triggered_time": None
            }
        ], "total_pages": 10000,
        "current_page": 1}

    FILLED_BUY_LIMIT_ORDER = {
        "id": 2021509801, "order_type": "limit", "quantity": "1.0", "disc_quantity": "0.0",
        "iceberg_total_quantity": "0.0", "side": "buy", "filled_quantity": "1.0", "price": 0.000819,
        "created_at": 1579575661, "updated_at": 1579575661, "status": "filled", "leverage_level": 1,
        "source_exchange": "QUOINE", "product_id": 500, "margin_type": None, "take_profit": None,
        "stop_loss": None, "trading_type": "spot", "product_code": "CASH", "funding_currency": "ETH",
        "crypto_account_id": None, "currency_pair_code": "CELETH", "average_price": 0.0,
        "target": "spot", "order_fee": 0.0, "source_action": "manual", "unwound_trade_id": None,
        "trade_id": None, "client_order_id": "buy-CEL-ETH-1579575660659385"}

    ORDERS_GET_AFTER_LIMIT_BUY = {
        "models": [
            {"id": 2021509801, "order_type": "limit", "quantity": "1.0", "disc_quantity": "0.0",
             "iceberg_total_quantity": "0.0", "side": "buy", "filled_quantity": "1.0", "price": "0.000819",
             "created_at": 1579575661, "updated_at": 1579575661, "status": "filled", "leverage_level": 1,
             "source_exchange": None, "product_id": 500, "margin_type": None, "take_profit": None,
             "stop_loss": None, "trading_type": "spot", "product_code": "CASH", "funding_currency": "ETH",
             "crypto_account_id": None, "currency_pair_code": "CELETH", "average_price": "0.00078",
             "target": "spot", "order_fee": "0.00000078", "source_action": "manual", "unwound_trade_id": None,
             "trade_id": None, "client_order_id": "buy-CEL-ETH-1579575660659385", "settings": None,
             "trailing_stop_type": None, "trailing_stop_value": None, "executions": [
                 {"id": 253491440, "quantity": "1.0", "price": "0.00078", "taker_side": "buy", "created_at": 1579575661,
                  "my_side": "buy"}], "stop_triggered_time": None}
        ],
        "current_page": 1,
        "total_pages": 1
    }

    FILLED_SELL_LIMIT_ORDER = {
        "id": 2021511071, "order_type": "limit", "quantity": "1.0", "disc_quantity": "0.0",
        "iceberg_total_quantity": "0.0", "side": "sell", "filled_quantity": "1.0", "price": 0.00072226,
        "created_at": 1579575692, "updated_at": 1579575692, "status": "filled", "leverage_level": 1,
        "source_exchange": "QUOINE", "product_id": 500, "margin_type": None, "take_profit": None,
        "stop_loss": None, "trading_type": "spot", "product_code": "CASH", "funding_currency": "ETH",
        "crypto_account_id": None, "currency_pair_code": "CELETH", "average_price": 0.0,
        "target": "spot", "order_fee": 0.0, "source_action": "manual", "unwound_trade_id": None,
        "trade_id": None, "client_order_id": "sell-CEL-ETH-1579575692882646"}

    ORDERS_GET_AFTER_LIMIT_SELL = {
        "models": [
            {
                "id": 2021511071, "order_type": "market", "quantity": "1.0", "disc_quantity": "0.0",
                "iceberg_total_quantity": "0.0", "side": "sell", "filled_quantity": "1.0", "price": "0.00072226",
                "created_at": 1579499322, "updated_at": 1579499322, "status": "filled", "leverage_level": 1,
                "source_exchange": None, "product_id": 500, "margin_type": None, "take_profit": None, "stop_loss": None,
                "trading_type": "spot", "product_code": "CASH", "funding_currency": "ETH", "crypto_account_id": None,
                "currency_pair_code": "CELETH", "average_price": "0.00078", "target": "spot", "order_fee": "0.00000078",
                "source_action": "manual", "unwound_trade_id": None, "trade_id": None,
                "client_order_id": "sell-CEL-ETH-1579575692882646", "settings": None, "trailing_stop_type": None,
                "trailing_stop_value": None, "executions": [
                    {
                        "id": 253095951, "quantity": "1.0", "price": "0.00072226",
                        "taker_side": "sell", "created_at": 1579499322,
                        "my_side": "sell"
                    }
                ],
                "stop_triggered_time": None
            }
        ], "total_pages": 10000,
        "current_page": 1}

    BUY_LIMIT_ORDER_BEFORE_CANCEL = {
        "id": 2022033542, "order_type": "limit", "quantity": "1.0", "disc_quantity": "0.0",
        "iceberg_total_quantity": "0.0", "side": "sell", "filled_quantity": "0.0",
        "price": 0.00116998, "created_at": 1579588095, "updated_at": 1579588095, "status": "live",
        "leverage_level": 1, "source_exchange": "QUOINE", "product_id": 500, "margin_type": None,
        "take_profit": None, "stop_loss": None, "trading_type": "spot", "product_code": "CASH",
        "funding_currency": "ETH", "crypto_account_id": None, "currency_pair_code": "CELETH",
        "average_price": 0.0, "target": "spot", "order_fee": 0.0, "source_action": "manual",
        "unwound_trade_id": None, "trade_id": None,
        "client_order_id": "sell-CEL-ETH-1579588095991611"}

    SELL_LIMIT_ORDER_BEFORE_CANCEL = {
        "id": 2022033543, "order_type": "limit", "quantity": "1.0", "disc_quantity": "0.0",
        "iceberg_total_quantity": "0.0", "side": "buy", "filled_quantity": "0.0",
        "price": 0.0005551, "created_at": 1579588095, "updated_at": 1579588095, "status": "live",
        "leverage_level": 1, "source_exchange": "QUOINE", "product_id": 500, "margin_type": None,
        "take_profit": None, "stop_loss": None, "trading_type": "spot", "product_code": "CASH",
        "funding_currency": "ETH", "crypto_account_id": None, "currency_pair_code": "CELETH",
        "average_price": 0.0, "target": "spot", "order_fee": 0.0, "source_action": "manual",
        "unwound_trade_id": None, "trade_id": None,
        "client_order_id": "buy-CEL-ETH-1579588095991610"}

    SELL_LIMIT_ORDER_AFTER_CANCEL = {
        "id": 2022033542, "order_type": "limit", "quantity": "1.0", "disc_quantity": "0.0",
        "iceberg_total_quantity": "0.0", "side": "sell", "filled_quantity": "0.0",
        "price": 0.00116998, "created_at": 1579588095, "updated_at": 1579588097,
        "status": "cancelled", "leverage_level": 1, "source_exchange": "QUOINE", "product_id": 500,
        "margin_type": None, "take_profit": None, "stop_loss": None, "trading_type": "spot",
        "product_code": "CASH", "funding_currency": "ETH", "crypto_account_id": None,
        "currency_pair_code": "CELETH", "average_price": 0.0, "target": "spot", "order_fee": 0.0,
        "source_action": "manual", "unwound_trade_id": None, "trade_id": None,
        "client_order_id": "sell-CEL-ETH-1579588095991611"}

    BUY_LIMIT_ORDER_AFTER_CANCEL = {
        "id": 2022033543, "order_type": "limit", "quantity": "1.0", "disc_quantity": "0.0",
        "iceberg_total_quantity": "0.0", "side": "buy", "filled_quantity": "0.0", "price": 0.0005551,
        "created_at": 1579588095, "updated_at": 1579588097, "status": "cancelled",
        "leverage_level": 1, "source_exchange": "QUOINE", "product_id": 500, "margin_type": None,
        "take_profit": None, "stop_loss": None, "trading_type": "spot", "product_code": "CASH",
        "funding_currency": "ETH", "crypto_account_id": None, "currency_pair_code": "CELETH",
        "average_price": 0.0, "target": "spot", "order_fee": 0.0, "source_action": "manual",
        "unwound_trade_id": None, "trade_id": None, "client_order_id": "buy-CEL-ETH-1579588095991610"}

    ORDER_SAVE_RESTORE = {
        "id": 2022217546, "order_type": "limit", "quantity": "1.0", "disc_quantity": "0.0",
        "iceberg_total_quantity": "0.0", "side": "buy", "filled_quantity": "0.0", "price": 0.00063439,
        "created_at": 1579592560, "updated_at": 1579592560, "status": "live", "leverage_level": 1,
        "source_exchange": "QUOINE", "product_id": 500, "margin_type": None, "take_profit": None,
        "stop_loss": None, "trading_type": "spot", "product_code": "CASH", "funding_currency": "ETH",
        "crypto_account_id": None, "currency_pair_code": "CELETH", "average_price": 0.0,
        "target": "spot", "order_fee": 0.0, "source_action": "manual", "unwound_trade_id": None,
        "trade_id": None, "client_order_id": "buy-CEL-ETH-1579592561189772"}

    ORDER_CANCEL_SAVE_RESTORE = {
        "id": 2022217546, "order_type": "limit", "quantity": "1.0", "disc_quantity": "0.0",
        "iceberg_total_quantity": "0.0", "side": "buy", "filled_quantity": "0.0",
        "price": 0.00063439, "created_at": 1579592560, "updated_at": 1579592562,
        "status": "cancelled", "leverage_level": 1, "source_exchange": "QUOINE",
        "product_id": 500, "margin_type": None, "take_profit": None, "stop_loss": None,
        "trading_type": "spot", "product_code": "CASH", "funding_currency": "ETH",
        "crypto_account_id": None, "currency_pair_code": "CELETH", "average_price": 0.0,
        "target": "spot", "order_fee": 0.0, "source_action": "manual",
        "unwound_trade_id": None, "trade_id": None,
        "client_order_id": "buy-CEL-ETH-1579592561189772"}

    ORDERS_UNFILLED = {
        'models': [
            {
                'id': 3074231238, 'order_type': 'limit', 'quantity': '1.0', 'disc_quantity': '0.0',
                'iceberg_total_quantity': '0.0', 'side': 'buy', 'filled_quantity': '0.0',
                'price': '0.000851', 'created_at': 1597391883, 'updated_at': 1597391883,
                'status': 'live', 'leverage_level': 1, 'source_exchange': 0, 'product_id': 500,
                'margin_type': None, 'take_profit': None, 'stop_loss': None, 'trading_type': 'spot',
                'product_code': 'CASH', 'funding_currency': 'ETH', 'crypto_account_id': None,
                'currency_pair_code': 'CELETH', 'average_price': '0.0', 'target': 'spot',
                'order_fee': '0.0', 'source_action': 'manual', 'unwound_trade_id': None,
                'trade_id': None, 'client_order_id': 'buy-CEL-ETH-1597391882834204',
                'settings': None, 'trailing_stop_type': None, 'trailing_stop_value': None,
                'executions': [], 'stop_triggered_time': None
            }
        ], 'total_pages': 10000, 'current_page': 1}
