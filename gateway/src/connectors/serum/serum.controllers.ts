import { Account, Connection, PublicKey } from '@solana/web3.js';
import { Market } from '@project-serum/serum';
import { Solanaish } from '../../chains/solana/solana';
import { Serumish } from './serum';
import {
  ClobDeleteOpenOrdersRequest,
  ClobDeleteOpenOrdersResponse,
  ClobDeleteOrdersRequest,
  ClobGetFilledOrdersRequest,
  ClobGetFilledOrdersResponse,
  ClobGetOpenOrdersRequest,
  ClobGetMarketsRequest,
  ClobGetMarketsResponse,
  ClobGetOrderBooksRequest,
  ClobGetOrderBooksResponse,
  ClobPostOrdersRequest,
  ClobGetTickersRequest,
  ClobGetTickersResponse,
  ClobGetOrdersResponse,
  ClobPostOrdersResponse,
  ClobDeleteOrdersResponse,
  ClobGetOpenOrdersResponse,
} from '../../clob/clob.requests';

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
  request: ClobGetMarketsRequest
): Promise<ClobGetMarketsResponse> {
  // TODO return all, if undefined!!!

  return {} as ClobGetMarketsResponse;
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
  request: ClobGetOrderBooksRequest
): Promise<ClobGetOrderBooksResponse> {
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
  request: ClobGetTickersRequest
): Promise<ClobGetTickersResponse> {
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
  request: ClobGetOrdersRequest
): Promise<ClobGetOrdersResponse> {
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
  request: ClobPostOrdersRequest
): Promise<ClobPostOrdersResponse> {
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
  request: ClobDeleteOrdersRequest
): Promise<ClobDeleteOrdersResponse> {
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
  request: ClobGetOpenOrdersRequest
): Promise<ClobGetOpenOrdersResponse> {
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
  request: ClobDeleteOpenOrdersRequest
): Promise<ClobDeleteOpenOrdersResponse> {
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
  request: ClobGetFilledOrdersRequest
): Promise<ClobGetFilledOrdersResponse> {
}
