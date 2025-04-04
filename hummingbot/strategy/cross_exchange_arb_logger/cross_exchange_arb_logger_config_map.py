from hummingbot.client.config.config_var import ConfigVar

cross_exchange_arb_logger_config_map = {
    "strategy":
        ConfigVar(
            key="strategy",
            prompt="",
            default="cross_exchange_arb_logger",
        ),
    "exchange_1_market_1":
        ConfigVar(
            key="exchange_1_market_1",
            prompt="Enter the name of the first exchange market pair >>> ",
            prompt_on_new=True,
        ),
    "exchange_2_market_2":
        ConfigVar(
            key="exchange_2_market_2",
            prompt="Enter the name of the second exchange market pair >>> ",
            prompt_on_new=True,
        ),
}
