import { StatusCodes } from 'http-status-codes';
import { Solanaish } from '../../chains/solana/solana';
import { Serumish } from './serum';
import {
  SerumDeleteOpenOrdersRequest,
  SerumDeleteOpenOrdersResponse,
  SerumDeleteOrdersRequest,
  SerumDeleteOrdersResponse,
  SerumGetFilledOrdersRequest,
  SerumGetFilledOrdersResponse,
  SerumGetMarketsRequest,
  SerumGetMarketsResponse,
  SerumGetOpenOrdersRequest,
  SerumGetOpenOrdersResponse,
  SerumGetOrderBooksRequest,
  SerumGetOrderBooksResponse,
  SerumGetOrdersResponse,
  SerumGetTickersRequest,
  SerumGetTickersResponse,
  SerumPostOrdersRequest,
  SerumPostOrdersResponse,
} from './serum.requests';
import { Market } from './serum.types';

/**
 * Get the all or the informed markets and their configurations.
 *
 * @param _solana
 * @param serum
 * @param request
 */
export async function getMarkets(
  _solana: Solanaish,
  serum: Serumish,
  request: SerumGetMarketsRequest
): Promise<SerumGetMarketsResponse> {
  const response = new SerumGetMarketsResponse();

  if ('name' in request) {
    response.body = await serum.getMarket(request.name);

    if (!response.body) {
      response.status = StatusCodes.NOT_FOUND;
      response.title = `Market Not Found`;
      response.message = `Market "${request.name}" not found.`;

      return response;
    }

    response.status = StatusCodes.OK;
    response.title = `Market Found`;
    response.message = `Market ${request.name} found.`;

    return response;
  }

  if ('names' in request) {
    if (!request.names || !request.names.length) {
      response.status = StatusCodes.BAD_REQUEST;
      response.title = `No Markets Informed`;
      response.message = `No markets were informed. If you want to get all markets, please do not inform the parameter "names".`;

      return response;
    }

    response.body = await serum.getMarkets(request.names);

    if (!response.body || !response.body.length) {
      response.status = StatusCodes.NOT_FOUND;
      response.title = `Markets Not Found`;
      response.message = `Markets "${request.names.concat(', ')}" not found.`;

      return response;
    }

    if (response.body.values.count() != request.names.length) {
      const missing = [];
      for (const [key, value] of response.body as Map<
        string,
        Market[] | null
      >) {
        if (!value) missing.push(key);
      }

      response.status = StatusCodes.MULTI_STATUS;
      response.title = `Some Markets Not Found`;
      response.message = `Markets "${missing.concat(', ')}" were not found.`;

      return response;
    }

    response.status = StatusCodes.OK;
    response.title = `Markets Found`;
    response.message = `Markets ${request.names.concat(', ')} found.`;

    return response;
  }

  response.body = await serum.getAllMarkets();

  if (!response.body || !response.body.length) {
    response.status = StatusCodes.NOT_FOUND;
    response.title = `Markets Not Found`;
    response.message = `Markets not found.`;

    return response;
  }

  response.status = StatusCodes.OK;
  response.title = `Found All Markets`;
  response.message = `Found all markets.`;

  return response;
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
