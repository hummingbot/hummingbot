import unittest
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.command.gateway_command import GatewayCommand
from hummingbot.core.utils.ssl_cert import certs_files_exist


class GatewayCommandUnitTest(unittest.TestCase):

    def test_certificate_creation(self):
        GatewayCommand.gateway("generate_certs")
        self.assertTrue(certs_files_exist)

    def test_attempted_connection_to_gateway(self):
        safe_ensure_future(GatewayCommand().get_gateway_connections())
        GatewayCommand.gateway("list-configs")
