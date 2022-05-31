"""
Unit tests for hummingbot.core.utils.ssl_cert
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.core.gateway import GatewayPaths
from hummingbot.core.utils.ssl_cert import (
    certs_files_exist,
    create_self_sign_certs,
    generate_csr,
    generate_private_key,
    generate_public_key,
    sign_csr,
)


class SslCertTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

    def test_generate_private_key(self):
        """
        Unit tests for generate_private_key
        """
        # Assert that it generates a file
        temp_dir = tempfile.gettempdir()
        private_key_file_path = temp_dir + "/private_key_test"
        generate_private_key("topsecret", private_key_file_path)
        self.assertEqual(os.path.exists(private_key_file_path), True)

    def test_generate_public_key(self):
        """
        Unit tests for generate_public_key
        """

        # create a private key
        temp_dir = tempfile.gettempdir()
        private_key_file_path = temp_dir + "/private_key_test"
        private_key = generate_private_key("topsecret", private_key_file_path)

        # create the public key, assert that the file exists
        public_key_file_path = temp_dir + "/public_key_test"
        generate_public_key(private_key, public_key_file_path)
        self.assertEqual(os.path.exists(public_key_file_path), True)

    def test_generate_csr(self):
        """
        Unit tests for generate_csr
        """

        # create a private key
        temp_dir = tempfile.gettempdir()
        private_key_file_path = temp_dir + "/private_key_test"
        private_key = generate_private_key("topsecret", private_key_file_path)

        # create a csr and assert that it exists
        csr_file_path = temp_dir + "/csr_test"
        generate_csr(private_key, csr_file_path)
        self.assertEqual(os.path.exists(csr_file_path), True)

    def test_sign_csr(self):
        """
        Unit tests for sign_csr
        """

        # create a private key
        temp_dir = tempfile.gettempdir()
        private_key_file_path = temp_dir + "/private_key_test"
        private_key = generate_private_key("topsecret", private_key_file_path)

        # create a public key
        public_key_file_path = temp_dir + "/public_key_test"
        public_key = generate_public_key(private_key, public_key_file_path)

        # create a csr
        csr_file_path = temp_dir + "/csr_test"
        csr = generate_csr(private_key, csr_file_path)

        # create a verified public key
        verified_public_key_file_path = temp_dir + "/verified_public_key"
        sign_csr(csr, public_key, private_key, verified_public_key_file_path)
        self.assertEqual(os.path.exists(verified_public_key_file_path), True)

        # try to create a verified public key with the wrong private key
        # x509 does not stop you from doing this and will still output a file
        # so we just do a simple check that the outputs are not the same
        private_key_file_path2 = temp_dir + "/private_key_test2"
        private_key2 = generate_private_key("topsecret2", private_key_file_path2)
        verified_public_key_file_path2 = temp_dir + "/verified_public_key2"
        sign_csr(csr, public_key, private_key2, verified_public_key_file_path2)

        with open(verified_public_key_file_path, "rb") as verified_public_key:
            with open(verified_public_key_file_path2, "rb") as verified_public_key2:
                self.assertNotEqual(verified_public_key, verified_public_key2)

    @patch("hummingbot.core.gateway.get_gateway_container_name", return_value="test_container_abc")
    def test_create_self_sign_certs(self, _):
        """
        Unit tests for create_self_sign_certs and certs_files_exist
        """

        # setup global cert_path and make sure it is empty
        with tempfile.TemporaryDirectory() as tempdir:
            temppath: Path = Path(tempdir)
            mock_gateway_paths: GatewayPaths = GatewayPaths(
                local_conf_path=temppath.joinpath("conf"),
                local_certs_path=temppath.joinpath("certs"),
                local_logs_path=temppath.joinpath("logs"),
                mount_conf_path=temppath.joinpath("conf"),
                mount_certs_path=temppath.joinpath("certs"),
                mount_logs_path=temppath.joinpath("logs"),
            )

            with patch("hummingbot.core.utils.ssl_cert.get_gateway_paths", return_value=mock_gateway_paths):
                self.assertEqual(certs_files_exist(client_config_map=self.client_config_map), False)

                # generate all necessary certs then confirm they exist in the expected place
                create_self_sign_certs("abc123", client_config_map=self.client_config_map)
                self.assertEqual(certs_files_exist(client_config_map=self.client_config_map), True)
