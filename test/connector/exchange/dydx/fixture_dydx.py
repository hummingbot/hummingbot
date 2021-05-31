class FixtureDydx:
    # General Exchange Info
    MARKETS = {"markets":
               {"WETH-DAI":
                {"name": "WETH-DAI",
                 "baseCurrency": {
                     "currency": "WETH",
                     "decimals": 18,
                     "soloMarketId": 0
                 },
                 "quoteCurrency": {
                     "currency": "DAI",
                     "decimals": 18,
                     "soloMarketId": 3
                 },
                 "minimumTickSize": "0.01",
                 "minimumOrderSize": "10",
                 "smallOrderThreshold": "200",
                 "makerFee": "0",
                 "largeTakerFee": "0.003",
                 "smallTakerFee": "0.01",
                 "fillOrKillMinFee": "32640972000000000000"
                 },
                "WETH-USDC":
                {"name": "WETH-USDC",
                 "baseCurrency": {
                     "currency": "WETH",
                     "decimals": 18,
                     "soloMarketId": 0
                 },
                 "quoteCurrency": {
                     "currency": "USDC",
                     "decimals": 6,
                     "soloMarketId": 2
                 },
                 "minimumTickSize": "0.00000000000001",
                 "minimumOrderSize": "10",
                 "smallOrderThreshold": "200",
                 "makerFee": "0",
                 "largeTakerFee": "0.003",
                 "smallTakerFee": "0.01",
                 "fillOrKillMinFee": "32640972"
                 },
                "DAI-USDC":
                {"name": "DAI-USDC",
                 "baseCurrency": {
                     "currency": "DAI",
                     "decimals": 18,
                     "soloMarketId": 3
                 },
                 "quoteCurrency": {
                     "currency": "USDC",
                     "decimals": 6,
                     "soloMarketId": 2
                 },
                 "minimumTickSize": "0.0000000000000001",
                 "minimumOrderSize": "2000",
                 "smallOrderThreshold": "125000",
                 "makerFee": "0",
                 "largeTakerFee": "0.002",
                 "smallTakerFee": "0.01",
                 "fillOrKillMinFee": "32640972"
                 },
                "PBTC-USDC":
                {"name": "PBTC-USDC",
                 "decimals": 8,
                 "minimumTickSize": "0.01",
                 "minimumOrderSize": "1000000",
                 "smallOrderThreshold": "75000000",
                 "makerFee": "-0.00025",
                 "largeTakerFee": "0.002",
                 "smallTakerFee": "0.01",
                 "fillOrKillMinFee": "17952535"},
                "WETH-PUSD":
                {"name": "WETH-PUSD",
                 "decimals": 6,
                 "minimumTickSize": "0.0000000000001",
                 "minimumOrderSize": "100000000",
                 "smallOrderThreshold": "7500000000",
                 "makerFee": "-0.00025",
                 "largeTakerFee": "0.002",
                 "smallTakerFee": "0.01",
                 "fillOrKillMinFee": "30030000000000000"
                 },
                "PLINK-USDC":
                {"name": "PLINK-USDC",
                 "decimals": 6,
                 "minimumTickSize": "0.005",
                 "minimumOrderSize": "15000000",
                 "smallOrderThreshold": "600000000",
                 "makerFee": "-0.00025",
                 "largeTakerFee": "0.002",
                 "smallTakerFee": "0.01",
                 "fillOrKillMinFee": "17952535"
                 }
                }
               }

    BALANCES = {
        "version": 1,
        "owner": "0x0913017c740260fea4b2c62828a4008ca8b0d6e4",
        "number": "782499163583804925933142394090321739117\
                   41268194868200833150293576330928686520",
        "uuid": "e8e16eb1-fa69-467a-a1b5-f6c612dc50c3",
        "balances": {
            "0": {
                "marketId": 0,
                "par": "0",
                "wei": "41000000000000000000",
                "pendingWei": "0",
                "orderNumber": "1128193300920000",
                "expiresAt": None,
                "expiryAddress": None,
                "expiryOrderNumber": None,
                "isPendingBlock": False
            },
            "1": {
                "marketId": 1,
                "par": "0",
                "wei": "100000000000000",
                "pendingWei": "0",
                "expiresAt": None,
                "orderNumber": None,
                "expiryAddress": None,
                "expiryOrderNumber": None,
                "isPendingBlock": False
            },
            "2": {
                "marketId": 2,
                "par": "0",
                "wei": "100000000000000",
                "pendingWei": "0",
                "expiresAt": None,
                "orderNumber": None,
                "expiryAddress": None,
                "expiryOrderNumber": None,
                "isPendingBlock": False
            },
            "3": {
                "marketId": 3,
                "par": "0",
                "wei": "100000000000000",
                "pendingWei": "0",
                "orderNumber": "1128193401090000",
                "expiresAt": None,
                "expiryAddress": None,
                "expiryOrderNumber": None,
                "isPendingBlock": False
            }
        },
        "confirmedBalances": {
            "0": {
                "marketId": 0,
                "par": "0",
                "wei": "410000000000000000000.0",
                "pendingWei": "0",
                "orderNumber": "1128193300920000",
                "expiresAt": None,
                "expiryAddress": None,
                "expiryOrderNumber": None,
                "isPendingBlock": False
            },
            "1": {
                "marketId": 1,
                "par": "0",
                "wei": "100000000000000",
                "pendingWei": "0",
                "expiresAt": None,
                "orderNumber": None,
                "expiryAddress": None,
                "expiryOrderNumber": None,
                "isPendingBlock": False
            },
            "2": {
                "marketId": 2,
                "par": "0",
                "wei": "100000000000000",
                "pendingWei": "0",
                "expiresAt": None,
                "orderNumber": None,
                "expiryAddress": None,
                "expiryOrderNumber": None,
                "isPendingBlock": False
            },
            "3": {
                "marketId": 3,
                "par": "0",
                "wei": "100000000000000.000000000000000000",
                "pendingWei": "0",
                "orderNumber": "1128193401090000",
                "expiresAt": None,
                "expiryAddress": None,
                "expiryOrderNumber": None,
                "isPendingBlock": False
            }
        }
    }

    WS_AFTER_BUY_1 = {
        "type": "channel_data",
        "connection_id": "a17dcc8e-9468-4308-96f5-3f458bf485d9",
        "message_id": 4,
        "channel": "orders",
        "id": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
        "contents": {
            "type": "ORDER",
            "order": {
                "uuid": "29c9d044-4e13-468f-8cf4-7e529e614296",
                "id": "0xb0751a113c759779ff5fd6a53b37b\
                  26211a9f8845d443323b9f877f32d9aafd9",
                "createdAt": "2020-01-14T22:22:19.131Z",
                "status": "OPEN",
                "accountOwner": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
                "accountNumber": "0",
                "orderType": "LIMIT",
                "fillOrKill": False,
                "postOnly": False,
                "market": "WETH-USDC",
                "side": "BUY",
                "baseAmount": "40000000000000000000",
                "quoteAmount": "20018000",
                "filledAmount": "0",
                "price": "0.0000000000010009",
                "cancelReason": None,
                "updatedAt": "2020-01-14T22:22:19.153Z"
            }
        }
    }

    WS_AFTER_MAKER_BUY_1 = {
        "type": "channel_data",
        "connection_id": "a17dcc8e-9468-4308-96f5-3f458bf485d9",
        "message_id": 4,
        "channel": "orders",
        "id": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
        "contents": {
            "type": "ORDER",
            "order": {
                "uuid": "29c9d044-4e13-468f-8cf4-7e529e614296",
                "id": "0xb0751a113c759779ff5fd6a53b37b\
                  26211a9f8845d443323b9f877f32d9aafd9",
                "createdAt": "2020-01-14T22:22:19.131Z",
                "status": "OPEN",
                "accountOwner": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
                "accountNumber": "0",
                "orderType": "LIMIT",
                "fillOrKill": False,
                "postOnly": False,
                "market": "WETH-USDC",
                "side": "BUY",
                "baseAmount": "40000000000000000000",
                "quoteAmount": "20018000",
                "filledAmount": "0",
                "price": "0.0000000000010009",
                "cancelReason": None,
                "updatedAt": "2020-01-14T22:22:19.153Z"
            }
        }
    }

    WS_AFTER_BUY_2 = {
        "type": "channel_data",
        "connection_id": "839bd50b-77f6-4568-b758-cdc4b2962efb",
        "message_id": 5,
        "channel": "orders",
        "id": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
        "contents": {
            "type": "ORDER",
            "order": {
                "uuid": "5137f016-80dc-47e8-89b5-aee3b2db15d0",
                "id": "0xb0751a113c759779ff5fd6a53b37b2\
                  6211a9f8845d443323b9f877f32d9aafd9",
                "createdAt": "2020-01-14T21:15:13.561Z",
                "status": "FILLED",
                "accountOwner": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
                "accountNumber": "0",
                "orderType": "LIMIT",
                "fillOrKill": False,
                "postOnly": False,
                "market": "WETH-USDC",
                "side": "BUY",
                "baseAmount": "40000000000000000000",
                "quoteAmount": "19900000",
                "filledAmount": "40000000000000000000",
                "price": "0.000000000000995",
                "cancelReason": None,
                "updatedAt": "2020-01-14T21:15:14.020Z"
            }
        }
    }

    WS_AFTER_BUY_3 = {
        "type": "channel_data",
        "connection_id": "839bd50b-77f6-4568-b758-cdc4b2962efb",
        "message_id": 6,
        "channel": "orders",
        "id": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
        "contents": {
            "type": "FILL",
            "fill": {
                "uuid": "5a2efda1-39f7-44c3-a62b-d5ca925937f9",
                "status": "CONFIRMED",
                "orderId": "0xb0751a113c759779ff5fd6a53b3\
                  7b26211a9f8845d443323b9f877f32d9aafd9",
                "transactionHash": "0xbc331c8894dbe19f65cf4132a98f\
                  f81793d1a9e5a437ecf62801d28f4d09caa9",
                "createdAt": "2020-01-14T21:15:14.008Z",
                "updatedAt": "2020-01-14T21:15:14.026Z",
                "amount": "40000000000000000000",
                "price": "0.000000000001",
                "side": "BUY",
                "market": "WETH-USDC",
                "liquidity": "MAKER",
                "accountOwner": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c"
            }
        }
    }

    WS_AFTER_SELL_1 = {
        "type": "channel_data",
        "connection_id": "a17dcc8e-9468-4308-96f5-3f458bf485d9",
        "message_id": 4,
        "channel": "orders",
        "id": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
        "contents": {
            "type": "ORDER",
            "order": {
                "uuid": "29c9d044-4e13-468f-8cf4-7e529e614296",
                "id": "0x03dfd18edc2f26fc9298edcd28ca6cad4971bd\
                  1f44d40253d5154b0d1f217680",
                "createdAt": "2020-01-14T22:22:19.131Z",
                "status": "OPEN",
                "accountOwner": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
                "accountNumber": "0",
                "orderType": "LIMIT",
                "fillOrKill": False,
                "postOnly": False,
                "market": "WETH-USDC",
                "side": "SELL",
                "baseAmount": "40000000000000000000",
                "quoteAmount": "20018000",
                "filledAmount": "0",
                "price": "0.0000000000010009",
                "cancelReason": None,
                "updatedAt": "2020-01-14T22:22:19.153Z"
            }
        }
    }

    WS_AFTER_SELL_2 = {
        "type": "channel_data",
        "connection_id": "839bd50b-77f6-4568-b758-cdc4b2962efb",
        "message_id": 5,
        "channel": "orders",
        "id": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
        "contents": {
            "type": "ORDER",
            "order": {
                "uuid": "5137f016-80dc-47e8-89b5-aee3b2db15d0",
                "id": "0x03dfd18edc2f26fc9298edcd28ca6cad4\
                  971bd1f44d40253d5154b0d1f217680",
                "createdAt": "2020-01-14T21:15:13.561Z",
                "status": "FILLED",
                "accountOwner": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
                "accountNumber": "0",
                "orderType": "LIMIT",
                "fillOrKill": False,
                "postOnly": False,
                "market": "WETH-USDC",
                "side": "SELL",
                "baseAmount": "40000000000000000000",
                "quoteAmount": "19900000",
                "filledAmount": "40000000000000000000",
                "price": "0.000000000000995",
                "cancelReason": None,
                "updatedAt": "2020-01-14T21:15:14.020Z"
            }
        }
    }

    WS_AFTER_SELL_3 = {
        "type": "channel_data",
        "connection_id": "839bd50b-77f6-4568-b758-cdc4b2962efb",
        "message_id": 6,
        "channel": "orders",
        "id": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
        "contents": {
            "type": "FILL",
            "fill": {
                "uuid": "5a2efda1-39f7-44c3-a62b-d5ca925937f9",
                "status": "CONFIRMED",
                "orderId": "0x03dfd18edc2f26fc9298edcd28ca6c\
                  ad4971bd1f44d40253d5154b0d1f217680",
                "transactionHash": "0xbc331c8894dbe19f65cf4132a98ff\
                  81793d1a9e5a437ecf62801d28f4d09caa9",
                "createdAt": "2020-01-14T21:15:14.008Z",
                "updatedAt": "2020-01-14T21:15:14.026Z",
                "amount": "40000000000000000000",
                "price": "0.000000000001",
                "side": "SELL",
                "market": "WETH-USDC",
                "liquidity": "MAKER",
                "accountOwner": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c"
            }
        }
    }

    BUY_LIMIT_ORDER = {
        "order": {
            "uuid": "c8087842-b74c-4e29-8a3f-1c2207d4a758",
            "id": "0xb0751a113c759779ff5fd6a53b37b26211a\
              9f8845d443323b9f877f32d9aafd9",
            "clientId": None,
            "status": "PENDING",
            "accountOwner": "0x3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9",
            "accountNumber": "0",
            "orderType": "LIMIT",
            "fillOrKill": False,
            "postOnly": False,
            "triggerPrice": None,
            "market": "WETH-USDC",
            "side": "BUY",
            "baseAmount": "40000000000000000000",
            "quoteAmount": "238610000",
            "filledAmount": "0",
            "price": "0.00000000023861",
            "cancelReason": None,
            "trailingPercent": None,
            "createdAt": "2020-07-06T19:41:55.109Z",
            "updatedAt": "2020-07-06T19:41:55.109Z",
            "expiresAt": "2020-08-03T19:56:53.000Z"
        }
    }

    SELL_LIMIT_ORDER = {
        "order": {
            "uuid": "c8087842-b74c-4e29-8a3f-1c2207d4a758",
            "id": "0x03dfd18edc2f26fc9298edcd28ca6cad4\
              971bd1f44d40253d5154b0d1f217680",
            "clientId": None,
            "status": "PENDING",
            "accountOwner": "0x3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9",
            "accountNumber": "0",
            "orderType": "LIMIT",
            "fillOrKill": False,
            "postOnly": False,
            "triggerPrice": None,
            "market": "WETH-USDC",
            "side": "SELL",
            "baseAmount": "10",
            "quoteAmount": "238610000",
            "filledAmount": "0",
            "price": "0.00000000023861",
            "cancelReason": None,
            "trailingPercent": None,
            "createdAt": "2020-07-06T19:41:55.109Z",
            "updatedAt": "2020-07-06T19:41:55.109Z",
            "expiresAt": "2020-08-03T19:56:53.000Z"
        }
    }

    BUY_LIMIT_MAKER_ORDER = {
        "order": {
            "uuid": "c8087842-b74c-4e29-8a3f-1c2207d4a758",
            "id": "0xb0751a113c759779ff5fd6a53b37b2\
              6211a9f8845d443323b9f877f32d9aafd9",
            "clientId": None,
            "status": "PENDING",
            "accountOwner": "0x3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9",
            "accountNumber": "0",
            "orderType": "LIMIT",
            "fillOrKill": False,
            "postOnly": True,
            "triggerPrice": None,
            "market": "WETH-USDC",
            "side": "BUY",
            "baseAmount": "10",
            "quoteAmount": "238610000",
            "filledAmount": "0",
            "price": "0.00000000023861",
            "cancelReason": None,
            "trailingPercent": None,
            "createdAt": "2020-07-06T19:41:55.109Z",
            "updatedAt": "2020-07-06T19:41:55.109Z",
            "expiresAt": "2020-08-03T19:56:53.000Z"
        }
    }

    SELL_LIMIT_MAKER_ORDER = {
        "order": {
            "uuid": "c8087842-b74c-4e29-8a3f-1c2207d4a758",
            "id": "0x03dfd18edc2f26fc9298edcd28ca6c\
              ad4971bd1f44d40253d5154b0d1f217680",
            "clientId": None,
            "status": "PENDING",
            "accountOwner": "0x3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9",
            "accountNumber": "0",
            "orderType": "LIMIT",
            "fillOrKill": False,
            "postOnly": True,
            "triggerPrice": None,
            "market": "WETH-USDC",
            "side": "SELL",
            "baseAmount": "10",
            "quoteAmount": "238610000",
            "filledAmount": "0",
            "price": "0.00000000023861",
            "cancelReason": None,
            "trailingPercent": None,
            "createdAt": "2020-07-06T19:41:55.109Z",
            "updatedAt": "2020-07-06T19:41:55.109Z",
            "expiresAt": "2020-08-03T19:56:53.000Z"
        }
    }

    FILLS = {
        "fills": [
            {
                "uuid": "8994f3a0-f5a6-4aa8-a19f-075f076ad999",
                "createdAt": "2020-01-15T00:50:17.042Z",
                "transactionHash": "0x8350fae014702ce62c73762f9f\
                  38d29704d9dbf1909dd1fc02526c897207a35a",
                "status": "CONFIRMED",
                "market": "WETH-USDC",
                "side": "SELL",
                "accountOwner": "0x5f5a46a8471f60b1e9f2ed0b8fc21ba8b48887d8",
                "accountNumber": "0",
                "orderId": "0x03dfd18edc2f26fc9298edcd28ca6c\
                  ad4971bd1f44d40253d5154b0d1f217680",
                "orderClientId": None,
                "price": "169.98523710095444091",
                "amount": "100000000000000000",
                "feeAmount": "0",
                "liquidity": "MAKER"
            },
            {
                "uuid": "15a0d654-76d6-4bb4-ad1a-15c088def1b7",
                "createdAt": "2020-01-15T00:49:55.580Z",
                "transactionHash": "0x7419547186ee1c54785162fd6752\
                  f4c2e88ca09f0944d8b9c038a0e2cf169a8c",
                "status": "CONFIRMED",
                "market": "WETH-USDC",
                "side": "BUY",
                "accountOwner": "0x5f5a46a8471f60b1e9f2ed0b8fc21ba8b48887d8",
                "accountNumber": "0",
                "orderId": "0xb0751a113c759779ff5fd6a53b37b\
                  26211a9f8845d443323b9f877f32d9aafd9",
                "orderClientId": "d025f607-9827-4043-9445-aec9c4b2e9af",
                "price": "170.94678134323509863",
                "amount": "100000000000000000",
                "feeAmount": "0",
                "liquidity": "MAKER"
            }
        ]
    }

    CANCEL_ORDER_BUY = {
        "type": "channel_data",
        "connection_id": "8c510abb-2e45-4f9a-be17-9c992b441da8",
        "message_id": 7,
        "channel": "orders",
        "id": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
        "contents": {
            "type": "ORDER",
            "order": {
                "uuid": "d98b3b81-8ffa-45c8-8e1a-38a31ab9f690",
                "id": "0xb0751a113c759779ff5fd6a53b37\
                  b26211a9f8845d443323b9f877f32d9aafd9",
                "createdAt": "2020-01-14T21:28:04.719Z",
                "status": "CANCELED",
                "accountOwner": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
                "accountNumber": "0",
                "orderType": "LIMIT",
                "fillOrKill": False,
                "postOnly": False,
                "market": "WETH-USDC",
                "side": "BUY",
                "baseAmount": "20000000000000000000",
                "quoteAmount": "100000",
                "filledAmount": "0",
                "price": "0.000000000000005",
                "cancelReason": "USER_CANCELED",
                "updatedAt": "2020-01-14T21:28:19.191Z"
            }
        }
    }

    CANCEL_ORDER_SELL = {
        "type": "channel_data",
        "connection_id": "8c510abb-2e45-4f9a-be17-9c992b441da8",
        "message_id": 7,
        "channel": "orders",
        "id": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
        "contents": {
            "type": "ORDER",
            "order": {
                "uuid": "d98b3b81-8ffa-45c8-8e1a-38a31ab9f690",
                "id": "0x03dfd18edc2f26fc9298edcd28ca6\
                  cad4971bd1f44d40253d5154b0d1f217680",
                "createdAt": "2020-01-14T21:28:04.719Z",
                "status": "CANCELED",
                "accountOwner": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
                "accountNumber": "0",
                "orderType": "LIMIT",
                "fillOrKill": False,
                "postOnly": False,
                "market": "WETH-USDC",
                "side": "BUY",
                "baseAmount": "20000000000000000000",
                "quoteAmount": "100000",
                "filledAmount": "0",
                "price": "0.000000000000005",
                "cancelReason": "USER_CANCELED",
                "updatedAt": "2020-01-14T21:28:19.191Z"
            }
        }
    }

    WS_AFTER_CANCEL_BUY = {
        "type": "channel_data",
        "connection_id": "8c510abb-2e45-4f9a-be17-9c992b441da8",
        "message_id": 7,
        "channel": "orders",
        "id": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
        "contents": {
            "type": "ORDER",
            "order": {
                "uuid": "d98b3b81-8ffa-45c8-8e1a-38a31ab9f690",
                "id": "0xb0751a113c759779ff5fd6a53b37b262\
                  11a9f8845d443323b9f877f32d9aafd9",
                "createdAt": "2020-01-14T21:28:04.719Z",
                "status": "CANCELED",
                "accountOwner": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
                "accountNumber": "0",
                "orderType": "LIMIT",
                "fillOrKill": False,
                "postOnly": False,
                "market": "WETH-USDC",
                "side": "BUY",
                "baseAmount": "20000000000000000000",
                "quoteAmount": "100000",
                "filledAmount": "0",
                "price": "0.000000000000005",
                "cancelReason": "USER_CANCELED",
                "updatedAt": "2020-01-14T21:28:19.191Z"
            }
        }
    }

    LIMIT_MAKER_BUY_ERROR = {
        "type": "channel_data",
        "connection_id": "8c510abb-2e45-4f9a-be17-9c992b441da8",
        "message_id": 7,
        "channel": "orders",
        "id": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
        "contents": {
            "type": "ORDER",
            "order": {
                "uuid": "d98b3b81-8ffa-45c8-8e1a-38a31ab9f690",
                "id": "0xb0751a113c759779ff5fd6a53b37b\
                  26211a9f8845d443323b9f877f32d9aafd9",
                "createdAt": "2020-01-14T21:28:04.719Z",
                "status": "CANCELED",
                "accountOwner": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
                "accountNumber": "0",
                "orderType": "LIMIT",
                "fillOrKill": False,
                "postOnly": True,
                "market": "WETH-USDC",
                "side": "BUY",
                "baseAmount": "40000000000000000000",
                "quoteAmount": "100000",
                "filledAmount": "0",
                "price": "0.000000000000005",
                "cancelReason": "POST_ONLY_WOULD_CROSS",
                "updatedAt": "2020-01-14T21:28:19.191Z"
            }
        }
    }

    LIMIT_MAKER_SELL_ERROR = {
        "type": "channel_data",
        "connection_id": "8c510abb-2e45-4f9a-be17-9c992b441da8",
        "message_id": 7,
        "channel": "orders",
        "id": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
        "contents": {
            "type": "ORDER",
            "order": {
                "uuid": "d98b3b81-8ffa-45c8-8e1a-38a31ab9f690",
                "id": "0x03dfd18edc2f26fc9298edcd28ca6cad4\
                  971bd1f44d40253d5154b0d1f217680",
                "createdAt": "2020-01-14T21:28:04.719Z",
                "status": "CANCELED",
                "accountOwner": "0x014be43bf2d72a7a151a761a1bd5224f7ad4973c",
                "accountNumber": "0",
                "orderType": "LIMIT",
                "fillOrKill": False,
                "postOnly": True,
                "market": "WETH-USDC",
                "side": "SELL",
                "baseAmount": "40000000000000000000",
                "quoteAmount": "100000",
                "filledAmount": "0",
                "price": "0.000000000000005",
                "cancelReason": "POST_ONLY_WOULD_CROSS",
                "updatedAt": "2020-01-14T21:28:19.191Z"
            }
        }
    }

    WETHUSDC_SNAP = {
        "bids": [
            {
                "id": "0xefa4562c0747a8f2a9aa69abb81747\
                  4ee9e98c8505a71de6054a610ac744b0cd",
                "uuid": "c58be890-6e76-4e98-95d4-27977a91af19",
                "amount": "17459277053478281216",
                "price": "160.06010000000002787211"
            },
            {
                "id": "0xa2ab9f653106fefef5b1264a509b02e\
                  ab021ffea442307e995908e5360f3cd4d",
                "uuid": "d2dba4c6-6442-46bc-b097-1f37312cf279",
                "amount": "149610989871929360384",
                "price": "160.06010000000000157722"
            },
            {
                "id": "0xec35d60dd1c5eab86cd7881fcbc12391\
                  93ceda695df2815d521a46f54bd90580",
                "uuid": "24d5a4e1-195b-43fa-a7d8-1d794619e97e",
                "amount": "54494000000000000000",
                "price": "160.05999999999998977766"
            },
        ],
        "asks": [
            {
                "id": "0xb242e2006a0d99c390fc7256d10558844\
                  a719d580e80eaa5a4f99dd14bd9ce5e",
                "uuid": "6fdff2f3-0175-4297-bf23-89526eb9aa36",
                "amount": "12074182754430260637",
                "price": "160.30000000000000000000"
            },
            {
                "id": "0xe32a00e11b91b6f8daa70fbe03ad0100fa\
                  458c0d87e5c59f2e629ce9d5d32921",
                "uuid": "3f9b35a8-d843-4ae6-bc8b-b534b07e8093",
                "amount": "50000000000000000000",
                "price": "160.40000000000000000000"
            },
            {
                "id": "0xcad0c2e92094bd1dd17a694bd25933a8825\
                  c6014aaf4ae2925512f62c15ae968",
                "uuid": "5aefdfd2-4e4d-4b37-9c99-35e8eec0ed9a",
                "amount": "50000000000000000000",
                "price": "160.50000000000000000000"
            },
        ]
    }
