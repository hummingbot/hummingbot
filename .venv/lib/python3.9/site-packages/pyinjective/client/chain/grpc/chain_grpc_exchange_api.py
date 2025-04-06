from typing import Any, Callable, Dict, List, Optional

from grpc.aio import Channel

from pyinjective.client.model.pagination import PaginationOption
from pyinjective.core.network import CookieAssistant
from pyinjective.proto.injective.exchange.v1beta1 import (
    query_pb2 as exchange_query_pb,
    query_pb2_grpc as exchange_query_grpc,
)
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class ChainGrpcExchangeApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = exchange_query_grpc.QueryStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_exchange_params(self) -> Dict[str, Any]:
        request = exchange_query_pb.QueryExchangeParamsRequest()
        response = await self._execute_call(call=self._stub.QueryExchangeParams, request=request)

        return response

    async def fetch_subaccount_deposits(
        self,
        subaccount_id: Optional[str] = None,
        subaccount_trader: Optional[str] = None,
        subaccount_nonce: Optional[int] = None,
    ) -> Dict[str, Any]:
        subaccount = None
        if subaccount_trader is not None or subaccount_nonce is not None:
            subaccount = exchange_query_pb.Subaccount(
                trader=subaccount_trader,
                subaccount_nonce=subaccount_nonce,
            )

        request = exchange_query_pb.QuerySubaccountDepositsRequest(subaccount_id=subaccount_id, subaccount=subaccount)
        response = await self._execute_call(call=self._stub.SubaccountDeposits, request=request)

        return response

    async def fetch_subaccount_deposit(
        self,
        subaccount_id: str,
        denom: str,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QuerySubaccountDepositRequest(
            subaccount_id=subaccount_id,
            denom=denom,
        )
        response = await self._execute_call(call=self._stub.SubaccountDeposit, request=request)

        return response

    async def fetch_exchange_balances(self) -> Dict[str, Any]:
        request = exchange_query_pb.QueryExchangeBalancesRequest()
        response = await self._execute_call(call=self._stub.ExchangeBalances, request=request)

        return response

    async def fetch_aggregate_volume(self, account: str) -> Dict[str, Any]:
        request = exchange_query_pb.QueryAggregateVolumeRequest(account=account)
        response = await self._execute_call(call=self._stub.AggregateVolume, request=request)

        return response

    async def fetch_aggregate_volumes(
        self,
        accounts: Optional[List[str]] = None,
        market_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QueryAggregateVolumesRequest(accounts=accounts, market_ids=market_ids)
        response = await self._execute_call(call=self._stub.AggregateVolumes, request=request)

        return response

    async def fetch_aggregate_market_volume(self, market_id: str) -> Dict[str, Any]:
        request = exchange_query_pb.QueryAggregateMarketVolumeRequest(market_id=market_id)
        response = await self._execute_call(call=self._stub.AggregateMarketVolume, request=request)

        return response

    async def fetch_aggregate_market_volumes(self, market_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        request = exchange_query_pb.QueryAggregateMarketVolumesRequest(market_ids=market_ids)
        response = await self._execute_call(call=self._stub.AggregateMarketVolumes, request=request)

        return response

    async def fetch_denom_decimal(self, denom: str) -> Dict[str, Any]:
        request = exchange_query_pb.QueryDenomDecimalRequest(denom=denom)
        response = await self._execute_call(call=self._stub.DenomDecimal, request=request)

        return response

    async def fetch_denom_decimals(self, denoms: Optional[List[str]] = None) -> Dict[str, Any]:
        request = exchange_query_pb.QueryDenomDecimalsRequest(denoms=denoms)
        response = await self._execute_call(call=self._stub.DenomDecimals, request=request)

        return response

    async def fetch_spot_markets(
        self,
        status: Optional[str] = None,
        market_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QuerySpotMarketsRequest(
            status=status,
            market_ids=market_ids,
        )
        response = await self._execute_call(call=self._stub.SpotMarkets, request=request)

        return response

    async def fetch_spot_market(self, market_id: str) -> Dict[str, Any]:
        request = exchange_query_pb.QuerySpotMarketRequest(market_id=market_id)
        response = await self._execute_call(call=self._stub.SpotMarket, request=request)

        return response

    async def fetch_full_spot_markets(
        self,
        status: Optional[str] = None,
        market_ids: Optional[List[str]] = None,
        with_mid_price_and_tob: Optional[bool] = None,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QueryFullSpotMarketsRequest(
            status=status,
            market_ids=market_ids,
            with_mid_price_and_tob=with_mid_price_and_tob,
        )
        response = await self._execute_call(call=self._stub.FullSpotMarkets, request=request)

        return response

    async def fetch_full_spot_market(
        self,
        market_id: str,
        with_mid_price_and_tob: Optional[bool] = None,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QueryFullSpotMarketRequest(
            market_id=market_id,
            with_mid_price_and_tob=with_mid_price_and_tob,
        )
        response = await self._execute_call(call=self._stub.FullSpotMarket, request=request)

        return response

    async def fetch_spot_orderbook(
        self,
        market_id: str,
        order_side: Optional[str] = None,
        limit_cumulative_notional: Optional[str] = None,
        limit_cumulative_quantity: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        limit = None
        if pagination is not None:
            limit = pagination.limit
        request = exchange_query_pb.QuerySpotOrderbookRequest(
            market_id=market_id,
            order_side=order_side,
            limit=limit,
            limit_cumulative_notional=limit_cumulative_notional,
            limit_cumulative_quantity=limit_cumulative_quantity,
        )
        response = await self._execute_call(call=self._stub.SpotOrderbook, request=request)

        return response

    async def fetch_trader_spot_orders(
        self,
        market_id: str,
        subaccount_id: str,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QueryTraderSpotOrdersRequest(
            market_id=market_id,
            subaccount_id=subaccount_id,
        )
        response = await self._execute_call(call=self._stub.TraderSpotOrders, request=request)

        return response

    async def fetch_account_address_spot_orders(
        self,
        market_id: str,
        account_address: str,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QueryAccountAddressSpotOrdersRequest(
            market_id=market_id,
            account_address=account_address,
        )
        response = await self._execute_call(call=self._stub.AccountAddressSpotOrders, request=request)

        return response

    async def fetch_spot_orders_by_hashes(
        self,
        market_id: str,
        subaccount_id: str,
        order_hashes: List[str],
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QuerySpotOrdersByHashesRequest(
            market_id=market_id,
            subaccount_id=subaccount_id,
            order_hashes=order_hashes,
        )
        response = await self._execute_call(call=self._stub.SpotOrdersByHashes, request=request)

        return response

    async def fetch_subaccount_orders(
        self,
        subaccount_id: str,
        market_id: str,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QuerySubaccountOrdersRequest(
            subaccount_id=subaccount_id,
            market_id=market_id,
        )
        response = await self._execute_call(call=self._stub.SubaccountOrders, request=request)

        return response

    async def fetch_trader_spot_transient_orders(
        self,
        market_id: str,
        subaccount_id: str,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QueryTraderSpotOrdersRequest(
            market_id=market_id,
            subaccount_id=subaccount_id,
        )
        response = await self._execute_call(call=self._stub.TraderSpotTransientOrders, request=request)

        return response

    async def fetch_spot_mid_price_and_tob(
        self,
        market_id: str,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QuerySpotMidPriceAndTOBRequest(
            market_id=market_id,
        )
        response = await self._execute_call(call=self._stub.SpotMidPriceAndTOB, request=request)

        return response

    async def fetch_derivative_mid_price_and_tob(
        self,
        market_id: str,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QueryDerivativeMidPriceAndTOBRequest(
            market_id=market_id,
        )
        response = await self._execute_call(call=self._stub.DerivativeMidPriceAndTOB, request=request)

        return response

    async def fetch_derivative_orderbook(
        self,
        market_id: str,
        limit_cumulative_notional: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        limit = None
        if pagination is not None:
            limit = pagination.limit
        request = exchange_query_pb.QueryDerivativeOrderbookRequest(
            market_id=market_id,
            limit=limit,
            limit_cumulative_notional=limit_cumulative_notional,
        )
        response = await self._execute_call(call=self._stub.DerivativeOrderbook, request=request)

        return response

    async def fetch_trader_derivative_orders(
        self,
        market_id: str,
        subaccount_id: str,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QueryTraderDerivativeOrdersRequest(
            market_id=market_id,
            subaccount_id=subaccount_id,
        )
        response = await self._execute_call(call=self._stub.TraderDerivativeOrders, request=request)

        return response

    async def fetch_account_address_derivative_orders(
        self,
        market_id: str,
        account_address: str,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QueryAccountAddressDerivativeOrdersRequest(
            market_id=market_id,
            account_address=account_address,
        )
        response = await self._execute_call(call=self._stub.AccountAddressDerivativeOrders, request=request)

        return response

    async def fetch_derivative_orders_by_hashes(
        self,
        market_id: str,
        subaccount_id: str,
        order_hashes: List[str],
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QueryDerivativeOrdersByHashesRequest(
            market_id=market_id,
            subaccount_id=subaccount_id,
            order_hashes=order_hashes,
        )
        response = await self._execute_call(call=self._stub.DerivativeOrdersByHashes, request=request)

        return response

    async def fetch_trader_derivative_transient_orders(
        self,
        market_id: str,
        subaccount_id: str,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QueryTraderDerivativeOrdersRequest(
            market_id=market_id,
            subaccount_id=subaccount_id,
        )
        response = await self._execute_call(call=self._stub.TraderDerivativeTransientOrders, request=request)

        return response

    async def fetch_derivative_markets(
        self,
        status: Optional[str] = None,
        market_ids: Optional[List[str]] = None,
        with_mid_price_and_tob: Optional[bool] = None,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QueryDerivativeMarketsRequest(
            status=status,
            market_ids=market_ids,
            with_mid_price_and_tob=with_mid_price_and_tob,
        )
        response = await self._execute_call(call=self._stub.DerivativeMarkets, request=request)

        return response

    async def fetch_derivative_market(
        self,
        market_id: str,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QueryDerivativeMarketRequest(
            market_id=market_id,
        )
        response = await self._execute_call(call=self._stub.DerivativeMarket, request=request)

        return response

    async def fetch_derivative_market_address(
        self,
        market_id: str,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QueryDerivativeMarketAddressRequest(
            market_id=market_id,
        )
        response = await self._execute_call(call=self._stub.DerivativeMarketAddress, request=request)

        return response

    async def fetch_subaccount_trade_nonce(self, subaccount_id: str) -> Dict[str, Any]:
        request = exchange_query_pb.QuerySubaccountTradeNonceRequest(subaccount_id=subaccount_id)
        response = await self._execute_call(call=self._stub.SubaccountTradeNonce, request=request)

        return response

    async def fetch_positions(self) -> Dict[str, Any]:
        request = exchange_query_pb.QueryPositionsRequest()
        response = await self._execute_call(call=self._stub.Positions, request=request)

        return response

    async def fetch_subaccount_positions(self, subaccount_id: str) -> Dict[str, Any]:
        request = exchange_query_pb.QuerySubaccountPositionsRequest(subaccount_id=subaccount_id)
        response = await self._execute_call(call=self._stub.SubaccountPositions, request=request)

        return response

    async def fetch_subaccount_position_in_market(self, subaccount_id: str, market_id: str) -> Dict[str, Any]:
        request = exchange_query_pb.QuerySubaccountPositionInMarketRequest(
            subaccount_id=subaccount_id,
            market_id=market_id,
        )
        response = await self._execute_call(call=self._stub.SubaccountPositionInMarket, request=request)

        return response

    async def fetch_subaccount_effective_position_in_market(self, subaccount_id: str, market_id: str) -> Dict[str, Any]:
        request = exchange_query_pb.QuerySubaccountEffectivePositionInMarketRequest(
            subaccount_id=subaccount_id,
            market_id=market_id,
        )
        response = await self._execute_call(call=self._stub.SubaccountEffectivePositionInMarket, request=request)

        return response

    async def fetch_perpetual_market_info(self, market_id: str) -> Dict[str, Any]:
        request = exchange_query_pb.QueryPerpetualMarketInfoRequest(market_id=market_id)
        response = await self._execute_call(call=self._stub.PerpetualMarketInfo, request=request)

        return response

    async def fetch_expiry_futures_market_info(self, market_id: str) -> Dict[str, Any]:
        request = exchange_query_pb.QueryExpiryFuturesMarketInfoRequest(market_id=market_id)
        response = await self._execute_call(call=self._stub.ExpiryFuturesMarketInfo, request=request)

        return response

    async def fetch_perpetual_market_funding(self, market_id: str) -> Dict[str, Any]:
        request = exchange_query_pb.QueryPerpetualMarketFundingRequest(market_id=market_id)
        response = await self._execute_call(call=self._stub.PerpetualMarketFunding, request=request)

        return response

    async def fetch_subaccount_order_metadata(self, subaccount_id: str) -> Dict[str, Any]:
        request = exchange_query_pb.QuerySubaccountOrderMetadataRequest(subaccount_id=subaccount_id)
        response = await self._execute_call(call=self._stub.SubaccountOrderMetadata, request=request)

        return response

    async def fetch_trade_reward_points(
        self,
        accounts: Optional[List[str]] = None,
        pending_pool_timestamp: Optional[int] = None,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QueryTradeRewardPointsRequest(
            accounts=accounts,
            pending_pool_timestamp=pending_pool_timestamp,
        )
        response = await self._execute_call(call=self._stub.TradeRewardPoints, request=request)

        return response

    async def fetch_pending_trade_reward_points(
        self,
        accounts: Optional[List[str]] = None,
        pending_pool_timestamp: Optional[int] = None,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QueryTradeRewardPointsRequest(
            accounts=accounts,
            pending_pool_timestamp=pending_pool_timestamp,
        )
        response = await self._execute_call(call=self._stub.PendingTradeRewardPoints, request=request)

        return response

    async def fetch_trade_reward_campaign(self) -> Dict[str, Any]:
        request = exchange_query_pb.QueryTradeRewardCampaignRequest()
        response = await self._execute_call(call=self._stub.TradeRewardCampaign, request=request)

        return response

    async def fetch_fee_discount_account_info(
        self,
        account: str,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QueryFeeDiscountAccountInfoRequest(account=account)
        response = await self._execute_call(call=self._stub.FeeDiscountAccountInfo, request=request)

        return response

    async def fetch_fee_discount_schedule(self) -> Dict[str, Any]:
        request = exchange_query_pb.QueryFeeDiscountScheduleRequest()
        response = await self._execute_call(call=self._stub.FeeDiscountSchedule, request=request)

        return response

    async def fetch_balance_mismatches(self, dust_factor: int) -> Dict[str, Any]:
        request = exchange_query_pb.QueryBalanceMismatchesRequest(dust_factor=dust_factor)
        response = await self._execute_call(call=self._stub.BalanceMismatches, request=request)

        return response

    async def fetch_balance_with_balance_holds(self) -> Dict[str, Any]:
        request = exchange_query_pb.QueryBalanceWithBalanceHoldsRequest()
        response = await self._execute_call(call=self._stub.BalanceWithBalanceHolds, request=request)

        return response

    async def fetch_fee_discount_tier_statistics(self) -> Dict[str, Any]:
        request = exchange_query_pb.QueryFeeDiscountTierStatisticsRequest()
        response = await self._execute_call(call=self._stub.FeeDiscountTierStatistics, request=request)

        return response

    async def fetch_mito_vault_infos(self) -> Dict[str, Any]:
        request = exchange_query_pb.MitoVaultInfosRequest()
        response = await self._execute_call(call=self._stub.MitoVaultInfos, request=request)

        return response

    async def fetch_market_id_from_vault(self, vault_address: str) -> Dict[str, Any]:
        request = exchange_query_pb.QueryMarketIDFromVaultRequest(vault_address=vault_address)
        response = await self._execute_call(call=self._stub.QueryMarketIDFromVault, request=request)

        return response

    async def fetch_historical_trade_records(self, market_id: str) -> Dict[str, Any]:
        request = exchange_query_pb.QueryHistoricalTradeRecordsRequest(market_id=market_id)
        response = await self._execute_call(call=self._stub.HistoricalTradeRecords, request=request)

        return response

    async def fetch_is_opted_out_of_rewards(self, account: str) -> Dict[str, Any]:
        request = exchange_query_pb.QueryIsOptedOutOfRewardsRequest(account=account)
        response = await self._execute_call(call=self._stub.IsOptedOutOfRewards, request=request)

        return response

    async def fetch_opted_out_of_rewards_accounts(self) -> Dict[str, Any]:
        request = exchange_query_pb.QueryOptedOutOfRewardsAccountsRequest()
        response = await self._execute_call(call=self._stub.OptedOutOfRewardsAccounts, request=request)

        return response

    async def fetch_market_volatility(
        self,
        market_id: str,
        trade_grouping_sec: Optional[int] = None,
        max_age: Optional[int] = None,
        include_raw_history: Optional[bool] = None,
        include_metadata: Optional[bool] = None,
    ) -> Dict[str, Any]:
        trade_history_options = exchange_query_pb.TradeHistoryOptions()
        if trade_grouping_sec is not None:
            trade_history_options.trade_grouping_sec = trade_grouping_sec
        if max_age is not None:
            trade_history_options.max_age = max_age
        if include_raw_history is not None:
            trade_history_options.include_raw_history = include_raw_history
        if include_metadata is not None:
            trade_history_options.include_metadata = include_metadata
        request = exchange_query_pb.QueryMarketVolatilityRequest(
            market_id=market_id, trade_history_options=trade_history_options
        )
        response = await self._execute_call(call=self._stub.MarketVolatility, request=request)

        return response

    async def fetch_binary_options_markets(self, status: Optional[str] = None) -> Dict[str, Any]:
        request = exchange_query_pb.QueryBinaryMarketsRequest(status=status)
        response = await self._execute_call(call=self._stub.BinaryOptionsMarkets, request=request)

        return response

    async def fetch_trader_derivative_conditional_orders(
        self,
        subaccount_id: Optional[str] = None,
        market_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QueryTraderDerivativeConditionalOrdersRequest(
            subaccount_id=subaccount_id,
            market_id=market_id,
        )
        response = await self._execute_call(call=self._stub.TraderDerivativeConditionalOrders, request=request)

        return response

    async def fetch_market_atomic_execution_fee_multiplier(
        self,
        market_id: str,
    ) -> Dict[str, Any]:
        request = exchange_query_pb.QueryMarketAtomicExecutionFeeMultiplierRequest(
            market_id=market_id,
        )
        response = await self._execute_call(call=self._stub.MarketAtomicExecutionFeeMultiplier, request=request)

        return response

    async def fetch_l3_derivative_orderbook(self, market_id: str) -> Dict[str, Any]:
        request = exchange_query_pb.QueryFullDerivativeOrderbookRequest(market_id=market_id)
        response = await self._execute_call(call=self._stub.L3DerivativeOrderBook, request=request)

        return response

    async def fetch_l3_spot_orderbook(self, market_id: str) -> Dict[str, Any]:
        request = exchange_query_pb.QueryFullSpotOrderbookRequest(market_id=market_id)
        response = await self._execute_call(call=self._stub.L3SpotOrderBook, request=request)

        return response

    async def fetch_market_balance(self, market_id: str) -> Dict[str, Any]:
        request = exchange_query_pb.QueryMarketBalanceRequest(market_id=market_id)
        response = await self._execute_call(call=self._stub.MarketBalance, request=request)

        return response

    async def fetch_market_balances(self) -> Dict[str, Any]:
        request = exchange_query_pb.QueryMarketBalancesRequest()
        response = await self._execute_call(call=self._stub.MarketBalances, request=request)

        return response

    async def fetch_denom_min_notional(self, denom: str) -> Dict[str, Any]:
        request = exchange_query_pb.QueryDenomMinNotionalRequest(denom=denom)
        response = await self._execute_call(call=self._stub.DenomMinNotional, request=request)

        return response

    async def fetch_denom_min_notionals(self) -> Dict[str, Any]:
        request = exchange_query_pb.QueryDenomMinNotionalsRequest()
        response = await self._execute_call(call=self._stub.DenomMinNotionals, request=request)
        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
