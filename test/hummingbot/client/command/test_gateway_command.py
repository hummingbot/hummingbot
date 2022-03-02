import unittest
from hummingbot.client.command.gateway_command import GatewayCommand
from hummingbot.core.utils.ssl_cert import certs_files_exist


class GatewayCommandUnitTest(unittest.TestCase):
    def test_certificate_creation(self):
        GatewayCommand.gateway("generate_certs")
        self.assertTrue(certs_files_exist)
