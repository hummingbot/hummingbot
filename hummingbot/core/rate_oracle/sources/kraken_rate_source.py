from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather

if TYPE_CHECKING:
    from hummingbot.connector.exchange.kraken.kraken_exchange import KrakenExchange


class KrakenRateSource(RateSourceBase):
    def __init__(self):
        super().__init__()
        self._exchange: Optional[KrakenExchange] = None  # delayed because of circular reference

    @property
    def name(self) -> str:
        return "kraken"

    @async_ttl_cache(ttl=10, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        self._ensure_exchanges()
        results = {}
        pairs_sub = {}
        tickers_sub = {}
        quote_token_length = len(quote_token)
        try:
            pairs = await self._exchange.get_asset_pairs()
            tickers = await self._exchange.get_all_tickers()
            # remove non USD from pairs and populate pairs_sub with ticker name
            for pair in pairs:
                if (pairs[pair]["status"] != "online"):
                    continue
               
                if quote_token == pairs[pair]['altname'][-quote_token_length:]:
                    pairs_sub[pairs[pair]['altname']] = pairs[pair]
                    pairs_sub[pairs[pair]['altname']]['ticker_name'] = pairs[pair]['base'] + pairs[pair]['quote']
            
            # remove non usd from tickers and add ticker info to matching pairs_sub
            for pair in pairs_sub:
                for ticker in tickers:
                        if quote_token != ticker[-quote_token_length:]:
                            continue
                        tickers_sub[ticker] = tickers[ticker]
                       
                        if (ticker == pairs_sub[pair]['ticker_name'] or ticker == pair):
                            if (ticker == 'XXRPUSDT'):
                                print ("Test")
                            pairs_sub[pair]['ticker'] = tickers[ticker]

            for trading_pair in pairs_sub:
                if ("ticker" not in pairs_sub[trading_pair]):
                    continue
                ask_price = pairs_sub[trading_pair]['ticker']["a"][0]
                bid_price = pairs_sub[trading_pair]['ticker']["b"][0]
                if bid_price is not None and ask_price is not None and 0 < Decimal(bid_price) <= Decimal(ask_price):
                    pair_hyphon =  pairs_sub[trading_pair]['wsname'].replace("/", "-")
                    if pair_hyphon.split('-')[0] in ['USD', 'EUR', 'GBP']:
                        pair_bequant = pair_hyphon.split('-')[0] + 'B' + '-' + pair_hyphon.split('-')[1]
                        results[pair_bequant] = (Decimal(bid_price) + Decimal(ask_price)) / Decimal("2")    
                    results[pair_hyphon] = (Decimal(bid_price) + Decimal(ask_price)) / Decimal("2")
               
               
        except Exception as e:
                self.logger().exception(
                msg="Unexpected error while retrieving rates from Kraken. Check the log file for more info.")
        
        return results
        

    def _ensure_exchanges(self):
        if self._exchange is None:
            self._exchange = self._build_kraken_connector_without_private_keys()
         

    @staticmethod
    def _build_kraken_connector_without_private_keys() -> 'KrakenExchange':
        from hummingbot.client.hummingbot_application import HummingbotApplication
        from hummingbot.connector.exchange.kraken.kraken_exchange import KrakenExchange

        app = HummingbotApplication.main_application()
        client_config_map = app.client_config_map
        
        return KrakenExchange(
            client_config_map=client_config_map,
            kraken_api_key="",
            kraken_secret_key="",
            trading_pairs=[],
            trading_required=False,
        )
    
