import {
  EstimateGasResponse,
  PriceRequest,
  PriceResponse,
  TradeRequest,
  TradeResponse,
} from './amm.requests';
import {
  price as uniswapPrice,
  trade as uniswapTrade,
  estimateGas as uniswapEstimateGas,
} from '../connectors/uniswap/uniswap.controllers';
import { Curve } from '../connectors/curve/curve';
import { Uniswapish } from '../services/common-interfaces';
import {
  price as curvePrice,
  trade as curveTrade,
} from '../connectors/curve/curve.controllers';
import { getChain, getConnector } from '../services/connection-manager';
import { NetworkSelectionRequest } from '../services/common-interfaces';

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
    throw new Error('');
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
    throw new Error('');
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
  } else {
    throw new Error('');
  }
}
