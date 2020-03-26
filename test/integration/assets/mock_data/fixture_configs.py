class FixtureConfigs:
    in_mem_new_pass_configs = [
        {"prompt": "Enter your new password >>> ", "input": "a"},
        {"prompt": "Please reenter your password >>> ", "input": "a"},
        {"prompt": "What is your market making strategy? >>> ", "input": "pure_market_making"},
        {"prompt": "Import previous configs or create a new config file? (import/create) >>> ", "input": "create"}
    ]

    pure_mm_basic_responses = {
        "maker_market": "binance",
        "maker_market_trading_pair": "LINK-ETH",
        "bid_place_threshold": "0.01",
        "ask_place_threshold": "0.01",
        "cancel_order_wait_time": "",
        "order_amount": "4",
        "advanced_mode": "Hell No!"
    }

    global_binance_config = {
        "binance_api_key": "",
        "binance_api_secret": "",
        "kill_switch_enabled": "no",
        "send_error_logs": "no"
    }

    in_mem_existing_pass_import_configs = [
        {"prompt": "What is your market making strategy? >>> ", "input": "pure_market_making"},
        {"prompt": "Import previous configs or create a new config file? (import/create) >>> ", "input": "import"}
    ]

    in_mem_existing_pass_create_configs = [
        {"prompt": "What is your market making strategy? >>> ", "input": "pure_market_making"},
        {"prompt": "Import previous configs or create a new config file? (import/create) >>> ", "input": "create"}
    ]
