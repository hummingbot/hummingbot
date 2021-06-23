# -*- coding: utf-8 -*-

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange


CENTRALIZED = True

EXAMPLE_PAIR = 'BTC-USDC'

DEFAULT_FEES = [0.15, 0.25]

KEYS = {
    'beaxy_api_key':
        ConfigVar(key='beaxy_api_key',
                  prompt='Enter your Beaxy API key >>> ',
                  required_if=using_exchange('beaxy'),
                  is_secure=True,
                  is_connect_key=True),
    'beaxy_secret_key':
        ConfigVar(key='beaxy_secret_key',
                  prompt='Enter your Beaxy secret key >>> ',
                  required_if=using_exchange('beaxy'),
                  is_secure=True,
                  is_connect_key=True),
}
