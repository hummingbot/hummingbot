from hummingbot.client.config.config_var import ConfigVar


# Returns a market prompt that incorporates the connector value set by the user
def market_prompt() -> str:
    connector = curve_cortex_arb_config_map.get("connector").value
    return f'Enter the token trading pair on {connector} >>> '


# List of parameters defined by the strategy
curve_cortex_arb_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="curve_cortex_arb"),
    "curve_connector":
        ConfigVar(key="curve_connector",
                  prompt="",
                  default="curve"),
    "cortex_connector":
        ConfigVar(key="cortex_connector",
                  prompt="",
                  default="cortex"),
}
