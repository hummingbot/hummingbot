import {
  EstimateGasResponse,
  PriceRequest,
  PriceResponse,
  TradeRequest,
  TradeResponse,
  AddLiquidityRequest,
  AddLiquidityResponse,
  RemoveLiquidityRequest,
  RemoveLiquidityResponse,
  CollectEarnedFeesRequest,
  PositionRequest,
  PositionResponse,
  PoolPriceRequest,
  PoolPriceResponse,
} from './amm.requests';
import {
  price as uniswapPrice,
  trade as uniswapTrade,
  addLiquidity as uniswapV3AddLiquidity,
  removeLiquidity as uniswapV3RemoveLiquidity,
  collectEarnedFees as uniswapV3CollectEarnedFees,
  positionInfo as uniswapV3PositionInfo,
  poolPrice as uniswapV3PoolPrice,
  estimateGas as uniswapEstimateGas,
} from '../connectors/uniswap/uniswap.controllers';
import { getChain, getConnector } from '../services/connection-manager';
import {
  NetworkSelectionRequest,
  Uniswapish,
  UniswapLPish,
} from '../services/common-interfaces';

export async function price(req: PriceRequest): Promise<PriceResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector: Uniswapish = <Uniswapish>(
    await getConnector(req.chain, req.network, req.connector)
  );
  return uniswapPrice(chain, connector, req);
}

export async function trade(req: TradeRequest): Promise<TradeResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector: Uniswapish = <Uniswapish>(
    await getConnector(req.chain, req.network, req.connector)
  );
  return uniswapTrade(chain, connector, req);
}

export async function addLiquidity(
  req: AddLiquidityRequest
): Promise<AddLiquidityResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector: UniswapLPish = <UniswapLPish>(
    await getConnector(req.chain, req.network, req.connector)
  );
  return uniswapV3AddLiquidity(chain, connector, req);
}

export async function reduceLiquidity(
  req: RemoveLiquidityRequest
): Promise<RemoveLiquidityResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector: UniswapLPish = <UniswapLPish>(
    await getConnector(req.chain, req.network, req.connector)
  );
  return uniswapV3RemoveLiquidity(chain, connector, req);
}

export async function collectFees(
  req: CollectEarnedFeesRequest
): Promise<RemoveLiquidityResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector: UniswapLPish = <UniswapLPish>(
    await getConnector(req.chain, req.network, req.connector)
  );
  return uniswapV3CollectEarnedFees(chain, connector, req);
}

export async function positionInfo(
  req: PositionRequest
): Promise<PositionResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector: UniswapLPish = <UniswapLPish>(
    await getConnector(req.chain, req.network, req.connector)
  );
  return uniswapV3PositionInfo(chain, connector, req);
}

export async function poolPrice(
  req: PoolPriceRequest
): Promise<PoolPriceResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector: UniswapLPish = <UniswapLPish>(
    await getConnector(req.chain, req.network, req.connector)
  );
  return uniswapV3PoolPrice(chain, connector, req);
}

export async function estimateGas(
  req: NetworkSelectionRequest
): Promise<EstimateGasResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector: Uniswapish = <Uniswapish>(
    await getConnector(req.chain, req.network, req.connector)
  );
  return uniswapEstimateGas(chain, connector);
}
