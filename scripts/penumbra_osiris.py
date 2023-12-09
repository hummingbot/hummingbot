import base64
import logging
import os
from decimal import Decimal
from pprint import pprint
from typing import Any, List

import numpy as np
import pandas as pd
import requests

from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.generated.penumbra.core.component.dex.v1alpha1 import (
    dex_pb2 as penumbra_dot_core_dot_component_dot_dex_dot_v1alpha1_dot_dex__pb2,
)
from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.generated.penumbra.core.component.dex.v1alpha1.dex_pb2_grpc import (
    QueryService as DexQueryService,
)
from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.generated.penumbra.core.component.shielded_pool.v1alpha1 import (
    shielded_pool_pb2 as penumbra_dot_core_dot_component_dot_shielded__pool_dot_v1alpha1_dot_shielded__pool__pb2,
)
from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.generated.penumbra.core.component.shielded_pool.v1alpha1.shielded_pool_pb2_grpc import (
    QueryService,
)
from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.generated.penumbra.custody.v1alpha1 import (
    custody_pb2 as penumbra_dot_custody_dot_v1alpha1_dot_custody__pb2,
)
from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.generated.penumbra.custody.v1alpha1.custody_pb2_grpc import (
    CustodyProtocolService,
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
from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.penumbra_constants import TOKEN_SYMBOL_MAP
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

LP_NFT_OPEN_PREFIX = 'lpnft_opened_'
LP_NFT_CLOSED_PREFIX = 'lpnft_closed_'

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
    order_refresh_time = 60
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
            bid_ask: List[float] = self.create_proposal()
            self.make_liquidity_position(bid_ask)
            self.create_timestamp = self.order_refresh_time + self.current_timestamp

    def create_proposal(self) -> List[float]:
        try:
            bookTicker = requests.get(f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={self.reference_pair.replace('-', '')}").json()
            bid_price = bookTicker['bidPrice']
            ask_price = bookTicker['askPrice']
        except:
            logging.getLogger().error("Error fetching bid/ask from binance, is your IP geolocked?")

        return [Decimal(str(bid_price)), Decimal(str(ask_price))]


    def clamp(self, value, min_value, max_value):
        """Clamps a value between a minimum and maximum value."""
        return max(min_value, min(value, max_value))


    def calculate_half_reserves(self, reserve1, reserve2):
        """
        Calculates half of the given reserves and clamps them to 80 bits.
        :param reserve1: The first reserve value.
        :param reserve2: The second reserve value.
        :return: Tuple of clamped half reserves (r1, r2).
        """

        if reserve1 == None or reserve1 == 0:
            logging.getLogger().error(
                "Not enough r1 reserves available to open a position.")
            raise ValueError("No reserves available to open a position.")
        if reserve2 == None or reserve2 == 0:
            logging.getLogger().error(
                "Not enough r2 reserves available to open a position.")
            raise ValueError("No reserves available to open a position.")

        max_80_bits = 2**80 - 1
        half_reserve1 = self.clamp(reserve1 // 2, 0, max_80_bits)
        half_reserve2 = self.clamp(reserve2 // 2, 0, max_80_bits)

        if half_reserve1 == 0 or half_reserve2 == 0:
            logging.getLogger().error(
                "Not enough reserves available to open a position.")
            raise ValueError("No reserves available to open a position.")

        return [half_reserve1, half_reserve2]

    def int_to_lo_hi(self, value):
        """
        Converts a large integer into lo and hi parts for a 128-bit unsigned integer.
        :param value: The integer to be converted.
        :return: A tuple (lo, hi) representing the low and high parts of the integer.
        """
        # Ensure value fits in 128 bits
        if value.bit_length() > 128:
            raise ValueError("Value is too large to fit in 128 bits")

        # Mask to extract 64 bits.
        mask = (1 << 64) - 1

        # Extract lo and hi values.
        lo = value & mask
        hi = (value >> 64) & mask

        return [lo, hi]

    def hi_low_to_human_readable(self, hi, lo, decimals):
        return ((hi << 64) | lo) / (10**decimals)

    def generate_nonce(self):
        """Generate a 32-byte nonce."""
        nonce_bytes = os.urandom(32)
        return nonce_bytes

    def authorize_tx(self, transaction):
        auth_client = CustodyProtocolService()

        auth_request = penumbra_dot_custody_dot_v1alpha1_dot_custody__pb2.AuthorizeRequest()
        auth_request.plan.CopyFrom(transaction.plan)

        auth_response = auth_client.Authorize(request=auth_request,target=self._pclientd_url,insecure=True)

        return auth_response

    #! TODO
    # https://guide.penumbra.zone/main/pclientd/build_transaction.html
    def make_liquidity_position(self, bid_ask: List[int]):
        try:
            client = ViewProtocolService()
            transactionPlanRequest = penumbra_dot_view_dot_v1alpha1_dot_view__pb2.TransactionPlannerRequest()

            # Set fee to zero
            transactionPlanRequest.fee.amount.lo = self.int_to_lo_hi(0)[0]

            # Assuming you have values for fee, p, q, your_trading_pair, your_reserve1, your_reserve2, and your_nonce
            # Set the TradingFunction directly
            trading_function = transactionPlanRequest.position_opens.add().position.phi

            midPrice = Decimal(bid_ask[0] + bid_ask[1]) / 2
            scaling_factor = Decimal('1000')
            midPrice = midPrice * scaling_factor

            while midPrice < 1:
                scaling_factor = scaling_factor * 1000
                midPrice = midPrice * 1000

            # P is always scaling value
            p_val = self.int_to_lo_hi(int(scaling_factor))

            trading_function.component.p.lo = p_val[0]
            trading_function.component.p.hi = p_val[1]

            q_val = self.int_to_lo_hi(int(midPrice))

            trading_function.component.q.lo = q_val[0]
            trading_function.component.q.hi = q_val[1]

            # Calculate spread:
            difference = scaling_factor * abs(bid_ask[1] - bid_ask[0])
            fraction = difference / midPrice
            # max of 50% fee, min of 100 bps (1%)
            spread = fraction * 100 * 100
            spread = max(100, min(spread, 5000))

            trading_function.component.fee = int(spread)

            # Get asset ids from constants file
            id_1 = TOKEN_SYMBOL_MAP[self.trading_pair.split('-')[0]]
            id_2 = TOKEN_SYMBOL_MAP[self.trading_pair.split('-')[1]]

            if id_1 is None:
                logging.getLogger().error(
                    f"Asset {self.trading_pair.split('-')[0]} not found in constants file"
                )
            if id_2 is None:
                logging.getLogger().error(
                    f"Asset {self.trading_pair.split('-')[1]} not found in constants file"
                )

            trading_function.pair.asset_1.inner = base64.b64decode(
                id_1['address'])
            trading_function.pair.asset_2.inner = base64.b64decode(
                id_2['address'])

            # Set the PositionState directly
            position_state = transactionPlanRequest.position_opens[0].position.state
            position_state.state = 1

            # Set the Reserves directly
            reserves = transactionPlanRequest.position_opens[0].position.reserves

            # TODO: really should be availible balances
            # Get all balances
            balances = self.get_all_balances()
            res1 = balances[self.trading_pair.split('-')[0]]['amount'] * 10**balances[self.trading_pair.split('-')[0]]['decimals']
            res2 = balances[self.trading_pair.split('-')[1]]['amount'] * 10**balances[self.trading_pair.split('-')[1]]['decimals']

            half_reserve1, half_reserve2 = self.calculate_half_reserves(res1, res2)

            half_reserve1 = self.int_to_lo_hi(int(half_reserve1))
            half_reserve2 = self.int_to_lo_hi(int(half_reserve2))

            reserves.r1.lo = half_reserve1[0]
            reserves.r1.hi = half_reserve1[1]
            reserves.r2.lo = half_reserve2[0]
            reserves.r2.hi = half_reserve2[1]


            # Set other fields of Position
            transactionPlanRequest.position_opens[0].position.close_on_fill = False
            transactionPlanRequest.position_opens[0].position.nonce = self.generate_nonce()

            transactionPlanResponse = client.TransactionPlanner(request=transactionPlanRequest,target=self._pclientd_url,insecure=True)

            # Authorize the tx
            authorized_resp = self.authorize_tx(transactionPlanResponse)

            # Witness & Build
            wit_and_build_req = penumbra_dot_view_dot_v1alpha1_dot_view__pb2.WitnessAndBuildRequest()
            wit_and_build_req.transaction_plan.CopyFrom(transactionPlanResponse.plan)
            wit_and_build_req.authorization_data.CopyFrom(authorized_resp.data)

            wit_and_build_resp = client.WitnessAndBuild(request=wit_and_build_req,target=self._pclientd_url,insecure=True)

            # Broadcast
            broadcast_request = penumbra_dot_view_dot_v1alpha1_dot_view__pb2.BroadcastTransactionRequest()
            broadcast_request.transaction.CopyFrom(wit_and_build_resp.transaction)
            # Service will await detection on chain
            broadcast_request.await_detection = True

            logging.getLogger().info("Creating order...")
            broadcast_response = client.BroadcastTransaction(request=broadcast_request,target=self._pclientd_url,insecure=True, timeout=60)
            logging.getLogger().info(f"Order created at block {broadcast_response.detection_height} in tx hash: {broadcast_response.id.hash.hex()}")
            #breakpoint()

        except Exception as e:
            logging.getLogger().error(f"Error making liquidity position: {str(e)}")

    # Cancel & withdraw from all orders
    def cancel_all_orders(self):
        active_orders, closed_orders = self.get_orders()
        #logging.getLogger().info("Orders: ", active_orders)

        client = ViewProtocolService()

        # Iterate over dictionary keys
        order_key_list = list(active_orders.keys())

        for order_key in order_key_list:
            try:
                transactionPlanRequest = penumbra_dot_view_dot_v1alpha1_dot_view__pb2.TransactionPlannerRequest()

                # Set fee to zero
                transactionPlanRequest.fee.amount.lo = self.int_to_lo_hi(0)[0]

                # Set the Position directly
                position_close_bech32m = transactionPlanRequest.position_closes.add().position_id
                position_close_bech32m.alt_bech32m = order_key_list[order_key]['asset'].denom_metadata.display.split(LP_NFT_OPEN_PREFIX)[1]

                transactionPlanResponse = client.TransactionPlanner(request=transactionPlanRequest,target=self._pclientd_url,insecure=True)

                # Authorize the tx
                authorized_resp = self.authorize_tx(transactionPlanResponse)

                # Witness & Build
                wit_and_build_req = penumbra_dot_view_dot_v1alpha1_dot_view__pb2.WitnessAndBuildRequest()
                wit_and_build_req.transaction_plan.CopyFrom(transactionPlanResponse.plan)
                wit_and_build_req.authorization_data.CopyFrom(authorized_resp.data)

                wit_and_build_resp = client.WitnessAndBuild(request=wit_and_build_req,target=self._pclientd_url,insecure=True)

                # Broadcast
                broadcast_request = penumbra_dot_view_dot_v1alpha1_dot_view__pb2.BroadcastTransactionRequest()
                broadcast_request.transaction.CopyFrom(wit_and_build_resp.transaction)
                # Service will await detection on chain
                broadcast_request.await_detection = True

                logging.getLogger().info("Deleting order..")
                broadcast_response = client.BroadcastTransaction(request=broadcast_request,target=self._pclientd_url,insecure=True)
                logging.getLogger().info(
                    f"Order deleted at block {broadcast_response.detection_height} in tx hash: {broadcast_response.id.hash.hex()}"
                )

                #breakpoint()

            except Exception as e:
                logging.getLogger().error(f"Error cancelling liquidity position: {str(e)}")


        # Withdraw from positions, iterate over closed orders if there were any, and also attempt to withdraw from any active positions since we just closed them
        # Concat the 2 dictionaries
        all_orders = {**active_orders, **closed_orders}
        all_order_keys = list(all_orders.keys())
        breakpoint()

        for order_key in all_order_keys:
            try:
                transactionPlanRequest = penumbra_dot_view_dot_v1alpha1_dot_view__pb2.TransactionPlannerRequest()

                # Set fee to zero
                transactionPlanRequest.fee.amount.lo = self.int_to_lo_hi(0)[0]

                # Set the Position directly
                position_withdraw_bech32m = transactionPlanRequest.position_withdraws.add().position_id
                position_withdraw_bech32m.alt_bech32m = all_orders[order_key]['asset'].denom_metadata.display.split(LP_NFT_CLOSED_PREFIX)[1] # Always closed prefix bc these orders should always be closed this point

                # Set the remaining Reserves
                zero_res = self.int_to_lo_hi(0)
                transactionPlanRequest.position_withdraws[0].reserves.r1.lo = zero_res[0]
                transactionPlanRequest.position_withdraws[0].reserves.r1.hi = zero_res[1]
                transactionPlanRequest.position_withdraws[0].reserves.r2.lo = zero_res[0]
                transactionPlanRequest.position_withdraws[0].reserves.r2.hi = zero_res[1]

                # Set the trading pair
                transactionPlanRequest.position_withdraws[0].trading_pair.asset_1.inner = bytes.fromhex(all_orders[order_key]['position'].phi.pair.asset_1.inner.hex())
                transactionPlanRequest.position_withdraws[0].trading_pair.asset_2.inner = bytes.fromhex(all_orders[order_key]['position'].phi.pair.asset_2.inner.hex())

                transactionPlanResponse = client.TransactionPlanner(request=transactionPlanRequest,target=self._pclientd_url,insecure=True)

                # Authorize the tx
                authorized_resp = self.authorize_tx(transactionPlanResponse)

                # Witness & Build
                wit_and_build_req = penumbra_dot_view_dot_v1alpha1_dot_view__pb2.WitnessAndBuildRequest()
                wit_and_build_req.transaction_plan.CopyFrom(transactionPlanResponse.plan)
                wit_and_build_req.authorization_data.CopyFrom(authorized_resp.data)

                wit_and_build_resp = client.WitnessAndBuild(request=wit_and_build_req,target=self._pclientd_url,insecure=True)

                # Broadcast
                broadcast_request = penumbra_dot_view_dot_v1alpha1_dot_view__pb2.BroadcastTransactionRequest()
                broadcast_request.transaction.CopyFrom(wit_and_build_resp.transaction)
                # Service will await detection on chain
                broadcast_request.await_detection = True

                breakpoint()

                logging.getLogger().info("Withdrawing from position..")
                broadcast_response = client.BroadcastTransaction(request=broadcast_request,target=self._pclientd_url,insecure=True)
                logging.getLogger().info(
                    f"Withdrawn from position at block {broadcast_response.detection_height} in tx hash: {broadcast_response.id.hash.hex()}"
                )

            except Exception as e:
                logging.getLogger().error(f"Error withdrawing from liquidity position: {str(e)}")


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

        responses = client.Balances(request=request,target=self._pclientd_url,insecure=True)

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

            if not denom_res.denom_metadata.denom_units:
                decimals = 0
            else:
                decimals = denom_res.denom_metadata.denom_units[0].exponent

            symbol = denom_res.denom_metadata.display

            # amount's are uint 128 bit https://buf.build/penumbra-zone/penumbra/docs/300a488c79c9490d86cf09e1eceff593:penumbra.core.num.v1alpha1#penumbra.core.num.v1alpha1.Amount
            balance = Decimal(str(self.hi_low_to_human_readable(response.balance.amount.hi, response.balance.amount.lo, decimals)))

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
            "Exchange", "Asset", "Availible Balance"
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

    def get_orders(self):
        client = ViewProtocolService()
        query_client = DexQueryService()

        # Get all the cleaned assets
        assets_req = penumbra_dot_view_dot_v1alpha1_dot_view__pb2.AssetsRequest()
        assets_req.include_lp_nfts = True
        assets = client.Assets(request=assets_req,target=self._pclientd_url,insecure=True)

        cleaned_assets = {}

        for asset in assets:
            # Only get assets with prefix 'lpnft_opened'

            denomDisplay = asset.denom_metadata.display

            if str(denomDisplay).startswith(LP_NFT_OPEN_PREFIX) or str(denomDisplay).startswith(LP_NFT_CLOSED_PREFIX):
                asset_id = base64.b64encode(bytes.fromhex(asset.denom_metadata.penumbra_asset_id.inner.hex()))
                cleaned_assets[asset_id] = asset

        # Get all the notes
        notes_req = penumbra_dot_view_dot_v1alpha1_dot_view__pb2.NotesRequest()
        notes_req.include_spent = False

        notes_resp = client.Notes(request=notes_req,target=self._pclientd_url,insecure=True)

        active_liq_positions = {}
        closed_liq_positions = {}

        for note in notes_resp:
            id_byte_str =  base64.b64encode(bytes.fromhex(note.note_record.note.value.asset_id.inner.hex()))

            # Associate the note with it's relevant asset in cleaned_assets by matching on penumbra_asset_id.inner & id_str
            if id_byte_str in cleaned_assets:
                # Get Position Data
                liq_request = penumbra_dot_core_dot_component_dot_dex_dot_v1alpha1_dot_dex__pb2.LiquidityPositionByIdRequest()

                # get the current prefix
                if str(cleaned_assets[id_byte_str].denom_metadata.display).startswith(LP_NFT_OPEN_PREFIX):
                    current_prefix = LP_NFT_OPEN_PREFIX
                elif str(cleaned_assets[id_byte_str].denom_metadata.display).startswith(LP_NFT_CLOSED_PREFIX):
                    current_prefix = LP_NFT_CLOSED_PREFIX
                else:
                    logging.getLogger().error(f"Prefix unsupported: {id_byte_str}")
                    raise ValueError(f"Prefix unsupported: {id_byte_str}")

                liq_request.position_id.alt_bech32m = str(
                    cleaned_assets[id_byte_str].denom_metadata.display).split(
                        current_prefix)[1]

                response = query_client.LiquidityPositionById(request=liq_request,target=self._pclientd_url,insecure=True)

                position = response.data

                # Only add to list if position is open
                if position.state.state == 1:
                    active_liq_positions[id_byte_str] = {
                        'note': note,
                        'asset': cleaned_assets[id_byte_str],
                        'position': response.data
                    }
                elif position.state.state == 2:
                    closed_liq_positions[id_byte_str] = {
                        'note': note,
                        'asset': cleaned_assets[id_byte_str],
                        'position': response.data
                    }

        return active_liq_positions, closed_liq_positions

    def active_orders_df(self):
        '''
        """
        Return a data frame of all active orders for displaying purpose.
        """
        columns = ["Exchange", "Market", "Side", "Price", "Amount"]
        data = []
        for order in self.get_active_orders():
            data.append([
                connector_name,
                order.trading_pair,
                "buy" if order.is_buy else "sell",
                float(order.price),
                float(order.quantity),
            ])
        if not data:
            raise ValueError
            
        df = pd.DataFrame(data=data, columns=columns)
        df.sort_values(by=["Exchange", "Market", "Side"], inplace=True)
        '''
        return 'df'

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