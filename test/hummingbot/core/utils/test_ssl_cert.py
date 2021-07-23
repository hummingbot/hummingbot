"""
Unit tests for hummingbot.core.utils.ssl_cert
"""

from hummingbot import set_cert_path
from hummingbot.core.utils.ssl_cert import generate_private_key, generate_public_key, generate_csr, sign_csr, create_self_sign_certs, certs_files_exist
import os
import tempfile
import unittest


class SslCertTest(unittest.TestCase):
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

    def test_create_self_sign_certs(self):
        """
        Unit tests for create_self_sign_certs and certs_files_exist
        """

        # setup global cert_path and make sure it is empty
        with tempfile.TemporaryDirectory() as tempdir:
            cp = tempdir + "/certs"
            set_cert_path(cp)
            if not os.path.exists(cp):
                os.mkdir(cp)

            self.assertEqual(certs_files_exist(), False)

            # generate all necessary certs then confirm they exist in the expected place
            create_self_sign_certs("abc123")
            self.assertEqual(certs_files_exist(), True)
