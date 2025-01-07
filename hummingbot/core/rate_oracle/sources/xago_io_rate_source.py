import copy
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional

from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache

if TYPE_CHECKING:
    from hummingbot.connector.exchange.xago_io.xago_io_exchange import XagoIoExchange


class XagoIoRateSource(RateSourceBase):
    def __init__(self):
        super().__init__()
        self._exchange: Optional[XagoIoExchange] = None  # delayed because of circular reference

    @property
    def name(self) -> str:
        return "xago_io"

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        self._ensure_exchange()
        results = {}
        try:
            records = await self._exchange.get_all_pairs_prices()
            # Add BUSD to records
            records["buyUSDT"] = records["buyUSD"]
            records["buyUSDC"] = records["buyUSD"]

            for _key, value in records.items():
                if not isinstance(value, list):
                    continue
                usd_list = [d for d in value if d.get('currency') == 'USD']
                if len(usd_list) == 0:
                    continue
                if len(usd_list) == 2:
                    usd_list.pop(1)

                usdt_dict = copy.deepcopy(usd_list[0])
                usdt_dict['currency'] = 'USDT'
                value.append(usdt_dict)

                usdc_dict = copy.deepcopy(usd_list[0])
                usdc_dict['currency'] = 'USDC'
                value.append(usdc_dict)

            for base_token in records:
                try:
                    if "buy" not in base_token:
                        continue
                    base_token_formatted = base_token.split("buy")[1]
                    for record in records[base_token]:
                        if record['currency'] == quote_token:
                            pair = f"{base_token_formatted}-{quote_token}"
                            price_value = record['price'] if record.get('price') is not None else '1'
                            results[pair] = Decimal(price_value)
                except KeyError as e:
                    # Ignore results for which their symbols is not tracked by the connector
                    self.logger().exception(
                        msg=f"Unexpected error while retrieving rates from Xago_io. Key error. {e}",
                    )
                    continue
        except Exception as e:
            self.logger().exception(
                msg=f"Unexpected error while retrieving rates from Xago_io. Check the log file for more info. {e}",
            )
        return results

    def _ensure_exchange(self):
        if self._exchange is None:
            self._exchange = self._build_xago_io_connector_without_private_keys()

    @staticmethod
    def _build_xago_io_connector_without_private_keys() -> 'XagoIoExchange':
        from hummingbot.client.hummingbot_application import HummingbotApplication
        from hummingbot.connector.exchange.xago_io.xago_io_exchange import XagoIoExchange

        app = HummingbotApplication.main_application()
        client_config_map = app.client_config_map

        return XagoIoExchange(
            client_config_map=client_config_map,
            xago_io_api_key="",
            xago_io_secret_key="",
            trading_pairs=[],
            trading_required=False,
        )
