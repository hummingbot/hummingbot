import base64
import logging
from decimal import Decimal
from pprint import pprint
from typing import Any, List

import grpc
import numpy as np
import pandas as pd
import requests

from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.generated.penumbra.core.component.shielded_pool.v1alpha1 import (
    shielded_pool_pb2 as penumbra_dot_core_dot_component_dot_shielded__pool_dot_v1alpha1_dot_shielded__pool__pb2,
)
from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.generated.penumbra.core.component.shielded_pool.v1alpha1.shielded_pool_pb2_grpc import (
    QueryService,
)
from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.generated.penumbra.view.v1alpha1 import (
    view_pb2 as penumbra_dot_view_dot_v1alpha1_dot_view__pb2,
)
from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.generated.penumbra.view.v1alpha1.view_pb2_grpc import (
    ViewProtocolService,
)
from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.penumbra_api_data_source import (
    PenumbraAPIDataSource as PenumbraGateway,
)
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


# The original Osiris bot uses binance feeds, so we aim to do the same here
# https://binance-docs.github.io/apidocs/spot/en/#market-data-endpoints
class PenumbraOsiris(ScriptStrategyBase):
    """
    Adapted from SimplePMM strategy example
    Video: -
    Description:
    The bot will place two orders around the bid-ask binances prices in a trading_pair. Every order_refresh_time in seconds,
    the bot will cancel and replace the orders.
    """
    #! Note: Penumbra does not current support websocket connections, so the order book must be refreshed by force in each tick before execution logic can begin

    bid_spread = 0.001
    ask_spread = 0.001
    order_refresh_time = 15
    order_amount = 0.01
    create_timestamp = 0
    trading_pair = "test_usd-penumbra"
    exchange = "penumbra"
    reference_pair = "ETH-USDC"
    markets = {exchange: {trading_pair}}
    _pclientd_url = 'localhost:8081'
    _gateway_url = 'localhost:15888'

    # Override to skip the ready check which depends on websocket connection
    def tick(self, timestamp: float):
        """
        Clock tick entry point, is run every second (on normal tick setting).
        Checks if all connectors are ready, if so the strategy is ready to trade.

        :param timestamp: current tick timestamp
        """
        self.on_tick()

    def on_tick(self):
        if self.create_timestamp <= self.current_timestamp:
            self.cancel_all_orders()
            proposal: List[OrderCandidate] = self.create_proposal()
            proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(proposal)
            self.place_orders(proposal_adjusted)
            self.create_timestamp = self.order_refresh_time + self.current_timestamp

    def create_proposal(self) -> List[OrderCandidate]:
        bookTicker = requests.get(f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={self.reference_pair.replace('-', '')}").json()
        buy_price = bookTicker['bidPrice']
        sell_price = bookTicker['askPrice']

        #print("bid spread: ", buy_price)
        #print("ask spread: ", sell_price)

        buy_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                   order_side=TradeType.BUY, amount=Decimal(self.order_amount), price=buy_price)

        sell_order = OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                    order_side=TradeType.SELL, amount=Decimal(self.order_amount), price=sell_price)

        #print("buy order: ", buy_order)
        #print("sell order: ", sell_order)

        return [buy_order, sell_order]


    #! TODO
    def adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        proposal_adjusted = self.connectors[self.exchange].budget_checker.adjust_candidates(proposal, all_or_none=True)
        return proposal_adjusted

    def place_orders(self, proposal: List[OrderCandidate]) -> None:
        for order in proposal:
            self.place_order(connector_name=self.exchange, order=order)

    def place_order(self, connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            self.sell(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                      order_type=order.order_type, price=order.price)
        elif order.order_side == TradeType.BUY:
            self.buy(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                     order_type=order.order_type, price=order.price)

    def cancel_all_orders(self):
        for order in self.get_active_orders(connector_name=self.exchange):
            self.cancel(self.exchange, order.trading_pair, order.client_order_id)

    def did_fill_order(self, event: OrderFilledEvent):
        msg = (f"{event.trade_type.name} {round(event.amount, 2)} {event.trading_pair} {self.exchange} at {round(event.price, 2)}")
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)
    #! TODO

    def get_all_balances(self):
        # Create new grpc.Channel + client
        client = ViewProtocolService()
        request = penumbra_dot_view_dot_v1alpha1_dot_view__pb2.BalancesRequest()
        query_client = QueryService()

        responses = client.Balances(request=request,
                                target=self._pclientd_url,
                                insecure=True)

        balance_dict = {}

        for response in responses:
            balance = {
                "amount":
                response.balance.amount.lo,
                "asset_id":
                    bytes.fromhex(
                        response.balance.asset_id.inner.hex())
            }

            denom_req = penumbra_dot_core_dot_component_dot_shielded__pool_dot_v1alpha1_dot_shielded__pool__pb2.DenomMetadataByIdRequest()
            denom_req.asset_id.inner = balance["asset_id"]

            # Query for metadata from DenomMetadataById
            denom_res = query_client.DenomMetadataById(
                request=denom_req,
                target=self._pclientd_url,
                insecure=True)

            if not denom_res.denom_metadata:
                decimals = 0
            else:
                decimals = denom_res.denom_metadata.denom_units[0].exponent

            symbol = denom_res.denom_metadata.display

            # amount's are uint 128 bit https://buf.build/penumbra-zone/penumbra/docs/300a488c79c9490d86cf09e1eceff593:penumbra.core.num.v1alpha1#penumbra.core.num.v1alpha1.Amount
            balance = ((response.balance.amount.hi << 64)
                       | response.balance.amount.lo) / (10**decimals)

            balance_dict[symbol] = {
                "asset_id_str":
                base64.b64encode(
                    bytes.fromhex(
                        response.balance.asset_id.inner.hex())).decode(
                            'utf-8'),
                "asset_id_bytes":
                bytes.fromhex(response.balance.asset_id.inner.hex()),
                "amount":
                balance,
                "decimals":
                decimals,
            }

        '''
        example return: 
        {
            'test_usd': {'amount': 7.952016459889115,
                         'asset_id_bytes': b'\xad\xeb\xa6\xef\x04&\x93\xfa0\x82\xf1\x8c'
                                b'X\xc6g\xff\xa4E=]\xb8\xcc\x82\xaa'
                                b'\xddn\x88\x9f\xf5\xb0f\x08',
                        'asset_id_str': 'reum7wQmk/owgvGMWMZn/6RFPV24zIKq3W6In/WwZgg='}
                    }
        }
        '''

        #pprint(balance_dict)
        return balance_dict

    def get_balance_df(self):
        """
        Returns a data frame for all asset balances for displaying purpose.
        """
        columns: List[str] = [
            "Exchange", "Asset", "Total Balance"
        ]
        data: List[Any] = []

        #! Get all balances first
        all_balances = self.get_all_balances()

        for asset in self.trading_pair.split('-'):
            balance = 0
            if asset in all_balances:
                balance = all_balances[asset]['amount']

            data.append([
                self.exchange,
                asset,
                float(balance),
            ])

        df = pd.DataFrame(data=data, columns=columns).replace(np.nan,
                                                              '',
                                                              regex=True)
        df.sort_values(by=["Exchange", "Asset"], inplace=True)
        return df

    def active_orders_df(self):
        # TODO
        print("active orders df")
        return

    # TODO: get ready
    def format_status(self) -> str:
        """
        Returns status of the current strategy on user balances and current active orders. This function is called
        when status command is issued. Override this function to create custom status display output.
        """
        lines = []
        warning_lines = []
        warning_lines.extend(
            self.network_warning(self.get_market_trading_pair_tuples()))

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + [
            "    " + line
            for line in balance_df.to_string(index=False).split("\n")
        ])

        return "\n".join(lines)

        try:
            df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + [
                "    " + line for line in df.to_string(index=False).split("\n")
            ])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        warning_lines.extend(
            self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)