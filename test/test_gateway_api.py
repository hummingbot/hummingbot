#!/usr/bin/env python
from os.path import (
    join,
    realpath,
)
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

import unittest
from hummingbot.client import settings
from hummingbot.client.config.gateway_config_map import gateway_config_map
import ruamel.yaml
import requests


yaml_parser = ruamel.yaml.YAML()


class GatewayAPIUnitTest(unittest.TestCase):

    API_CALL_TIMEOUT = 10.0
    GATEWAY_URL = 'https://localhost'
    GATEWAY_PORT = None
    gateway_config_path: str = realpath(join(__file__, join("../../", settings.GATEWAY_CONFIG_PATH)))
    TEMPLATE_DATA = None

    def setUp(self):
        with open(self.gateway_config_path, "r") as template_fd:
            self.TEMPLATE_DATA = yaml_parser.load(template_fd)
            template_version = self.TEMPLATE_DATA.get("template_version", 0)
            self.assertGreaterEqual(template_version, 1)
            for key in self.TEMPLATE_DATA:
                if key == "gateway_api_port":
                    self.GATEWAY_PORT = str(self.TEMPLATE_DATA['gateway_api_port'])
                if key == "template_version":
                    continue
                self.assertTrue(key in gateway_config_map, f"{key} not in gateway_config_map")

    def tearDown(self):
        pass

    def test_get_api_status(self):
        url = ':'.join([self.GATEWAY_URL, self.GATEWAY_PORT]) + '/api/status'
        # cert = realpath(join(__file__, join("../../certs/server-public-key.pem")))
        # response = requests.get(url, verify=cert)

        cacerts = (realpath(join(__file__, join("../../certs/server-public-key.pem"))),
                   realpath(join(__file__, join("../../certs/server-private-key.pem"))))
        response = requests.get(url, cert=cacerts)

        result = response.json()
        self.assertTrue('status' in result.keys() and result['status'] == 'ok', f"Gateway API {url} not ready")
