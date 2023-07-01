import unittest

from hummingbot.client.platform import get_installation_type, get_system


class TestSystemInstallationTestCase(unittest.TestCase):

    def test_get_system(self):
        system = get_system()
        self.assertIn(system, ["Windows", "Linux", "Darwin"])

    def test_get_installation_type(self):
        installation_type = get_installation_type()
        self.assertIn(installation_type, ["docker", "binary", "source"])


if __name__ == '__main__':
    unittest.main()
