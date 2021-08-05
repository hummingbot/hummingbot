import asyncio
from collections import deque
from unittest import TestCase
from unittest.mock import patch, AsyncMock, PropertyMock

from hummingbot.connector.exchange.bybit.bybit_api_order_book_data_source import BybitAPIOrderBookDataSource


class AsyncContextMock(AsyncMock):
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return


class BybitAPIOrderBookDataSourceTests(TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    def setUp(self) -> None:
        super().setUp()
        self.base_asset = "BTC"
        self.quote_asset = "USDT"
        self.trading_pair = f"{self.base_asset}-{self.quote_asset}"

        self.api_responses_json: asyncio.Queue = asyncio.Queue()
        self.api_responses_status = deque()
        self.log_records = []

        self.data_source = BybitAPIOrderBookDataSource([self.trading_pair])
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

    def handle(self, record):
        self.log_records.append(record)

    def _get_next_api_response_status(self):
        status = self.api_responses_status.popleft()
        return status

    async def _get_next_api_response_json(self):
        json = await self.api_responses_json.get()
        return json

    def _configure_mock_api(self, mock_api: AsyncMock):
        response = AsyncMock()
        type(response).status = PropertyMock(side_effect=self._get_next_api_response_status)
        response.json.side_effect = self._get_next_api_response_json
        mock_api.return_value.__aenter__.return_value = response

    @patch("aiohttp.ClientSession.get")
    def test_get_last_traded_prices(self, mock_get):
        self._configure_mock_api(mock_get)
        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                {
                    "symbol": "BTCUSD",
                    "bid_price": "7230",
                    "ask_price": "7230.5",
                    "last_price": "7230.00",
                    "last_tick_direction": "ZeroMinusTick",
                    "prev_price_24h": "7163.00",
                    "price_24h_pcnt": "0.009353",
                    "high_price_24h": "7267.50",
                    "low_price_24h": "7067.00",
                    "prev_price_1h": "7209.50",
                    "price_1h_pcnt": "0.002843",
                    "mark_price": "7230.31",
                    "index_price": "7230.14",
                    "open_interest": 117860186,
                    "open_value": "16157.26",
                    "total_turnover": "3412874.21",
                    "turnover_24h": "10864.63",
                    "total_volume": 28291403954,
                    "volume_24h": 78053288,
                    "funding_rate": "0.0001",
                    "predicted_funding_rate": "0.0001",
                    "next_funding_time": "2019-12-28T00:00:00Z",
                    "countdown_hour": 2,
                    "delivery_fee_rate": "0",
                    "predicted_delivery_price": "0.00",
                    "delivery_time": ""
                }
            ],
            "time_now": "1577484619.817968"
        }
        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait(mock_response)

        results = asyncio.get_event_loop().run_until_complete(
            asyncio.gather(self.data_source.get_last_traded_prices([self.trading_pair])))

        self.assertEqual(results[self.trading_pair], mock_response["result"][0]["last_price"])
