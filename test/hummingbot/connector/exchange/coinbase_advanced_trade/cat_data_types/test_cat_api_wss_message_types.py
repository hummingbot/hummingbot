import unittest

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_wss_message_types import (
    CoinbaseAdvancedTradeEventMessage,
)

# from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities
# .cat_api_wss_class_validation_with_web_documentation import \ ClassWSSValidationWithWebDocumentation,
# get_websocket_documentation
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_class_validation_from_json_docstring import (
    ClassValidationFromJsonDocstring,
)

# from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_wss_message_types import *


# class WSSWebDocumentation:
#    base_url = "https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-channels"
#    class_under_test = None
#
#    @classmethod
#    def setUpClass(cls) -> None:
#        super().setUpClass()
#        cls.web_params: Dict[str, Any] = asyncio.run(get_websocket_documentation(cls.base_url))
#
#    def test_level2event_documentation(self):
#        self.class_under_test = CoinbaseAdvancedTradeLevel2EventMessage
#        docstring = inspect.getdoc(self.class_under_test)
#        doc_url = re.search(r"https?://[^\s]+", docstring).group(0)
#        if doc_url:
#            self.assertTrue(doc_url.startswith(self.base_url), f"Expected {doc_url} to start with {self.base_url}")
#            CoinbaseAdvancedTradeLevel2EventMessage(**self.web_params["level2"]["Response"]["events"][0])
#
#    def test_market_trades_event_documentation(self):
#        self.class_under_test = CoinbaseAdvancedTradeLevel2EventMessage
#        docstring = inspect.getdoc(self.class_under_test)
#        doc_url = re.search(r"https?://[^\s]+", docstring).group(0)
#        if doc_url:
#            self.assertTrue(doc_url.startswith(self.base_url), f"Expected {doc_url} to start with {self.base_url}")
#            CoinbaseAdvancedTradeMarketTradesEventMessage(**self.web_params["market_trades"]["Response"]["events"][0])
#
#    def test_userevent_documentation(self):
#        self.class_under_test = CoinbaseAdvancedTradeLevel2EventMessage
#        docstring = inspect.getdoc(self.class_under_test)
#        doc_url = re.search(r"https?://[^\s]+", docstring).group(0)
#        if doc_url:
#            self.assertTrue(doc_url.startswith(self.base_url), f"Expected {doc_url} to start with {self.base_url}")
#            CoinbaseAdvancedTradeUserEventMessage(**self.web_params["user"]["Response"]["events"][0])
#
#    def test_allevents_documentation(self):
#        for event in self.web_params:
#            response = self.web_params[event].get("Response", None)
#            if response:
#                CoinbaseAdvancedTradeWSSMessage(**response)


# List of classes you want to test
classes_under_test = [CoinbaseAdvancedTradeEventMessage.get_registry()[key] for key in
                      CoinbaseAdvancedTradeEventMessage.get_registry().keys()]

# DEBUG: classes_under_test = [CoinbaseAdvancedTradeLevel2EventMessage]
# Dynamically create a subclass for each class you want to test
for class_under_test in classes_under_test:
    name = f"TestJson{class_under_test.__name__}"
    globals()[name] = type(name, (ClassValidationFromJsonDocstring.TestSuite,), {"class_under_test": class_under_test})

if __name__ == "__main__":
    unittest.main()
