import asyncio
from decimal import Decimal
from typing import List, Optional, Tuple
from unittest.mock import AsyncMock, patch


class XrplClientMock:
    def __init__(
            self, initial_timestamp: float, wallet_address: str, base: str, quote: str,
    ):
        self.initial_timestamp = initial_timestamp
        self.base = base
        self.base_coin_issuer = "rh8LssQyeBdEXk7Zv86HxHrx8k2R2DBUrx"
        self.base_decimals = 15
        self.quote = quote
        self.quote_coin_issuer = "rh8LssQyeBdEXk7Zv86HxHrx8k2R2DBUrx"
        self.quote_decimals = 8
        self.market_id = f'{base}-{quote}'
        self.wallet_address = wallet_address

        self.gateway_instance_mock_patch = patch(
            target=(
                "hummingbot.connector.gateway.clob_spot.data_sources.xrpl.xrpl_api_data_source"
                ".GatewayHttpClient"
            ),
            autospec=True,
        )

        self.gateway_instance_mock: Optional[AsyncMock] = None

        self.place_order_called_event = asyncio.Event()
        self.cancel_order_called_event = asyncio.Event()
        self.update_market_called_event = asyncio.Event()
        self.update_ticker_called_event = asyncio.Event()
        self.update_balances_called_event = asyncio.Event()
        self.orderbook_snapshot_called_event = asyncio.Event()
        self.transaction_status_update_called_event = asyncio.Event()

    def start(self):
        self.gateway_instance_mock = self.gateway_instance_mock_patch.start()
        self.gateway_instance_mock.get_instance.return_value = self.gateway_instance_mock

    def stop(self):
        self.gateway_instance_mock_patch.stop()

    def run_until_place_order_called(self, timeout: float = 1):
        asyncio.get_event_loop().run_until_complete(
            asyncio.wait_for(fut=self.place_order_called_event.wait(), timeout=timeout)
        )

    def run_until_cancel_order_called(self, timeout: float = 1):
        asyncio.get_event_loop().run_until_complete(
            asyncio.wait_for(fut=self.cancel_order_called_event.wait(), timeout=timeout)
        )

    def run_until_update_market_called(self, timeout: float = 1):
        asyncio.get_event_loop().run_until_complete(
            asyncio.wait_for(fut=self.update_market_called_event.wait(), timeout=timeout)
        )

    def run_until_transaction_status_update_called(self, timeout: float = 1):
        asyncio.get_event_loop().run_until_complete(
            asyncio.wait_for(fut=self.transaction_status_update_called_event.wait(), timeout=timeout)
        )

    def run_until_update_ticker_called(self, timeout: float = 1):
        asyncio.get_event_loop().run_until_complete(
            asyncio.wait_for(fut=self.update_ticker_called_event.wait(), timeout=timeout)
        )

    def run_until_orderbook_snapshot_called(self, timeout: float = 1):
        asyncio.get_event_loop().run_until_complete(
            asyncio.wait_for(fut=self.orderbook_snapshot_called_event.wait(), timeout=timeout)
        )

    def run_until_update_balances_called(self, timeout: float = 1):
        asyncio.get_event_loop().run_until_complete(
            asyncio.wait_for(fut=self.update_balances_called_event.wait(), timeout=timeout)
        )

    def configure_place_order_response(
            self,
            timestamp: int,
            transaction_hash: str,
            exchange_order_id: str,
    ):
        def place_and_return(*_, **__):
            self.place_order_called_event.set()
            return {
                "network": "xrpl",
                "timestamp": timestamp,
                "latency": 2,
                "txHash": transaction_hash,
            }

        def transaction_update_and_return(*_, **__):
            self.transaction_status_update_called_event.set()
            return {
                "sequence": exchange_order_id
            }

        self.gateway_instance_mock.clob_place_order.side_effect = place_and_return
        self.gateway_instance_mock.get_transaction_status.side_effect = transaction_update_and_return

    def configure_cancel_order_response(self, timestamp: int, transaction_hash: str):
        def cancel_and_return(*_, **__):
            self.cancel_order_called_event.set()
            return {
                "network": "xrpl",
                "timestamp": timestamp,
                "latency": 2,
                "txHash": transaction_hash,
            }

        self.gateway_instance_mock.clob_cancel_order.side_effect = cancel_and_return

    def configure_trading_rules_response(self, minimum_order_size: str, base_transfer_rate: str,
                                         quote_transfer_rate: str):
        def update_market_and_return(*_, **__):
            self.update_market_called_event.set()
            return {
                "markets": [
                    {"marketId": self.market_id,
                     "minimumOrderSize": minimum_order_size,
                     "smallestTickSize": str(min(self.base_decimals, self.quote_decimals)),
                     "baseTickSize": self.base_decimals,
                     "quoteTickSize": self.quote_decimals,
                     "baseTransferRate": base_transfer_rate,
                     "quoteTransferRate": quote_transfer_rate,
                     "baseIssuer": self.base_coin_issuer,
                     "quoteIssuer": self.quote_coin_issuer,
                     "baseCurrency": self.base,
                     "quoteCurrency": self.quote, }
                ],

            }

        self.gateway_instance_mock.get_clob_markets.side_effect = update_market_and_return

    def configure_last_traded_price_response(self, price: str, trading_pair: str):
        def update_market_and_return(*_, **__):
            self.update_ticker_called_event.set()
            return {
                "markets": [
                    {
                        "marketId": trading_pair,
                        "midprice": price
                    }
                ]
            }

        self.gateway_instance_mock.get_clob_ticker.side_effect = update_market_and_return

    def configure_orderbook_snapshot(self, timestamp: float, bids: List[Tuple[float, float]],
                                     asks: List[Tuple[float, float]]):
        def update_orderbook_and_return(*_, **__):
            self.orderbook_snapshot_called_event.set()
            transformed_bids = [{"price": price, "quantity": quantity} for price, quantity in bids]
            transformed_asks = [{"price": price, "quantity": quantity} for price, quantity in asks]

            return {
                "timestamp": timestamp,
                "buys": transformed_bids,
                "sells": transformed_asks
            }

        self.gateway_instance_mock.get_clob_orderbook_snapshot.side_effect = update_orderbook_and_return

    def configure_get_account_balances_response(self, base: str, quote: str,
                                                base_balance: Decimal,
                                                quote_balance: Decimal):
        def update_balances_and_return(*_, **__):
            self.update_balances_called_event.set()

            return {
                "balances": {
                    base: {
                        "total_balance": base_balance,
                        "available_balance": base_balance
                    },
                    quote: {
                        "total_balance": quote_balance,
                        "available_balance": quote_balance
                    }
                }
            }

        self.gateway_instance_mock.get_balances.side_effect = update_balances_and_return
