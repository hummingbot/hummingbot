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
import { Curve } from '../connectors/curve/curve';
import {
  estimateGas as curveEstimateGas,
  price as curvePrice,
  trade as curveTrade,
} from '../connectors/curve/curve.controllers';
import { getChain, getConnector } from '../services/connection-manager';
import {
  NetworkSelectionRequest,
  Uniswapish,
  UniswapLPish,
} from '../services/common-interfaces';

export async function price(req: PriceRequest): Promise<PriceResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);
  if (
    (<any>connector).types === 'Uniswap' ||
    (<any>connector).types === 'Pangolin'
  ) {
    return uniswapPrice(chain, <Uniswapish>connector, req);
  } else if ((<any>connector).types === 'Curve') {
    return curvePrice(chain, <Curve>connector, req);
  } else {
    throw new Error('Unsupported connector');
  }
}

export async function trade(req: TradeRequest): Promise<TradeResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);
  if (
    (<any>connector).types === 'Uniswap' ||
    (<any>connector).types === 'Pangolin'
  ) {
    return uniswapTrade(chain, <Uniswapish>connector, req);
  } else if ((<any>connector).types === 'Curve') {
    return curveTrade(chain, <Curve>connector, req);
  } else {
    throw new Error('Unsupported connector');
  }
}

export async function addLiquidity(
  req: AddLiquidityRequest
): Promise<AddLiquidityResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);
  if ((<any>connector).types === 'UniswapLP') {
    return uniswapV3AddLiquidity(chain, <UniswapLPish>connector, req);
  } else {
    throw new Error('Unsupported connector');
  }
}

export async function reduceLiquidity(
  req: RemoveLiquidityRequest
): Promise<RemoveLiquidityResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);

  if ((<any>connector).types === 'UniswapLP') {
    return uniswapV3RemoveLiquidity(chain, <UniswapLPish>connector, req);
  } else {
    throw new Error('Unsupported connector');
  }
}

export async function collectFees(
  req: CollectEarnedFeesRequest
): Promise<RemoveLiquidityResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);
  if ((<any>connector).types === 'UniswapLP') {
    return uniswapV3CollectEarnedFees(chain, <UniswapLPish>connector, req);
  } else {
    throw new Error('Unsupported connector');
  }
}

export async function positionInfo(
  req: PositionRequest
): Promise<PositionResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);
  if ((<any>connector).types === 'UniswapLP') {
    return uniswapV3PositionInfo(chain, <UniswapLPish>connector, req);
  } else {
    throw new Error('Unsupported connector');
  }
}

export async function poolPrice(
  req: PoolPriceRequest
): Promise<PoolPriceResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);
  if ((<any>connector).types === 'UniswapLP') {
    return uniswapV3PoolPrice(chain, <UniswapLPish>connector, req);
  } else {
    throw new Error('Unsupported connector');
  }
}

export async function estimateGas(
  req: NetworkSelectionRequest
): Promise<EstimateGasResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);
  if (
    (<any>connector).types === 'Uniswap' ||
    (<any>connector).types === 'Pangolin'
  ) {
    return uniswapEstimateGas(chain, <Uniswapish>connector);
  } else if ((<any>connector).types === 'Curve') {
    return curveEstimateGas(chain, <Curve>connector);
  } else {
    throw new Error('Unknown connector');
  }
}
