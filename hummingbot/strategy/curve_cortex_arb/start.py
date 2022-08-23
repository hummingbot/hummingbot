from hummingbot.client.config.config_helpers import load_client_config_map_from_file
from hummingbot.strategy.curve_cortex_arb import CurveCortexArb


def start(self):
    self.client_config_map = load_client_config_map_from_file()
    self.strategy = CurveCortexArb(client_config_map = self.client_config_map)
