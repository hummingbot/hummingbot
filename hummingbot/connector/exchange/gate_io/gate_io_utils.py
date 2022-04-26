import hummingbot.connector.exchange.gate_io.gate_io_constants as CONSTANTS
from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"
DEFAULT_FEES = [0.2, 0.2]

KEYS = {
    "gate_io_api_key":
        ConfigVar(key="gate_io_api_key",
                  prompt=f"Enter your {CONSTANTS.EXCHANGE_NAME} API key >>> ",
                  required_if=using_exchange("gate_io"),
                  is_secure=True,
                  is_connect_key=True),
    "gate_io_secret_key":
        ConfigVar(key="gate_io_secret_key",
                  prompt=f"Enter your {CONSTANTS.EXCHANGE_NAME} secret key >>> ",
                  required_if=using_exchange("gate_io"),
                  is_secure=True,
                  is_connect_key=True),
}
