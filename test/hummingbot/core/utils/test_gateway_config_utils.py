from typing import List
from unittest import TestCase
import hummingbot.core.utils.gateway_config_utils as utils


class GatewayConfigUtilsTest(TestCase):

    config_dict = {
        "a": 1,
        "b": {
            "ba": 21,
            "bb": 22,
            "bc": {
                "bca": 231,
                "bcb": 232
            }
        },
        "c": 3
    }

    def test_build_config_dict_display(self):
        lines: List[str] = []
        utils.build_config_dict_display(lines, self.config_dict)
        self.assertEqual(8, len(lines))
        self.assertEqual('a: 1', lines[0])
        self.assertEqual('b:', lines[1])
        self.assertEqual('  ba: 21', lines[2])
        self.assertEqual('  bb: 22', lines[3])
        self.assertEqual('  bc:', lines[4])
        self.assertEqual('    bca: 231', lines[5])
        self.assertEqual('    bcb: 232', lines[6])
        self.assertEqual('c: 3', lines[7])

    def test_build_config_namespace_keys(self):
        keys = []
        utils.build_config_namespace_keys(keys, self.config_dict)
        self.assertEqual(["a", "b", "b.ba", "b.bb", "b.bc", "b.bc.bca", "b.bc.bcb", "c"], keys)

    def test_sear(self):
        result = utils.search_configs(self.config_dict, "a")
        self.assertEqual({"a": 1}, result)
        result = utils.search_configs(self.config_dict, "A")
        self.assertEqual(None, result)
        result = utils.search_configs(self.config_dict, "b")
        self.assertEqual({
            "b": {
                "ba": 21,
                "bb": 22,
                "bc": {
                    "bca": 231,
                    "bcb": 232
                }
            }
        }, result)
        result = utils.search_configs(self.config_dict, "b.bb")
        self.assertEqual({
            "b": {
                "bb": 22
            }
        }, result)
        result = utils.search_configs(self.config_dict, "b.bc")
        self.assertEqual({
            "b": {
                "bc": {
                    "bca": 231,
                    "bcb": 232
                }
            }
        }, result)
        result = utils.search_configs(self.config_dict, "b.bc.bcb")
        self.assertEqual({
            "b": {
                "bc": {
                    "bcb": 232
                }
            }
        }, result)
        result = utils.search_configs(self.config_dict, "b.BC.bCb")
        self.assertEqual(None, result)
        result = utils.search_configs(self.config_dict, "b.BC.bCb")
        self.assertEqual(None, result)
        result = utils.search_configs(self.config_dict, "d")
        self.assertEqual(None, result)
        result = utils.search_configs(self.config_dict, "b.xyz")
        self.assertEqual(None, result)
        result = utils.search_configs(self.config_dict, "b.bb.xyz")
        self.assertEqual(None, result)
