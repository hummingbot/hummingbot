import {
  ClobDeleteOpenOrdersRequest,
  ClobDeleteOrdersRequest,
  ClobGetFilledOrdersRequest,
  ClobGetFilledOrdersResponse,
  ClobGetOpenOrdersRequest,
  ClobGetOrdersRequest,
  ClobGetMarketsRequest,
  ClobGetMarketsResponse,
  ClobGetOrderBooksRequest,
  ClobGetOrderBooksResponse,
  ClobOrdersResponse,
  ClobPostOrdersRequest,
  ClobGetTickersRequest,
  ClobGetTickersResponse,
  ClobGetOpenOrdersResponse,
  ClobDeleteOpenOrdersResponse,
} from './clob.requests';
import { getChain, getConnector } from '../services/connection-manager';
import * as serumControllers from '../connectors/serum/serum.controllers';
import { Solanaish } from '../chains/solana/solana';
import { Serumish } from '../connectors/serum/serum';

/**
 * GET /clob/markets
 *
 * @param request
 */
export async function getMarkets(
  request: ClobGetMarketsRequest
): Promise<ClobGetMarketsResponse> {
  const chain: Solanaish = await getChain(request.chain, request.network);
  const connector: Serumish = await getConnector(
    request.chain,
    request.network,
    request.connector
  );

  return serumControllers.getMarkets(chain, connector, request);
}

/**
 * GET /clob/orderBooks
 *
 * @param request
 */
export async function getOrderBooks(
  request: ClobGetOrderBooksRequest
): Promise<ClobGetOrderBooksResponse> {
  const chain: Solanaish = await getChain(request.chain, request.network);
  const connector: Serumish = await getConnector(
    request.chain,
    request.network,
    request.connector
  );

  return serumControllers.getOrderBooks(chain, connector, request);
}

/**
 * GET /clob/tickers
 *
 * @param request
 */
export async function getTickers(
  request: ClobGetTickersRequest
): Promise<ClobGetTickersResponse> {
  const chain: Solanaish = await getChain(request.chain, request.network);
  const connector: Serumish = await getConnector(
    request.chain,
    request.network,
    request.connector
  );

  return serumControllers.getTickers(chain, connector, request);
}

/**
 * GET /clob/orders
 *
 * @param request
 */
export async function getOrders(
  request: ClobGetOrdersRequest
): Promise<ClobOrdersResponse> {
  const chain: Solanaish = await getChain(request.chain, request.network);
  const connector: Serumish = await getConnector(
    request.chain,
    request.network,
    request.connector
  );

  return serumControllers.getOrders(chain, connector, request);
}

/**
 * POST /clob/orders
 *
 * @param request
 */
export async function postOrders(
  request: ClobPostOrdersRequest
): Promise<ClobOrdersResponse> {
  const chain: Solanaish = await getChain(request.chain, request.network);
  const connector: Serumish = await getConnector(
    request.chain,
    request.network,
    request.connector
  );

  return serumControllers.postOrders(chain, connector, request);
}

/**
 * DELETE /clob/orders
 *
 * @param request
 */
export async function deleteOrders(
  request: ClobDeleteOrdersRequest
): Promise<ClobOrdersResponse> {
  const chain: Solanaish = await getChain(request.chain, request.network);
  const connector: Serumish = await getConnector(
    request.chain,
    request.network,
    request.connector
  );

  return serumControllers.deleteOrders(chain, connector, request);
}

/**
 * GET /clob/openOrders
 *
 * @param request
 */
export async function getOpenOrders(
  request: ClobGetOpenOrdersRequest
): Promise<ClobGetOpenOrdersResponse> {
  const chain: Solanaish = await getChain(request.chain, request.network);
  const connector: Serumish = await getConnector(
    request.chain,
    request.network,
    request.connector
  );

  return serumControllers.getOpenOrders(chain, connector, request);
}

/**
 * DELETE /clob/openOrders
 *
 * @param request
 */
export async function deleteOpenOrders(
  request: ClobDeleteOpenOrdersRequest
): Promise<ClobDeleteOpenOrdersResponse> {
  const chain: Solanaish = await getChain(request.chain, request.network);
  const connector: Serumish = await getConnector(
    request.chain,
    request.network,
    request.connector
  );

  return serumControllers.deleteOpenOrders(chain, connector, request);
}

/**
 * GET /clob/filledOrders
 *
 * @param request
 */
export async function getFilledOrders(
  request: ClobGetFilledOrdersRequest
): Promise<ClobGetFilledOrdersResponse> {
  const chain: Solanaish = await getChain(request.chain, request.network);
  const connector: Serumish = await getConnector(
    request.chain,
    request.network,
    request.connector
  );

  return serumControllers.getFilledOrders(chain, connector, request);
}
