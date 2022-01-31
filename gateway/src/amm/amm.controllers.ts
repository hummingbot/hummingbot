import {
  PriceRequest,
  PriceResponse,
  TradeRequest,
  TradeResponse,
} from './amm.requests';
import {
  price as uniswapPrice,
  trade as uniswapTrade,
} from '../connectors/uniswap/uniswap.controllers';
import { getChain, getConnector } from '../services/connection-manager';

export async function price(req: PriceRequest): Promise<PriceResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);
  return uniswapPrice(chain, connector, req);
}

export async function trade(req: TradeRequest): Promise<TradeResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);
  return uniswapTrade(chain, connector, req);
}
