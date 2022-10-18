import {
  EstimateGasResponse,
  PerpAvailablePairsResponse,
  PerpCreateTakerRequest,
  PerpCreateTakerResponse,
  PerpMarketRequest,
  PerpMarketResponse,
  PerpPositionRequest,
  PerpPositionResponse,
  PerpPricesResponse,
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
  PerpBalanceRequest,
  PerpBalanceResponse,
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
import {
  estimateGas as curveEstimateGas,
  price as curvePrice,
  trade as curveTrade,
} from '../connectors/curve/curve.controllers';
import {
  getPriceData as perpPriceData,
  createTakerOrder,
  estimateGas as perpEstimateGas,
  getPosition,
  getAvailablePairs,
  checkMarketStatus,
  getAccountValue,
} from '../connectors/perp/perp.controllers';
import { getChain, getConnector } from '../services/connection-manager';
import {
  ConnectorType,
  Ethereumish,
  NetworkSelectionRequest,
  Perpish,
} from '../services/common-interfaces';

export async function price(req: PriceRequest): Promise<PriceResponse> {
  const chain = await getChain<Ethereumish>(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);

  if (connector.connectorType === ConnectorType.Uniswapish) {
    return uniswapPrice(chain, connector as any, req);
  } else if (connector.connectorType === ConnectorType.Curvish) {
    return curvePrice(chain, connector as any, req);
  } else {
    throw new Error('Unsupported connector');
  }
}

export async function trade(req: TradeRequest): Promise<TradeResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);
  if (connector.connectorType === ConnectorType.Uniswapish) {
    return uniswapTrade(chain, connector as any, req);
  } else if (connector.connectorType === ConnectorType.Curvish) {
    return curveTrade(chain, connector as any, req);
  } else {
    throw new Error('Unsupported connector');
  }
}

export async function addLiquidity(
  req: AddLiquidityRequest
): Promise<AddLiquidityResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);
  if (connector.connectorType === ConnectorType.UniswapLPish) {
    return uniswapV3AddLiquidity(chain, connector as any, req);
  } else {
    throw new Error('Unsupported connector');
  }
}

export async function reduceLiquidity(
  req: RemoveLiquidityRequest
): Promise<RemoveLiquidityResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);

  if (connector.connectorType === ConnectorType.UniswapLPish) {
    return uniswapV3RemoveLiquidity(chain, connector as any, req);
  } else {
    throw new Error('Unsupported connector');
  }
}

export async function collectFees(
  req: CollectEarnedFeesRequest
): Promise<RemoveLiquidityResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);
  if (connector.connectorType === ConnectorType.UniswapLPish) {
    return uniswapV3CollectEarnedFees(chain, connector as any, req);
  } else {
    throw new Error('Unsupported connector');
  }
}

export async function positionInfo(
  req: PositionRequest
): Promise<PositionResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);
  if (connector.connectorType === ConnectorType.UniswapLPish) {
    return uniswapV3PositionInfo(chain, connector as any, req);
  } else {
    throw new Error('Unsupported connector');
  }
}

export async function poolPrice(
  req: PoolPriceRequest
): Promise<PoolPriceResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);
  if (connector.connectorType === ConnectorType.UniswapLPish) {
    return uniswapV3PoolPrice(chain, connector as any, req);
  } else {
    throw new Error('Unsupported connector');
  }
}

export async function estimateGas(
  req: NetworkSelectionRequest
): Promise<EstimateGasResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);
  if (connector.connectorType === ConnectorType.Uniswapish) {
    return uniswapEstimateGas(chain, connector as any);
  } else if (connector.connectorType === ConnectorType.Curvish) {
    return curveEstimateGas(chain, connector as any);
  } else {
    throw new Error('Unknown connector');
  }
}

// perp
export async function perpMarketPrices(
  req: PriceRequest
): Promise<PerpPricesResponse> {
  const chain = await getChain<Ethereumish>(req.chain, req.network);
  const connector: Perpish = await getConnector<Perpish>(
    req.chain,
    req.network,
    req.connector
  );
  return perpPriceData(chain, connector, req);
}

export async function perpOrder(
  req: PerpCreateTakerRequest,
  isOpen: boolean
): Promise<PerpCreateTakerResponse> {
  const chain = await getChain<Ethereumish>(req.chain, req.network);
  const connector: Perpish = await getConnector<Perpish>(
    req.chain,
    req.network,
    req.connector,
    req.address
  );
  return createTakerOrder(chain, connector, req, isOpen);
}

export async function perpPosition(
  req: PerpPositionRequest
): Promise<PerpPositionResponse> {
  const chain = await getChain<Ethereumish>(req.chain, req.network);
  const connector: Perpish = await getConnector<Perpish>(
    req.chain,
    req.network,
    req.connector,
    req.address
  );
  return getPosition(chain, connector, req);
}

export async function perpBalance(
  req: PerpBalanceRequest
): Promise<PerpBalanceResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector: Perpish = await getConnector<Perpish>(
    req.chain,
    req.network,
    req.connector,
    req.address
  );
  return getAccountValue(chain, connector);
}

export async function perpPairs(
  req: NetworkSelectionRequest
): Promise<PerpAvailablePairsResponse> {
  const chain = await getChain<Ethereumish>(req.chain, req.network);
  const connector: Perpish = await getConnector<Perpish>(
    req.chain,
    req.network,
    req.connector
  );
  return getAvailablePairs(chain, connector);
}

export async function getMarketStatus(
  req: PerpMarketRequest
): Promise<PerpMarketResponse> {
  const chain = await getChain<Ethereumish>(req.chain, req.network);
  const connector: Perpish = await getConnector<Perpish>(
    req.chain,
    req.network,
    req.connector
  );
  return checkMarketStatus(chain, connector, req);
}

export async function estimatePerpGas(
  req: NetworkSelectionRequest
): Promise<EstimateGasResponse> {
  const chain = await getChain<Ethereumish>(req.chain, req.network);
  const connector: Perpish = await getConnector<Perpish>(
    req.chain,
    req.network,
    req.connector
  );
  return perpEstimateGas(chain, connector);
}
