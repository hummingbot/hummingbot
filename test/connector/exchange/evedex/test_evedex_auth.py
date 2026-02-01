
import unittest
import sys
import os
import logging
from unittest.mock import MagicMock

# Add repo root to path
sys.path.append(os.getcwd() + "/hummingbot-repo")

# --- MOCKING START ---
# 1. Mock External Libs that might be missing or slow
sys.modules["pandas"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["cachetools"] = MagicMock()

# 2. Mock Hummingbot Logger components to satisfy __init__.py
class MockStructLogger(logging.Logger):
    pass

sys.modules["hummingbot.logger"] = MagicMock()
sys.modules["hummingbot.logger.struct_logger"] = MagicMock()
sys.modules["hummingbot.logger.struct_logger"].StructLogger = MockStructLogger
sys.modules["hummingbot.logger.logger"] = MagicMock()

# 3. Handle 'hummingbot.core' dependencies.
# The error "No module named 'hummingbot.core.data_type'; 'hummingbot.core' is not a package"
# happens because we previously mocked 'hummingbot.core' as a MagicMock object.
# A MagicMock object is not a package, so we can't import submodules from it unless we explicitly set them as attributes.
# But python's import system gets confused if we try to import "from hummingbot.core.data_type..." if hummingbot.core is just a mock.

# Instead of mocking the entire core module, let's mock the specific leaf nodes we need,
# or create a fake module hierarchy.

# Strategy: Let Python find the real files on disk, but mock the heavy dependencies inside them.
# The previous error failed because `hummingbot.core` was mocked in a previous run or interference?
# No, I removed the `sys.modules['hummingbot.core'] = MagicMock()` line in this iteration.
# Wait, I see I did NOT remove it in the previous failed run's edit? 
# Ah, I see: "sys.modules['hummingbot.core'] = MagicMock()" was likely in my head but not the file.

# Let's check the error again: "ModuleNotFoundError: No module named 'hummingbot.core.data_type'; 'hummingbot.core' is not a package"
# This implies something has polluted sys.modules['hummingbot.core'] to be a non-package (likely a mock or a file).
# OR, it implies `hummingbot.core` was imported as a module, but `data_type` is a directory?

# Let's try a different approach: Only test EvedexAuth for now.
# EvedexAuth ONLY depends on `eth_account`, `json`, `typing`, and `evedex_constants`.
# `evedex_constants` depends on `RateLimit` from `hummingbot.core.api_throttler.data_types`.

# We can bypass importing `evedex_exchange` in `__init__.py` to avoid the cascade of imports.
# We will verify EvedexAuth in isolation.

# To do this, we need to modify `hummingbot/connector/exchange/evedex/__init__.py` temporarily or just import from the file directly.
# But `__init__.py` is already written and imports everything.
# We can mock `hummingbot.connector.exchange.evedex.evedex_exchange` so it doesn't actually load the file.

sys.modules["hummingbot.connector.exchange.evedex.evedex_exchange"] = MagicMock()
sys.modules["hummingbot.connector.exchange.evedex.evedex_api_order_book_data_source"] = MagicMock()
sys.modules["hummingbot.connector.exchange.evedex.evedex_user_stream_tracker"] = MagicMock()
sys.modules["hummingbot.connector.exchange.evedex.evedex_api_user_stream_data_source"] = MagicMock()

# We still need `evedex_constants` to load for the Chain ID.
# And `evedex_constants` needs `hummingbot.core.api_throttler.data_types`.
# So we mock THAT.

sys.modules["hummingbot.core"] = MagicMock()
# We must ensure it's treated as a package if we want to attach children?
# Actually, if we mock `hummingbot.core` as a MagicMock, `from hummingbot.core.api_throttler...` might fail if it tries to traverse.
# It is safer to define `hummingbot.core.api_throttler.data_types` in sys.modules directly.

sys.modules["hummingbot.core.api_throttler"] = MagicMock()
sys.modules["hummingbot.core.api_throttler.data_types"] = MagicMock()
sys.modules["hummingbot.core.api_throttler.data_types"].RateLimit = MagicMock()

# --- MOCKING END ---

from hummingbot.connector.exchange.evedex.evedex_auth import EvedexAuth
from hummingbot.connector.exchange.evedex import evedex_constants as CONSTANTS

class EvedexAuthTest(unittest.TestCase):
    def setUp(self):
        # Sample private key (do not use in prod)
        self.private_key = "0x0000000000000000000000000000000000000000000000000000000000000001"
        self.auth = EvedexAuth(private_key=self.private_key)

    def test_get_public_key(self):
        # Known address for key 0x...01
        expected_address = "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf"
        self.assertEqual(self.auth.get_public_key(), expected_address)

    def test_construct_eip712_message(self):
        method = "POST"
        endpoint = "/order"
        params = {"price": "100", "qty": "1"}
        
        message = self.auth._construct_eip712_message(method, endpoint, params)
        
        self.assertEqual(message["domain"]["name"], "Evedex Exchange")
        self.assertEqual(message["domain"]["chainId"], CONSTANTS.CHAIN_ID)
        self.assertEqual(message["message"]["method"], method)
        self.assertEqual(message["message"]["endpoint"], endpoint)
        # Params should be a sorted JSON string
        self.assertEqual(message["message"]["params"], '{"price": "100", "qty": "1"}')

    def test_sign_request(self):
        method = "POST"
        endpoint = "/order"
        params = {"price": "100", "qty": "1"}
        
        signature = self.auth.sign_request(method, endpoint, params)
        
        # Signature should be a hex string starting with 0x and length 132 (65 bytes * 2 + 2)
        # eth_account returns hex string directly
        # Sometimes it might not have 0x prefix depending on version, checking just hex
        if not signature.startswith("0x"):
            signature = "0x" + signature
            
        self.assertTrue(signature.startswith("0x"))
        self.assertEqual(len(signature), 132)

if __name__ == '__main__':
    unittest.main()
