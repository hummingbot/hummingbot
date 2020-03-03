class FixtureCoinbasePro:
    ACCOUNTS_GET = [{"id": "2d36cb78-5145-41fe-90b0-3f204f2e357d", "currency": "USDC", "balance": "90.1480261500000000",
                     "available": "90.14802615", "hold": "0.0000000000000000",
                     "profile_id": "bc2f3a64-0c0b-49ce-bb3e-5efc978b5b5c", "trading_enabled": True},
                    {"id": "d3356a99-ad27-4b1b-92f8-26233be0d62a", "currency": "ETH", "balance": "0.4424257124965000",
                     "available": "0.4424257124965", "hold": "0.0000000000000000",
                     "profile_id": "bc2f3a64-0c0b-49ce-bb3e-5efc978b5b5c", "trading_enabled": True}]

    FEES_GET = {"maker_fee_rate": "0.0050", "taker_fee_rate": "0.0050", "usd_volume": "462.93"}

    ORDERS_STATUS = []

    ORDERS_LIMIT = {"id": "4aa4773e-ca4e-4146-8ac1-a0ec8c39f835", "price": "278.05000000", "size": "0.02000000",
                    "product_id": "ETH-USDC", "side": "buy", "stp": "dc", "type": "limit", "time_in_force": "GTC",
                    "post_only": False, "created_at": "2020-02-14T06:52:32.167853Z", "fill_fees": "0",
                    "filled_size": "0", "executed_value": "0", "status": "pending", "settled": False}

    ORDERS_LIMIT_2 = {"id": "9087815a-3d3d-4c2c-b627-78fd83d8644e", "price": "787.44000000", "size": "0.07000000",
                      "product_id": "ETH-USDC", "side": "sell", "stp": "dc", "type": "limit", "time_in_force": "GTC",
                      "post_only": False, "created_at": "2020-02-14T07:57:31.842502Z", "fill_fees": "0",
                      "filled_size": "0", "executed_value": "0", "status": "pending", "settled": False}

    WS_ORDER_FILLED = {"type": "done", "side": "buy", "product_id": "ETH-USDC", "time": "2020-02-14T06:52:32.172333Z",
                       "sequence": 544313348, "profile_id": "bc2f3a64-0c0b-49ce-bb3e-5efc978b5b5c",
                       "user_id": "5dc62091b2d9e604842cad56", "order_id": "4aa4773e-ca4e-4146-8ac1-a0ec8c39f835",
                       "reason": "filled", "price": "278.05", "remaining_size": "0"}

    ORDERS_MARKET = {"id": "dedfcd66-2324-4805-bd31-b8920c3a25b4", "size": "0.02000000", "product_id": "ETH-USDC",
                     "side": "buy", "stp": "dc", "funds": "84.33950263", "type": "market", "post_only": False,
                     "created_at": "2020-02-14T07:21:17.166831Z", "fill_fees": "0", "filled_size": "0",
                     "executed_value": "0", "status": "pending", "settled": False}

    ORDERS_MARKET_2 = {"id": "CBS_MARKET_SELL", "size": "0.02000000", "product_id": "ETH-USDC",
                       "side": "sell", "stp": "dc", "funds": "84.33950263", "type": "market", "post_only": False,
                       "created_at": "2020-02-14T07:21:17.166831Z", "fill_fees": "0", "filled_size": "0",
                       "executed_value": "0", "status": "pending", "settled": False}

    WS_MARKET_FILLED = {"type": "done", "side": "buy", "product_id": "ETH-USDC", "time": "2020-02-14T07:21:17.171949Z",
                        "sequence": 544350029, "profile_id": "bc2f3a64-0c0b-49ce-bb3e-5efc978b5b5c",
                        "user_id": "5dc62091b2d9e604842cad56", "order_id": "dedfcd66-2324-4805-bd31-b8920c3a25b4",
                        "reason": "filled", "remaining_size": "0"}

    WS_ORDER_OPEN = {"type": "open", "side": "buy", "product_id": "ETH-USDC", "time": "2020-02-14T07:41:45.174224Z",
                     "sequence": 544392466, "profile_id": "bc2f3a64-0c0b-49ce-bb3e-5efc978b5b5c",
                     "user_id": "5dc62091b2d9e604842cad56", "price": "235.67",
                     "order_id": "9d8c39b0-094f-4832-9a73-9b2e43b03780", "remaining_size": "0.02"}

    WS_ORDER_CANCELLED = {"type": "done", "side": "buy", "product_id": "ETH-USDC",
                          "time": "2020-02-14T07:41:45.450940Z", "sequence": 544392470,
                          "profile_id": "bc2f3a64-0c0b-49ce-bb3e-5efc978b5b5c", "user_id": "5dc62091b2d9e604842cad56",
                          "order_id": "9d8c39b0-094f-4832-9a73-9b2e43b03780", "reason": "canceled", "price": "235.67",
                          "remaining_size": "0.02"}

    COINBASE_ACCOUNTS_GET = \
        [
            {"id": "8543f030-4a21-58d6-ba63-3446e74a01fe", "name": "ETH Wallet", "balance": "0.00000000",
             "currency": "ETH",
             "type": "wallet", "primary": False, "active": True, "available_on_consumer": True, "hold_balance": "0.00",
             "hold_currency": "PHP"},
            {"id": "414f0c91-8490-5790-bb6e-6007c7686267", "name": "USDC Wallet", "balance": "0.000000",
             "currency": "USDC",
             "type": "wallet", "primary": False, "active": True, "available_on_consumer": True, "hold_balance": "0.00",
             "hold_currency": "PHP"},
        ]

    DEPOSIT_INFO = {"id": "1ce80c77-c500-57ab-b5cf-3d523081d871",
                    "address": "0xC642d20e12C37CA8D684F4c41e492f2Fb8C7fA13",
                    "address_info": {"address": "0xC642d20e12C37CA8D684F4c41e492f2Fb8C7fA13"},
                    "name": "New exchange deposit address", "created_at": "2020-02-17T06:34:29Z",
                    "updated_at": "2020-02-17T06:34:29Z", "network": "ethereum", "uri_scheme": "ethereum",
                    "resource": "address",
                    "resource_path": "/v2/accounts/8543f030-4a21-58d6-ba63-3446e74a01fe/addresses/1ce80c77-c500-57ab-b5cf-3d523081d871",
                    "warnings": [{"title": "Only send Ether (ETH) to this address",
                                  "details": "Sending any other digital asset, including Ethereum Classic (ETC), will result in permanent loss.",
                                  "image_url": "https://dynamic-assets.coinbase.com/7796fb1bd5752a156c77e0b1fa28fb17e93d03b4b8e2dcff58dcaf8f99b2e4a3c3af2cd905d5536761c54ac273d62d91a38ef8e5702fa988c37264e7aba36b3b/asset_icons/3af4b33bde3012fd29dd1366b0ad737660f24acc91750ee30a034a0679256d0b.png"}],
                    "warning_title": "Only send Ether (ETH) to this address",
                    "warning_details": "Sending any other digital asset, including Ethereum Classic (ETC), will result in permanent loss.",
                    "deposit_uri": "ethereum:0xC642d20e12C37CA8D684F4c41e492f2Fb8C7fA13", "callback_url": None,
                    "exchange_deposit_address": True}
