"""

Run with:

```
$ cd ~/src/hummingbot-pysui
$ conda activate hummingbot
$ py.test test/hummingbot/connector/exchange/suidex/libsui/test_libsui.py

(hummingbot) 20240530-10:21.46 martin@cdcx4 hummingbot-pysui ▶ $ cd ~/src/hummingbot-pysui && py.test test/hummingbot/connector/exchange/suidex/libsui/test_libsui.py
============================================================================================================ test session starts =============================================================================================================
platform linux -- Python 3.10.14, pytest-8.2.1, pluggy-1.5.0
rootdir: /home/martin/src/hummingbot-pysui
configfile: pyproject.toml
plugins: anyio-4.4.0, web3-6.19.0
collected 2 items

test/hummingbot/connector/exchange/suidex/libsui/test_libsui.py ..                                                                                                                                                                     [100%]

============================================================================================================= 2 passed in 0.04s ==============================================================================================================
(hummingbot) 20240530-10:21.56 martin@cdcx4 hummingbot-pysui ▶ $

```

"""


import unittest


class DexTestCase(unittest.TestCase):
    @classmethod
    def setUpPairs(cls, base_asset: str, quote_asset: str) -> None:
        cls.base_asset = base_asset
        cls.quote_asset = quote_asset
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.hb_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"
        return base_asset, quote_asset



class LibSuiTestCases(DexTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        base_asset = "BTC_FIXME"
        quote_asset = "USD_FIXME"
        return cls.setUpPairs(base_asset, quote_asset)


    def test_is_test_runner_working(self):
        self.assertTrue(True)
        self.assertFalse(False)
        return True

    def test_more_tests_here(self):
        return "change me"
