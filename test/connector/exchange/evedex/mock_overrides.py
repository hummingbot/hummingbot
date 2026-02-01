
# Aggressive Mocking of Top-Level Packages
import sys
from unittest.mock import MagicMock

# Mock pandas
sys.modules["pandas"] = MagicMock()
sys.modules["pandas.DataFrame"] = MagicMock()

# Mock hummingbot logger to avoid pandas dependency
sys.modules["hummingbot.logger"] = MagicMock()
sys.modules["hummingbot.logger.struct_logger"] = MagicMock()
sys.modules["hummingbot.logger.logger"] = MagicMock()
