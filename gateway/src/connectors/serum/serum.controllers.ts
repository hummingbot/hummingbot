import { Account, Connection, PublicKey } from '@solana/web3.js';
import { Market } from '@project-serum/serum';
import { Solanaish } from '../../chains/solana/solana';
import { Serumish } from './serum';
import {
  SerumDeleteOpenOrdersRequest,
  SerumDeleteOpenOrdersResponse,
  SerumDeleteOrdersRequest,
  SerumGetFilledOrdersRequest,
  SerumGetFilledOrdersResponse,
  SerumGetOpenOrdersRequest,
  SerumGetMarketsRequest,
  SerumGetMarketsResponse,
  SerumGetOrderBooksRequest,
  SerumGetOrderBooksResponse,
  SerumPostOrdersRequest,
  SerumGetTickersRequest,
  SerumGetTickersResponse,
  SerumGetOrdersResponse,
  SerumPostOrdersResponse,
  SerumDeleteOrdersResponse,
  SerumGetOpenOrdersResponse,
} from './serum.requests';

/**
 * Get the all or the informed markets and their configurations.
 *
 * @param solana
 * @param serum
 * @param request
 */
export async function getMarkets(
  solana: Solanaish,
  serum: Serumish,
  request: SerumGetMarketsRequest
): Promise<SerumGetMarketsResponse> {
  if ('name' in request) await serum.getMarket(request.name);
  else if ('names' in request) await serum.getMarkets(request.names);
  else await serum.getAllMarkets();

  return {} as SerumGetMarketsResponse;
}

/**
 * Get the current orderbook for each informed market.
 *
 * @param solana
 * @param serum
 * @param request
 */
export async function getOrderBooks(
  solana: Solanaish,
  serum: Serumish,
  request: SerumGetOrderBooksRequest
): Promise<SerumGetOrderBooksResponse> {
  // TODO return all, if undefined!!!
}

/**
 * Get the last traded prices for each informed market.
 *
 * @param solana
 * @param serum
 * @param request
 */
export async function getTickers(
  solana: Solanaish,
  serum: Serumish,
  request: SerumGetTickersRequest
): Promise<SerumGetTickersResponse> {
 // TODO return all, if undefined!!!
}

/**
 * Get one or more orders.
 *
 * @param solana
 * @param serum
 * @param request
 */
export async function getOrders(
  solana: Solanaish,
  serum: Serumish,
  request: SerumGetOrdersRequest
): Promise<SerumGetOrdersResponse> {
}

/**
 * Create one or more orders.
 *
 * @param solana
 * @param serum
 * @param request
 */
export async function postOrders(
  solana: Solanaish,
  serum: Serumish,
  request: SerumPostOrdersRequest
): Promise<SerumPostOrdersResponse> {
}

/**
 * Cancel one or more orders.
 *
 * @param solana
 * @param serum
 * @param request
 */
export async function deleteOrders(
  solana: Solanaish,
  serum: Serumish,
  request: SerumDeleteOrdersRequest
): Promise<SerumDeleteOrdersResponse> {
}

/**
 * Get all open orders for each informed market.
 *
 * @param solana
 * @param serum
 * @param request
 */
export async function getOpenOrders(
  solana: Solanaish,
  serum: Serumish,
  request: SerumGetOpenOrdersRequest
): Promise<SerumGetOpenOrdersResponse> {
}

/**
 * Cancel all open orders for each informed market.
 *
 * @param solana
 * @param serum
 * @param request
 */
export async function deleteOpenOrders(
  solana: Solanaish,
  serum: Serumish,
  request: SerumDeleteOpenOrdersRequest
): Promise<SerumDeleteOpenOrdersResponse> {
}

/**
 * Get filled orders.
 *
 * @param solana
 * @param serum
 * @param request
 */
export async function getFilledOrders(
  solana: Solanaish,
  serum: Serumish,
  request: SerumGetFilledOrdersRequest
): Promise<SerumGetFilledOrdersResponse> {
}
