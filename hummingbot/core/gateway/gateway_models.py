# Generated from gateway-openapi.json by 'make gateway-models'. Do not edit.
# flake8: noqa: E501

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, condecimal, confloat, conint


class AmmPoolInfo(BaseModel):
    address: str
    base_token_address: str = Field(..., alias='baseTokenAddress')
    quote_token_address: str = Field(..., alias='quoteTokenAddress')
    fee_pct: Decimal = Field(..., alias='feePct')
    price: Decimal
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')


class AmmGetPoolInfoRequest(BaseModel):
    network: str | None = None
    pool_address: str = Field(..., alias='poolAddress')


class AmmAddLiquidityRequest(BaseModel):
    network: str | None = None
    wallet_address: str | None = Field(None, alias='walletAddress')
    pool_address: str = Field(..., alias='poolAddress')
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct')


class AmmAddLiquidityResponseData(BaseModel):
    fee: Decimal
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool this operation acted on')
    position_address: str | None = Field(None, alias='positionAddress', description='Position the liquidity went into. Absent on fungible-LP AMMs, which hold liquidity as LP tokens rather than a position account.')
    position_rent: Decimal | None = Field(None, alias='positionRent', description='Native token locked as rent when this call opened the position. Absent when adding to a position that already existed, and on fungible-LP AMMs.')
    base_token_amount_added: Decimal = Field(..., alias='baseTokenAmountAdded')
    quote_token_amount_added: Decimal = Field(..., alias='quoteTokenAmountAdded')


class AmmOpenPositionResponseData(BaseModel):
    fee: Decimal
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool this operation acted on')
    position_address: str | None = Field(None, alias='positionAddress', description='Address of the newly opened position. Absent on fungible-LP AMMs, which hold liquidity as LP tokens rather than a position account.')
    position_rent: Decimal = Field(..., alias='positionRent', description='Native token locked as rent for the position account, refunded on close. 0 on fungible-LP AMMs, which lock no rent.')
    base_token_amount_added: Decimal = Field(..., alias='baseTokenAmountAdded')
    quote_token_amount_added: Decimal = Field(..., alias='quoteTokenAmountAdded')


class AmmClosePositionResponseData(BaseModel):
    fee: Decimal
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool this operation acted on')
    position_address: str | None = Field(None, alias='positionAddress', description='Position this operation acted on')
    position_rent_refunded: Decimal = Field(..., alias='positionRentRefunded', description='Native token rent returned when the position account closed. 0 on fungible-LP AMMs, which have no position account to close.')
    base_token_amount_removed: Decimal = Field(..., alias='baseTokenAmountRemoved')
    quote_token_amount_removed: Decimal = Field(..., alias='quoteTokenAmountRemoved')


class QuoteLiquidityRequest(BaseModel):
    network: str | None = None
    pool_address: str = Field(..., alias='poolAddress')
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct')


class QuoteLiquidityResponse(BaseModel):
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool the quote was computed against')
    base_limited: bool = Field(..., alias='baseLimited')
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')
    base_token_amount_max: Decimal = Field(..., alias='baseTokenAmountMax')
    quote_token_amount_max: Decimal = Field(..., alias='quoteTokenAmountMax')


class AmmRemoveLiquidityRequest(BaseModel):
    network: str | None = None
    wallet_address: str | None = Field(None, alias='walletAddress')
    pool_address: str = Field(..., alias='poolAddress')
    percentage_to_remove: condecimal(ge=Decimal('0'), le=Decimal('100')) = Field(..., alias='percentageToRemove')


class AmmRemoveLiquidityResponseData(BaseModel):
    fee: Decimal
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool this operation acted on')
    position_address: str | None = Field(None, alias='positionAddress', description='Position this operation acted on')
    base_token_amount_removed: Decimal = Field(..., alias='baseTokenAmountRemoved')
    quote_token_amount_removed: Decimal = Field(..., alias='quoteTokenAmountRemoved')


class CreatePoolRequest(BaseModel):
    network: str | None = None
    wallet_address: str | None = Field(None, alias='walletAddress')
    base_token: str = Field(..., alias='baseToken', description='Base token symbol or address (becomes the pool base)')
    quote_token: str = Field(..., alias='quoteToken', description='Quote token symbol or address (becomes the pool quote)')
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount', description='Amount of base token to seed the pool with')
    quote_token_amount: Decimal | None = Field(None, alias='quoteTokenAmount', description='Amount of quote token to seed with. If provided, the base:quote ratio sets the initial price. If omitted (and no initialPrice), the price is fetched from the market.')
    initial_price: Decimal | None = Field(None, alias='initialPrice', description='Initial price as quote per base. Overrides quoteTokenAmount. If both are omitted, the current market price is fetched from the unified swap router so the pool opens on-market.')


class CreatePoolResponseData(BaseModel):
    fee: Decimal
    base_token_amount_added: Decimal = Field(..., alias='baseTokenAmountAdded')
    quote_token_amount_added: Decimal = Field(..., alias='quoteTokenAmountAdded')


class PositionDetail(BaseModel):
    position_address: str = Field(..., alias='positionAddress', description='Address of the individual position (NFT position account)')
    lp_token_amount: Decimal = Field(..., alias='lpTokenAmount', description='Liquidity held by this position (LP units)')
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')


class AmmPositionInfo(BaseModel):
    pool_address: str = Field(..., alias='poolAddress')
    wallet_address: str = Field(..., alias='walletAddress')
    base_token_address: str = Field(..., alias='baseTokenAddress')
    quote_token_address: str = Field(..., alias='quoteTokenAddress')
    lp_token_amount: Decimal = Field(..., alias='lpTokenAmount')
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')
    price: Decimal
    positions: list[PositionDetail] | None = None


class AmmGetPositionInfoRequest(BaseModel):
    network: str | None = None
    pool_address: str = Field(..., alias='poolAddress')
    wallet_address: str | None = Field(None, alias='walletAddress')


class Side(Enum):
    buy = 'BUY'
    sell = 'SELL'


class AmmQuoteSwapRequest(BaseModel):
    network: str | None = None
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool address (optional - can be looked up from baseToken and quoteToken)')
    base_token: str = Field(..., alias='baseToken', description='Token to determine swap direction')
    quote_token: str | None = Field(None, alias='quoteToken', description='The other token in the pair (optional - required if poolAddress not provided)')
    amount: Decimal
    side: Side = Field(..., description='Trade direction')
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct')


class AmmQuoteSwapResponse(BaseModel):
    pool_address: str = Field(..., alias='poolAddress')
    token_in: str = Field(..., alias='tokenIn')
    token_out: str = Field(..., alias='tokenOut')
    amount_in: Decimal = Field(..., alias='amountIn')
    amount_out: Decimal = Field(..., alias='amountOut')
    price: Decimal
    slippage_pct: Decimal | None = Field(None, alias='slippagePct')
    min_amount_out: Decimal = Field(..., alias='minAmountOut')
    max_amount_in: Decimal = Field(..., alias='maxAmountIn')
    price_impact_pct: Decimal = Field(..., alias='priceImpactPct')


class AmmExecuteSwapRequest(BaseModel):
    wallet_address: str | None = Field(None, alias='walletAddress')
    network: str | None = None
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool address (optional - can be looked up from baseToken and quoteToken)')
    base_token: str = Field(..., alias='baseToken')
    quote_token: str | None = Field(None, alias='quoteToken', description='The other token in the pair (optional - required if poolAddress not provided)')
    amount: Decimal
    side: Side
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct')


class AmmExecuteSwapResponseData(BaseModel):
    token_in: str = Field(..., alias='tokenIn')
    token_out: str = Field(..., alias='tokenOut')
    amount_in: Decimal = Field(..., alias='amountIn')
    amount_out: Decimal = Field(..., alias='amountOut')
    fee: Decimal
    base_token_balance_change: Decimal = Field(..., alias='baseTokenBalanceChange')
    quote_token_balance_change: Decimal = Field(..., alias='quoteTokenBalanceChange')
    slippage_pct: Decimal | None = Field(None, alias='slippagePct', description='Slippage tolerance percentage actually applied to the swap')


class EstimateGasRequest(BaseModel):
    network: str | None = None


class EstimateGasResponse(BaseModel):
    fee_per_compute_unit: Decimal = Field(..., alias='feePerComputeUnit')
    denomination: str
    compute_units: float = Field(..., alias='computeUnits')
    fee_asset: str = Field(..., alias='feeAsset')
    fee: Decimal
    timestamp: float
    gas_type: str | None = Field(None, alias='gasType')
    max_fee_per_gas: Decimal | None = Field(None, alias='maxFeePerGas')
    max_priority_fee_per_gas: Decimal | None = Field(None, alias='maxPriorityFeePerGas')
    priority_fee_level: str | None = Field(None, alias='priorityFeeLevel')
    priority_fee_per_cu_estimate: Decimal | None = Field(None, alias='priorityFeePerCUEstimate')


class BalanceRequest(BaseModel):
    network: str | None = None
    address: str | None = None
    tokens: list[str] | None = Field(None, description='a list of token symbols or addresses')
    fetch_all: bool | None = Field(None, alias='fetchAll', description='fetch all tokens in wallet, not just those in token list (default: false)')


class BalanceResponse(BaseModel):
    balances: dict[str, float]


class TokensRequest(BaseModel):
    network: str | None = None
    token_symbols: str | list[str] | None = Field(None, alias='tokenSymbols')


class Token(BaseModel):
    symbol: str
    address: str
    decimals: float
    name: str


class TokensResponse(BaseModel):
    tokens: list[Token]


class PollRequest(BaseModel):
    network: str | None = None
    signature: str = Field(..., description='Transaction signature/hash')


class PollResponse(BaseModel):
    current_block: float = Field(..., alias='currentBlock')
    signature: str
    tx_block: float | None = Field(..., alias='txBlock')
    tx_status: float = Field(..., alias='txStatus', description='Transaction status: 1 = confirmed, 0 = pending, -1 = failed, -2 = not found (unknown to the chain: never received or dropped; on Solana this is terminal once the transaction blockhash expires)')
    fee: float | None
    error: str | None
    tx_data: dict[str, Any] | None = Field(..., alias='txData')


class StatusRequest(BaseModel):
    network: str | None = None


class StatusResponse(BaseModel):
    chain: str
    network: str
    rpc_url: str = Field(..., alias='rpcUrl')
    rpc_provider: str = Field(..., alias='rpcProvider')
    current_block_number: float = Field(..., alias='currentBlockNumber')
    native_currency: str = Field(..., alias='nativeCurrency')
    swap_provider: str = Field(..., alias='swapProvider')


class ChainQuoteSwapResponse(BaseModel):
    token_in: str = Field(..., alias='tokenIn', description='Address of the token being swapped from')
    token_out: str = Field(..., alias='tokenOut', description='Address of the token being swapped to')
    amount_in: Decimal = Field(..., alias='amountIn', description='Amount of tokenIn to be swapped')
    amount_out: Decimal = Field(..., alias='amountOut', description='Expected amount of tokenOut to receive')
    price: Decimal = Field(..., description='Exchange rate between tokenIn and tokenOut')
    price_impact_pct: Decimal = Field(..., alias='priceImpactPct', description='Estimated price impact percentage (0-100)')
    min_amount_out: Decimal = Field(..., alias='minAmountOut', description='Minimum amount of tokenOut that will be accepted')
    max_amount_in: Decimal = Field(..., alias='maxAmountIn', description='Maximum amount of tokenIn that will be spent')
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool address for AMM/CLMM swaps')
    route_path: str | None = Field(None, alias='routePath', description='Route path for router-based swaps')
    slippage_pct: Decimal | None = Field(None, alias='slippagePct', description='Slippage tolerance percentage')


class ChainExecuteSwapResponseData(BaseModel):
    token_in: str = Field(..., alias='tokenIn', description='Address of the token swapped from')
    token_out: str = Field(..., alias='tokenOut', description='Address of the token swapped to')
    amount_in: Decimal = Field(..., alias='amountIn', description='Actual amount of tokenIn swapped')
    amount_out: Decimal = Field(..., alias='amountOut', description='Actual amount of tokenOut received')
    fee: Decimal = Field(..., description='Transaction fee paid')
    base_token_balance_change: Decimal = Field(..., alias='baseTokenBalanceChange', description='Change in base token balance (negative for decrease)')
    quote_token_balance_change: Decimal = Field(..., alias='quoteTokenBalanceChange', description='Change in quote token balance (negative for decrease)')
    slippage_pct: Decimal | None = Field(None, alias='slippagePct', description='Slippage tolerance percentage actually applied to the swap')
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool the swap executed against. Set by the pool-scoped routes (/trading/clmm, /trading/amm), which resolve exactly one pool; a router picks its own path across pools and leaves this unset. Without it a settled fill cannot be reconciled to a venue without refetching the transaction.')


class WrapRequest(BaseModel):
    network: str | None = None
    address: str = Field(..., description='Wallet address holding the native token')
    amount: str = Field(..., description='Amount of the native token to wrap, in whole units (not lamports/wei)', examples=['1.0'])


class UnwrapRequest(BaseModel):
    network: str | None = None
    address: str = Field(..., description='Wallet address holding the wrapped token')
    amount: str | None = Field(None, description='Amount of the wrapped token to unwrap, in whole units. Solana unwraps the full balance when omitted; EVM chains require it.', examples=['1.0'])


class ChainWrapResponseData(BaseModel):
    nonce: float | None = Field(None, description='EVM transaction nonce; absent on non-EVM chains')
    fee: str
    amount: str
    wrapped_address: str = Field(..., alias='wrappedAddress')
    native_token: str = Field(..., alias='nativeToken')
    wrapped_token: str = Field(..., alias='wrappedToken')


class RouterQuoteSwapResponse(BaseModel):
    token_in: str = Field(..., alias='tokenIn', description='Address of the token being swapped from')
    token_out: str = Field(..., alias='tokenOut', description='Address of the token being swapped to')
    amount_in: Decimal = Field(..., alias='amountIn', description='Amount of tokenIn to be swapped')
    amount_out: Decimal = Field(..., alias='amountOut', description='Expected amount of tokenOut to receive')
    price: Decimal = Field(..., description='Exchange rate between tokenIn and tokenOut')
    price_impact_pct: Decimal = Field(..., alias='priceImpactPct', description='Estimated price impact percentage (0-100)')
    min_amount_out: Decimal = Field(..., alias='minAmountOut', description='Minimum amount of tokenOut that will be accepted')
    max_amount_in: Decimal = Field(..., alias='maxAmountIn', description='Maximum amount of tokenIn that will be spent')
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool address for AMM/CLMM swaps')
    route_path: str | None = Field(None, alias='routePath', description='Route path for router-based swaps')
    slippage_pct: Decimal | None = Field(None, alias='slippagePct', description='Slippage tolerance percentage')
    quote_id: str = Field(..., alias='quoteId', description='Identifier to pass to /trading/router/execute-quote')
    approximation: bool | None = Field(None, description='True when a BUY was approximated via a sell-leg ExactIn quote because the router has no ExactOut route; amountOut is an estimate rather than exact')


class FetchPoolsRequest(BaseModel):
    network: str | None = Field(None, description='Network to use')
    limit: confloat(ge=1.0, le=100.0) | None = Field(50, description='Maximum number of pools to return')
    query: str | None = Field(None, description='Search query to match pools by name, tokens, or address')
    sort_by: str | None = Field(None, alias='sortBy', description='Sort by field (connector-specific)')


class PoolListItem(BaseModel):
    address: str = Field(..., description='Pool address')
    name: str = Field(..., description='Pool name (e.g., SOL-USDC)')
    base_token_address: str = Field(..., alias='baseTokenAddress', description='Base token address')
    base_token_symbol: str = Field(..., alias='baseTokenSymbol', description='Base token symbol')
    quote_token_address: str = Field(..., alias='quoteTokenAddress', description='Quote token address')
    quote_token_symbol: str = Field(..., alias='quoteTokenSymbol', description='Quote token symbol')
    bin_step: float = Field(..., alias='binStep', description='Bin step / tick spacing')
    base_fee: Decimal = Field(..., alias='baseFee', description='Base fee percentage')
    price: Decimal = Field(..., description='Current price')
    tvl: Decimal = Field(..., description='Total value locked in USD')
    apr: Decimal | None = Field(None, description='Annual percentage rate')
    apy: Decimal | None = Field(None, description='Annual percentage yield')
    volume24h: Decimal | None = Field(None, description='24-hour trading volume')
    fees24h: Decimal | None = Field(None, description='24-hour fees collected')


class FetchPoolsResponse(BaseModel):
    pools: list[PoolListItem]
    total: float = Field(..., description='Total number of matching pools')
    page: float = Field(..., description='Current page number')
    page_size: float = Field(..., alias='pageSize', description='Number of pools per page')


class GetPositionsOwnedRequest(BaseModel):
    network: str | None = None
    wallet_address: str = Field(..., alias='walletAddress')


class BinLiquidity(BaseModel):
    bin_id: float = Field(..., alias='binId')
    price: Decimal
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')


class PoolInfo(BaseModel):
    address: str
    base_token_address: str = Field(..., alias='baseTokenAddress')
    quote_token_address: str = Field(..., alias='quoteTokenAddress')
    bin_step: float | None = Field(None, alias='binStep')
    fee_pct: Decimal = Field(..., alias='feePct')
    price: Decimal
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')
    active_bin_id: float = Field(..., alias='activeBinId')
    bins: list[BinLiquidity] | None = None


class MeteoraPoolInfo(BaseModel):
    address: str
    base_token_address: str = Field(..., alias='baseTokenAddress')
    quote_token_address: str = Field(..., alias='quoteTokenAddress')
    bin_step: float | None = Field(None, alias='binStep')
    fee_pct: Decimal = Field(..., alias='feePct')
    price: Decimal
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')
    active_bin_id: float = Field(..., alias='activeBinId')
    bins: list[BinLiquidity] | None = None
    dynamic_fee_pct: float = Field(..., alias='dynamicFeePct')
    min_bin_id: float = Field(..., alias='minBinId')
    max_bin_id: float = Field(..., alias='maxBinId')


class GetPoolInfoRequest(BaseModel):
    network: str | None = None
    pool_address: str = Field(..., alias='poolAddress')
    bin_count: conint(ge=0, le=401) | None = Field(0, alias='binCount', description='If > 0, include a `bins` array in the response (per-tickSpacing token amounts around the active tick, mirroring Meteora pool-info.bins[]). Default 0 = skip the bin fetch.')


class PositionInfo(BaseModel):
    address: str
    pool_address: str = Field(..., alias='poolAddress')
    base_token_address: str = Field(..., alias='baseTokenAddress')
    quote_token_address: str = Field(..., alias='quoteTokenAddress')
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')
    base_fee_amount: Decimal = Field(..., alias='baseFeeAmount')
    quote_fee_amount: Decimal = Field(..., alias='quoteFeeAmount')
    lower_bin_id: float = Field(..., alias='lowerBinId')
    upper_bin_id: float = Field(..., alias='upperBinId')
    lower_price: Decimal = Field(..., alias='lowerPrice')
    upper_price: Decimal = Field(..., alias='upperPrice')
    price: Decimal


class GetPositionInfoRequest(BaseModel):
    network: str | None = None
    position_address: str = Field(..., alias='positionAddress')
    wallet_address: str | None = Field(None, alias='walletAddress')


class OpenPositionRequest(BaseModel):
    network: str | None = None
    wallet_address: str | None = Field(None, alias='walletAddress')
    lower_price: Decimal = Field(..., alias='lowerPrice')
    upper_price: Decimal = Field(..., alias='upperPrice')
    pool_address: str = Field(..., alias='poolAddress')
    base_token_amount: Decimal | None = Field(None, alias='baseTokenAmount')
    quote_token_amount: Decimal | None = Field(None, alias='quoteTokenAmount')
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct')


class OpenPositionResponseData(BaseModel):
    fee: Decimal
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool this operation acted on')
    position_address: str = Field(..., alias='positionAddress')
    position_rent: Decimal = Field(..., alias='positionRent')
    base_token_amount_added: Decimal = Field(..., alias='baseTokenAmountAdded')
    quote_token_amount_added: Decimal = Field(..., alias='quoteTokenAmountAdded')


class AddLiquidityRequest(BaseModel):
    network: str | None = None
    wallet_address: str | None = Field(None, alias='walletAddress')
    position_address: str = Field(..., alias='positionAddress')
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct')


class AddLiquidityResponseData(BaseModel):
    fee: Decimal
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool this operation acted on')
    position_address: str | None = Field(None, alias='positionAddress', description='Position this operation acted on')
    base_token_amount_added: Decimal = Field(..., alias='baseTokenAmountAdded')
    quote_token_amount_added: Decimal = Field(..., alias='quoteTokenAmountAdded')


class RemoveLiquidityRequest(BaseModel):
    network: str | None = None
    wallet_address: str | None = Field(None, alias='walletAddress')
    position_address: str = Field(..., alias='positionAddress')
    percentage_to_remove: condecimal(ge=Decimal('0'), le=Decimal('100')) = Field(..., alias='percentageToRemove')


class RemoveLiquidityResponseData(BaseModel):
    fee: Decimal
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool this operation acted on')
    position_address: str | None = Field(None, alias='positionAddress', description='Position this operation acted on')
    base_token_amount_removed: Decimal = Field(..., alias='baseTokenAmountRemoved')
    quote_token_amount_removed: Decimal = Field(..., alias='quoteTokenAmountRemoved')


class CollectFeesRequest(BaseModel):
    network: str | None = None
    wallet_address: str | None = Field(None, alias='walletAddress')
    position_address: str = Field(..., alias='positionAddress')


class CollectFeesResponseData(BaseModel):
    fee: Decimal
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool this operation acted on')
    position_address: str | None = Field(None, alias='positionAddress', description='Position this operation acted on')
    base_fee_amount_collected: Decimal = Field(..., alias='baseFeeAmountCollected')
    quote_fee_amount_collected: Decimal = Field(..., alias='quoteFeeAmountCollected')


class ClosePositionRequest(BaseModel):
    network: str | None = None
    wallet_address: str | None = Field(None, alias='walletAddress')
    position_address: str = Field(..., alias='positionAddress')


class ClosePositionResponseData(BaseModel):
    fee: Decimal
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool this operation acted on')
    position_address: str | None = Field(None, alias='positionAddress', description='Position this operation acted on')
    position_rent_refunded: Decimal = Field(..., alias='positionRentRefunded')
    base_token_amount_removed: Decimal = Field(..., alias='baseTokenAmountRemoved')
    quote_token_amount_removed: Decimal = Field(..., alias='quoteTokenAmountRemoved')
    base_fee_amount_collected: Decimal = Field(..., alias='baseFeeAmountCollected')
    quote_fee_amount_collected: Decimal = Field(..., alias='quoteFeeAmountCollected')


class ClmmCreatePoolRequest(BaseModel):
    network: str | None = None
    wallet_address: str | None = Field(None, alias='walletAddress')
    base_token: str = Field(..., alias='baseToken')
    quote_token: str = Field(..., alias='quoteToken')
    initial_price: Decimal | None = Field(None, alias='initialPrice', description='Initial pool price as quote per base. If omitted, the current market price is fetched from the unified swap router so the pool opens on-market.')
    bin_step: float | None = Field(None, alias='binStep', description='Bin/tick granularity: Meteora DLMM bin step (bps); Orca Whirlpool tick spacing.')
    fee_bps: float | None = Field(None, alias='feeBps', description='Base fee in basis points: Meteora DLMM base fee; Uniswap/PancakeSwap V3 fee tier (1, 5, 30 or 100 bps; PancakeSwap also 25).')
    amm_config_index: float | None = Field(None, alias='ammConfigIndex', description='Fee-config index for the Raydium CLMM family: Raydium API config list index; pancakeswap-sol amm_config PDA index. Default 0.')


class ClmmCreatePoolResponseData(BaseModel):
    fee: Decimal


class QuotePositionRequest(BaseModel):
    network: str | None = None
    lower_price: Decimal = Field(..., alias='lowerPrice')
    upper_price: Decimal = Field(..., alias='upperPrice')
    pool_address: str = Field(..., alias='poolAddress')
    base_token_amount: Decimal | None = Field(None, alias='baseTokenAmount')
    quote_token_amount: Decimal | None = Field(None, alias='quoteTokenAmount')
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct')


class QuotePositionResponse(BaseModel):
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool the quote was computed against')
    base_limited: bool = Field(..., alias='baseLimited')
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')
    base_token_amount_max: Decimal = Field(..., alias='baseTokenAmountMax')
    quote_token_amount_max: Decimal = Field(..., alias='quoteTokenAmountMax')
    liquidity: Any | None = None


class ClmmQuoteSwapRequest(BaseModel):
    network: str | None = None
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool address (optional - can be looked up from baseToken and quoteToken)')
    base_token: str = Field(..., alias='baseToken', description='Token to determine swap direction')
    quote_token: str | None = Field(None, alias='quoteToken', description='The other token in the pair (optional - required if poolAddress not provided)')
    amount: Decimal
    side: Side = Field(..., description='Trade direction')
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct')


class ClmmQuoteSwapResponse(BaseModel):
    pool_address: str = Field(..., alias='poolAddress')
    token_in: str = Field(..., alias='tokenIn')
    token_out: str = Field(..., alias='tokenOut')
    amount_in: Decimal = Field(..., alias='amountIn')
    amount_out: Decimal = Field(..., alias='amountOut')
    price: Decimal
    slippage_pct: Decimal | None = Field(None, alias='slippagePct')
    min_amount_out: Decimal = Field(..., alias='minAmountOut')
    max_amount_in: Decimal = Field(..., alias='maxAmountIn')
    price_impact_pct: Decimal = Field(..., alias='priceImpactPct')


class ClmmExecuteSwapRequest(BaseModel):
    wallet_address: str | None = Field(None, alias='walletAddress')
    network: str | None = None
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool address (optional - can be looked up from baseToken and quoteToken)')
    base_token: str = Field(..., alias='baseToken')
    quote_token: str | None = Field(None, alias='quoteToken', description='The other token in the pair (optional - required if poolAddress not provided)')
    amount: Decimal
    side: Side
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct')


class ClmmExecuteSwapResponseData(BaseModel):
    token_in: str = Field(..., alias='tokenIn')
    token_out: str = Field(..., alias='tokenOut')
    amount_in: Decimal = Field(..., alias='amountIn')
    amount_out: Decimal = Field(..., alias='amountOut')
    fee: Decimal
    base_token_balance_change: Decimal = Field(..., alias='baseTokenBalanceChange')
    quote_token_balance_change: Decimal = Field(..., alias='quoteTokenBalanceChange')
    slippage_pct: Decimal | None = Field(None, alias='slippagePct', description='Slippage tolerance percentage actually applied to the swap')


class QuoteSwapRequest(BaseModel):
    network: str | None = Field(None, description='The blockchain network to use')
    base_token: str = Field(..., alias='baseToken', description='Token to determine swap direction')
    quote_token: str = Field(..., alias='quoteToken', description='The other token in the pair')
    amount: Decimal = Field(..., description='Amount of base token to trade')
    side: Side = Field(..., description='Trade direction - BUY means buying base token with quote token, SELL means selling base token for quote token')
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct', description='Maximum acceptable slippage percentage')
    approximate_if_no_exact_out: bool | None = Field(True, alias='approximateIfNoExactOut', description='For BUY orders on routers without ExactOut support: approximate the required input via a sell-leg quote and return an ExactIn quote flagged as an approximation. If false, such BUY requests fail with a clear error.')


class QuoteSwapResponse(BaseModel):
    quote_id: str = Field(..., alias='quoteId', description='Unique identifier for this quote')
    token_in: str = Field(..., alias='tokenIn', description='Address of the token being swapped from')
    token_out: str = Field(..., alias='tokenOut', description='Address of the token being swapped to')
    amount_in: Decimal = Field(..., alias='amountIn', description='Amount of tokenIn to be swapped')
    amount_out: Decimal = Field(..., alias='amountOut', description='Expected amount of tokenOut to receive')
    price: Decimal = Field(..., description='Exchange rate between tokenIn and tokenOut')
    price_impact_pct: Decimal = Field(..., alias='priceImpactPct', description='Estimated price impact percentage (0-100)')
    min_amount_out: Decimal = Field(..., alias='minAmountOut', description='Minimum amount of tokenOut that will be accepted')
    max_amount_in: Decimal = Field(..., alias='maxAmountIn', description='Maximum amount of tokenIn that will be spent')
    approximation: bool | None = Field(None, description='True when a BUY was approximated via a sell-leg ExactIn quote because the router does not support ExactOut; amountOut is an estimate rather than exact')


class ExecuteQuoteRequest(BaseModel):
    wallet_address: str | None = Field(None, alias='walletAddress', description='Wallet address that will execute the swap')
    network: str | None = Field(None, description='The blockchain network to use')
    quote_id: str = Field(..., alias='quoteId', description='ID of the quote to execute')


class ExecuteSwapRequest(BaseModel):
    wallet_address: str | None = Field(None, alias='walletAddress', description='Wallet address that will execute the swap')
    network: str | None = Field(None, description='The blockchain network to use')
    base_token: str = Field(..., alias='baseToken', description='Token to determine swap direction')
    quote_token: str = Field(..., alias='quoteToken', description='The other token in the pair')
    amount: Decimal = Field(..., description='Amount of base token to trade')
    side: Side = Field(..., description='Trade direction - BUY means buying base token with quote token, SELL means selling base token for quote token')
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct', description='Maximum acceptable slippage percentage')
    approximate_if_no_exact_out: bool | None = Field(True, alias='approximateIfNoExactOut', description='For BUY orders on routers without ExactOut support: approximate the required input via a sell-leg quote and execute an ExactIn swap. If false, such BUY requests fail with a clear error.')


class SwapExecuteResponseData(BaseModel):
    token_in: str = Field(..., alias='tokenIn', description='Address of the token swapped from')
    token_out: str = Field(..., alias='tokenOut', description='Address of the token swapped to')
    amount_in: Decimal = Field(..., alias='amountIn', description='Actual amount of tokenIn swapped')
    amount_out: Decimal = Field(..., alias='amountOut', description='Actual amount of tokenOut received')
    fee: Decimal = Field(..., description='Transaction fee paid')
    base_token_balance_change: Decimal = Field(..., alias='baseTokenBalanceChange', description='Change in base token balance (negative for decrease)')
    quote_token_balance_change: Decimal = Field(..., alias='quoteTokenBalanceChange', description='Change in quote token balance (negative for decrease)')
    slippage_pct: Decimal | None = Field(None, alias='slippagePct', description='Slippage tolerance percentage actually applied to the swap')


class AmmAddLiquidityResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: AmmAddLiquidityResponseData | None = None


class AmmOpenPositionResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: AmmOpenPositionResponseData | None = None


class AmmClosePositionResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: AmmClosePositionResponseData | None = None


class AmmRemoveLiquidityResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: AmmRemoveLiquidityResponseData | None = None


class CreatePoolResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    pool_address: str = Field(..., alias='poolAddress', description='Address of the newly created pool')
    price: Decimal | None = Field(None, description='Initial price the pool was seeded at (quote per base)')
    data: CreatePoolResponseData | None = None


class AmmExecuteSwapResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: AmmExecuteSwapResponseData | None = None


class ChainExecuteSwapResponse(BaseModel):
    signature: str = Field(..., description='Transaction signature/hash')
    status: float = Field(..., description='Transaction status: 0 = PENDING, 1 = CONFIRMED, -1 = FAILED')
    data: ChainExecuteSwapResponseData | None = None


class ChainWrapResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: ChainWrapResponseData | None = None


class OpenPositionResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: OpenPositionResponseData | None = None


class AddLiquidityResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: AddLiquidityResponseData | None = None


class RemoveLiquidityResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: RemoveLiquidityResponseData | None = None


class CollectFeesResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: CollectFeesResponseData | None = None


class ClosePositionResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: ClosePositionResponseData | None = None


class ClmmCreatePoolResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    pool_address: str = Field(..., alias='poolAddress', description='Address of the newly created pool')
    price: Decimal | None = Field(None, description='Initial price the pool was initialized at (quote per base)')
    data: ClmmCreatePoolResponseData | None = None


class ClmmExecuteSwapResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: ClmmExecuteSwapResponseData | None = None


class SwapExecuteResponse(BaseModel):
    signature: str = Field(..., description='Transaction signature/hash')
    status: float = Field(..., description='Transaction status: 0 = PENDING, 1 = CONFIRMED, -1 = FAILED')
    data: SwapExecuteResponseData | None = None
