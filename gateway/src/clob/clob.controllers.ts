import {ClobMarketsRequest} from "./clob.requests";
import {getChain, getConnector} from "../services/connection-manager";
import {markets} from "../connectors/serum/serum.controllers";

/** import {
  PriceRequest,
  PriceResponse,
  TradeRequest,
  TradeResponse,
} from './clob.requests';
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
**/

export async function markets(req: ClobMarketsRequest) {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);

  return markets(chain, connector, req);
}

export async function orderbook(body: any) {
  console.log(body);
  return body;
}

export async function getOrders(body: any) {
  console.log(body);
  return body;
}

export async function postOrder(body: any) {
  console.log(body);
  return body;
}

export async function deleteOrders(body: any) {
  console.log(body);
  return body;
}

export async function fills(body: any) {
  console.log(body);
  return body;
}
