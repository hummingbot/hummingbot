import { Solanaish } from '../chains/solana/solana';
import { Serumish } from '../connectors/serum/serum';
import * as serumControllers from '../connectors/serum/serum.controllers';
import { ResponseWrapper } from '../services/common-interfaces';
import { getChain, getConnector } from '../services/connection-manager';
import {
  ClobDeleteOrdersRequest,
  ClobDeleteOrdersResponse,
  ClobGetFilledOrdersRequest,
  ClobGetFilledOrdersResponse,
  ClobGetMarketsRequest,
  ClobGetMarketsResponse,
  ClobGetOpenOrdersRequest,
  ClobGetOpenOrdersResponse,
  ClobGetOrderBooksRequest,
  ClobGetOrderBooksResponse,
  ClobGetOrdersRequest,
  ClobGetOrdersResponse,
  ClobGetTickersRequest,
  ClobGetTickersResponse,
  ClobPostOrdersRequest,
  ClobPostOrdersResponse,
  ClobPostSettleFundsRequest,
  ClobPostSettleFundsResponse,
} from './clob.requests';

/**
 * GET /clob/markets
 *
 * @param request
 */
export async function getMarkets(
  request: ClobGetMarketsRequest
): Promise<ResponseWrapper<ClobGetMarketsResponse>> {
  const chain: Solanaish = await getChain<Solanaish>(
    request.chain,
    request.network
  );
  const connector: Serumish = await getConnector<Serumish>(
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
): Promise<ResponseWrapper<ClobGetOrderBooksResponse>> {
  const chain: Solanaish = await getChain<Solanaish>(
    request.chain,
    request.network
  );
  const connector: Serumish = await getConnector<Serumish>(
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
): Promise<ResponseWrapper<ClobGetTickersResponse>> {
  const chain: Solanaish = await getChain<Solanaish>(
    request.chain,
    request.network
  );
  const connector: Serumish = await getConnector<Serumish>(
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
): Promise<ResponseWrapper<ClobGetOrdersResponse>> {
  const chain: Solanaish = await getChain<Solanaish>(
    request.chain,
    request.network
  );
  const connector: Serumish = await getConnector<Serumish>(
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
export async function createOrders(
  request: ClobPostOrdersRequest
): Promise<ResponseWrapper<ClobPostOrdersResponse>> {
  const chain: Solanaish = await getChain<Solanaish>(
    request.chain,
    request.network
  );
  const connector: Serumish = await getConnector<Serumish>(
    request.chain,
    request.network,
    request.connector
  );

  return serumControllers.createOrders(chain, connector, request);
}

/**
 * DELETE /clob/orders
 *
 * @param request
 */
export async function cancelOrders(
  request: ClobDeleteOrdersRequest
): Promise<ResponseWrapper<ClobDeleteOrdersResponse>> {
  const chain: Solanaish = await getChain<Solanaish>(
    request.chain,
    request.network
  );
  const connector: Serumish = await getConnector<Serumish>(
    request.chain,
    request.network,
    request.connector
  );

  return serumControllers.cancelOrders(chain, connector, request);
}

/**
 * GET /clob/orders/open
 *
 * @param request
 */
export async function getOpenOrders(
  request: ClobGetOpenOrdersRequest
): Promise<ResponseWrapper<ClobGetOpenOrdersResponse>> {
  const chain: Solanaish = await getChain<Solanaish>(
    request.chain,
    request.network
  );
  const connector: Serumish = await getConnector<Serumish>(
    request.chain,
    request.network,
    request.connector
  );

  return serumControllers.getOpenOrders(chain, connector, request);
}

/**
 * GET /clob/orders/filled
 *
 * @param request
 */
export async function getFilledOrders(
  request: ClobGetFilledOrdersRequest
): Promise<ResponseWrapper<ClobGetFilledOrdersResponse>> {
  const chain: Solanaish = await getChain<Solanaish>(
    request.chain,
    request.network
  );
  const connector: Serumish = await getConnector<Serumish>(
    request.chain,
    request.network,
    request.connector
  );

  return serumControllers.getFilledOrders(chain, connector, request);
}

/**
 * Settle funds for one or more markets.
 *
 * POST /clob/settleFunds
 *
 * @param request
 */
export async function settleFunds(
  request: ClobPostSettleFundsRequest
): Promise<ResponseWrapper<ClobPostSettleFundsResponse>> {
  const chain: Solanaish = await getChain<Solanaish>(
    request.chain,
    request.network
  );
  const connector: Serumish = await getConnector<Serumish>(
    request.chain,
    request.network,
    request.connector
  );

  return serumControllers.settleFunds(chain, connector, request);
}
