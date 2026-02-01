import sys
from unittest.mock import MagicMock

# Mock hummingbot modules to avoid full installation
sys.modules["hummingbot"] = MagicMock()
sys.modules["hummingbot.connector"] = MagicMock()
sys.modules["hummingbot.connector.exchange"] = MagicMock()
sys.modules["hummingbot.connector.exchange.evedex"] = MagicMock()
# Allow actual import of our target module
del sys.modules["hummingbot.connector.exchange.evedex"]

# Mock constants if needed, though we want to test the real ones
