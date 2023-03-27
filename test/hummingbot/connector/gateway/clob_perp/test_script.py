import asyncio
import time
import unittest
from typing import Awaitable

from grpc.aio import UnaryStreamCall
from pyinjective.async_client import AsyncClient
from pyinjective.constant import Network
from pyinjective.proto.exchange.injective_accounts_rpc_pb2 import SubaccountBalancesListResponse
from pyinjective.proto.exchange.injective_derivative_exchange_rpc_pb2 import MarketsResponse


class TestScript(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

    def setUp(self) -> None:
        self.network = Network.custom(
            lcd_endpoint="https://k8s.global.mainnet.lcd.injective.network:443",
            tm_websocket_endpoint="wss://k8s.global.mainnet.tm.injective.network:443/websocket",
            grpc_endpoint="k8s.global.mainnet.chain.grpc.injective.network:443",
            grpc_exchange_endpoint="k8s.global.mainnet.exchange.grpc.injective.network:443",
            grpc_explorer_endpoint="k8s.mainnet.explorer.grpc.injective.network:443",
            chain_id="injective-1",
            env="mainnet",
        )
        self.client = AsyncClient(self.network, insecure=False)
        return super().setUp()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    async def test_get_oracle_list(self):
        response = await self.client.get_oracle_list()
        print(response)
        """region Example(JSON stringify): Oracle List Response
        [
            {
                "symbol":"ETH",
                "oracle_type":"coinbase",
                "price":"4360.145"
            },
            {
                "symbol":"BTC",
                "oracle_type":"coinbase",
                "price":"51176.9"
            },
            {
                "symbol":"BTC",
                "oracle_type":"bandibc",
                "price":"23849.05"
            },
            {
                "symbol":"ETH",
                "oracle_type":"bandibc",
                "price":"1658.574999999"
            },
            {
            "symbol":"BAYC/WETH",
            "base_symbol": "BAYC",
            "quote_symbol": "WETH",
            "oracle_type":"pricefeed",
            "price":"69.8421"
            },
        ]
        endregion"""

    async def test_get_derivative_markets(self):
        market_status = "active"
        response: MarketsResponse = await self.client.get_derivative_markets(market_status=market_status)

        print(response)
        """region Example(JSON stringify): Derivative Market List Response
        [
            {
                "market_id": "0x4ca0f92fc28be0c9761326016b5a1a2177dd6375558365116b5bdda9abc229ce",  # noqa: mock
                "market_status": "active",
                "ticker": "BTC/USDT PERP",
                "oracle_base": "BTC",
                "oracle_quote": "USDT",
                "oracle_type": "bandibc",
                "oracle_scale_factor": 6,
                "initial_margin_ratio": "0.095",
                "maintenance_margin_ratio": "0.05",
                "quote_denom": "peggy0xdAC17F958D2ee523a2206206994597C13D831ec7",  # noqa: mock
                "quote_token_meta": {
                    "name": "Tether",
                    "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # noqa: mock
                    "symbol": "USDT",
                    "logo": "https://static.alchemyapi.io/images/assets/825.png",
                    "decimals": 6,
                    "updated_at": 1676497993039
                },
                "maker_fee_rate": "-0.0001",
                "taker_fee_rate": "0.001",
                "service_provider_fee": "0.4",
                "is_perpetual": true,
                "min_price_tick_size": "100000",
                "min_quantity_tick_size": "0.0001",
                "perpetual_market_info": {
                    "hourly_funding_rate_cap": "0.0000625",
                    "hourly_interest_rate": "0.00000416666",
                    "next_funding_timestamp": 1677661200,
                    "funding_interval": 3600
                },
                "perpetual_market_funding": {
                    "cumulative_funding": "6749828879.286921884648585187",
                    "cumulative_price": "1.502338165156193724",
                    "last_timestamp": 1677660809
                }
            }
        ]
        endregion"""

    async def test_get_funding_rates(self):
        market_id: str = "0x4ca0f92fc28be0c9761326016b5a1a2177dd6375558365116b5bdda9abc229ce"  # noqa: mock
        limit: int = 1
        response: MarketsResponse = await self.client.get_funding_rates(market_id=market_id, limit=limit)

        print(response)
        """region Example(JSON stringify): Funding Rates Response
        [
            {
                "market_id": "0x4ca0f92fc28be0c9761326016b5a1a2177dd6375558365116b5bdda9abc229ce",  # noqa: mock
                "rate": "0.000025",
                "timestamp": 1677661200349,
            }
        ]
        endregion"""

    async def test_stream_derivative_order_book(self):
        market_id: str = "0x4ca0f92fc28be0c9761326016b5a1a2177dd6375558365116b5bdda9abc229ce"  # noqa: mock

        stream: UnaryStreamCall = await self.client.stream_derivative_orderbooks(market_ids=[market_id])
        async for response in stream:
            print(response)

    async def test_stream_account_balance(self):
        subaccount_id: str = "0x72B52e007d01cc5aC36349288F24CE1Bd912CEDf000000000000000000000000"  # noqa: mock
        stream: UnaryStreamCall = await self.client.stream_subaccount_balance(subaccount_id=subaccount_id)
        async for response in stream:
            print(response)

    async def test_get_subaccount_balances_list(self):
        # acct_addr: str = "inj1w26juqraq8x94smrfy5g7fxwr0v39nkluxrq07"
        subaccount_id: str = "0x72B52e007d01cc5aC36349288F24CE1Bd912CEDf000000000000000000000000"  # noqa: mock
        response: SubaccountBalancesListResponse = await self.client.get_subaccount_balances_list(
            subaccount_id=subaccount_id
        )
        # response: SubaccountBalancesListResponse = await self.client.get_portfolio(account_address=acct_addr)
        print(response)

    async def test_get_trade(self):
        market_id: str = "0x4ca0f92fc28be0c9761326016b5a1a2177dd6375558365116b5bdda9abc229ce"  # noqa: mock

        response = await self.client.get_derivative_trades(market_id=market_id)
        print(response)

    async def test_stream_transaction(self):
        stream: UnaryStreamCall = await self.client.stream_txs()
        async for response in stream:
            print(response)

    async def test_get_order_book(self):
        market_id: str = "0x9b9980167ecc3645ff1a5517886652d94a0825e54a77d2057cbbe3ebee015963"  # noqa: mock

        response = await self.client.get_derivative_orderbook(market_id=market_id)
        print(response)

    async def test_stream_positions(self):
        market_id: str = "0x4ca0f92fc28be0c9761326016b5a1a2177dd6375558365116b5bdda9abc229ce"  # noqa: mock
        stream: UnaryStreamCall = await self.client.stream_derivative_positions(market_id=market_id)
        async for response in stream:
            print(response)

    async def test_stream_prices(self):
        stream: UnaryStreamCall = await self.client.stream_oracle_prices(
            base_symbol="BTC", quote_symbol="USDT", oracle_type="bandibc"
        )
        async for response in stream:
            print(response)

    async def test_stream_markets(self):
        # stream: UnaryStreamCall = await self.client.stream_derivative_markets(
        #     market_ids=["0x4ca0f92fc28be0c9761326016b5a1a2177dd6375558365116b5bdda9abc229ce"]  # noqa: mock
        # )
        stream: UnaryStreamCall = await self.client.stream_historical_derivative_orders(
            market_id="0x9b9980167ecc3645ff1a5517886652d94a0825e54a77d2057cbbe3ebee015963"  # noqa: mock
        )
        async for response in stream:
            print(response)

    async def test_get_portfolio(self):
        acct_addr: str = "inj1w26juqraq8x94smrfy5g7fxwr0v39nkluxrq07"  # noqa: mock

        response = await self.client.get_account_portfolio(account_address=acct_addr)
        # {entry["peggy_denom"]: {"symbol": entry.name, "decimal": entry["decimals"]} for entry in mainnet_config.values() if "peggy_denom" in entry}

        print(response)

    async def test_bank_total_balance_stream_account_balance_v2(self):
        acct_addr: str = "inj1w26juqraq8x94smrfy5g7fxwr0v39nkluxrq07"  # noqa: mock

        stream: UnaryStreamCall = await self.client.stream_account_portfolio(account_address=acct_addr)
        async for response in stream:
            """
            type: "bank"
            denom: "peggy0xdAC17F958D2ee523a2206206994597C13D831ec7"  # noqa: mock
            amount: "25083070"
            """
            print(f"BANK: [{time.time()}] {response}")

    async def test_subaccount_total_balances_stream_account_balance_v2(self):
        acct_addr: str = "inj1w26juqraq8x94smrfy5g7fxwr0v39nkluxrq07"  # noqa: mock

        stream: UnaryStreamCall = await self.client.stream_account_portfolio(
            account_address=acct_addr,
            subaccount_id="0x72b52e007d01cc5ac36349288f24ce1bd912cedf000000000000000000000000",  # noqa: mock
            type="total_balances",
        )
        async for response in stream:
            """
            type: "total_balances"
            denom: "peggy0xdAC17F958D2ee523a2206206994597C13D831ec7"  # noqa: mock
            amount: "8346000.769648987490134461"
            subaccount_id: "0x72b52e007d01cc5ac36349288f24ce1bd912cedf000000000000000000000000"  # noqa: mock
            """
            print(f"SUB:  [{time.time()}] {response}")

    async def test_subaccount_available_balances_stream_account_balance_v2(self):
        acct_addr: str = "inj1w26juqraq8x94smrfy5g7fxwr0v39nkluxrq07"

        stream: UnaryStreamCall = await self.client.stream_account_portfolio(
            account_address=acct_addr,
            subaccount_id="0x72b52e007d01cc5ac36349288f24ce1bd912cedf000000000000000000000000",  # noqa: mock
            type="available_balances",
        )
        async for response in stream:
            print(response)

    async def test_get_portfolio_responses(self):
        acct_addr: str = "inj1w26juqraq8x94smrfy5g7fxwr0v39nkluxrq07"  # noqa: mock
        subaccount_id: str = "0x72B52e007d01cc5aC36349288F24CE1Bd912CEDf000000000000000000000000"  # noqa: mock
        subaccount_response: SubaccountBalancesListResponse = await self.client.get_subaccount_balances_list(
            subaccount_id=subaccount_id
        )
        portfolio_response = await self.client.get_account_portfolio(account_address=acct_addr)
        print(subaccount_response)
        print(portfolio_response)
