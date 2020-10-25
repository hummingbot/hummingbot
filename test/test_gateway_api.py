#!/usr/bin/env python
from os.path import (
    join,
    realpath,
)
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

import unittest
from hummingbot.client import settings
# from hummingbot.client.config.global_config_map import global_config_map
import ruamel.yaml
import requests


yaml_parser = ruamel.yaml.YAML()


class GatewayAPIUnitTest(unittest.TestCase):

    API_CALL_TIMEOUT = 10.0
    GATEWAY_HOST = 'https://localhost'
    GATEWAY_PORT = '5000'  # global_config_map.get("gateway_api_port").value
    API_HOST = ':'.join([GATEWAY_HOST, GATEWAY_PORT])

    # for name, config in global_config_map.items():
    #     print(name, config)
    gateway_config_path: str = realpath(join(__file__, join("../../", settings.GATEWAY_CONFIG_PATH)))
    TEMPLATE_DATA = None

    def setUp(self):
        pass
        # with open(self.gateway_config_path, "r") as template_fd:
        #     self.TEMPLATE_DATA = yaml_parser.load(template_fd)
        #     template_version = self.TEMPLATE_DATA.get("template_version", 0)
        #     self.assertGreaterEqual(template_version, 1)
        #     for key in self.TEMPLATE_DATA:
        #         if key == "gateway_api_port":
        #             self.GATEWAY_PORT = str(self.TEMPLATE_DATA['gateway_api_port'])
        #         if key == "template_version":
        #             continue
        #         self.assertTrue(key in gateway_config_map, f"{key} not in global_config_map")

    def tearDown(self):
        pass

    def test_get_no_cert_verification(self):
        url = self.API_HOST + '/api'
        response = requests.get(url, verify=False)
        result = response.json()
        print(result.keys(), result['error'], 'error' in result.keys())
        self.assertTrue('error' in result.keys(), f"{result['error']}")

    def test_get_api_status(self):
        url = self.API_HOST + '/api'

        certServer = realpath(join(__file__, join("../../certs/server_cert.pem")))
        cacerts = (realpath(join(__file__, join("../../certs/client_cert.pem"))),
                   realpath(join(__file__, join("../../certs/client_key.pem"))))
        response = requests.get(url, verify=certServer, cert=cacerts)

        result = response.json()
        print('result', result)
        self.assertTrue('status' in result.keys() and result['status'] == 'ok', f"Gateway API {url} not ready")
