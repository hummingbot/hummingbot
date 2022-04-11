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
  SerumGetOrdersRequest,
  SerumGetOrdersResponse,
  SerumGetTickersRequest,
  SerumGetTickersResponse,
  SerumPostOrdersRequest,
  SerumPostOrdersResponse,
} from './serum.requests';
import { ResponseWrapper } from '../../services/common-interfaces';
import { HttpException } from '../../services/error-handler';
import { MarketNotFoundError } from "./serum.types";

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
): Promise<ResponseWrapper<SerumGetMarketsResponse>> {
  const response = new ResponseWrapper<SerumGetMarketsResponse>();

  if ('name' in request) {
    try {
      response.body = await serum.getMarket(request.name);

      response.status = StatusCodes.OK;

      return response;
    } catch (exception) {
      if (exception instanceof MarketNotFoundError) {
        throw new HttpException(
          StatusCodes.NOT_FOUND,
          exception.message
          // TODO should we create new error codes?!!!
        );
      } else {
        throw exception; // TODO Ask Mike! Should we throw an HttpException here? or would it be ok to throw the original exception?!!!
      }
    }
  }

  if ('names' in request) {
    if (!request.names || !request.names.length) {
      throw new HttpException(
        StatusCodes.BAD_REQUEST,
        `No markets were informed. If you want to get all markets, please do not inform the parameter "names".`
      );
    }

    try {
      response.body = await serum.getMarkets(request.names);

      response.status = StatusCodes.OK;

      return response;
    } catch (exception: any) {
      if (exception instanceof MarketNotFoundError) {
        throw new HttpException(StatusCodes.NOT_FOUND, exception.message);
      } else {
        throw exception;
      }
    }
  }

  response.body = await serum.getAllMarkets();

  if (!response.body || !response.body.size) {
    throw new HttpException(StatusCodes.NOT_FOUND, `No market was found.`);
  }

  response.status = StatusCodes.OK;

  return response;
}

/**
 * Get the current orderbook for each informed market.
 *
 * @param _solana
 * @param serum
 * @param request
 */
export async function getOrderBooks(
  _solana: Solanaish,
  serum: Serumish,
  request: SerumGetOrderBooksRequest
): Promise<ResponseWrapper<SerumGetOrderBooksResponse>> {
  const response = new ResponseWrapper<SerumGetOrderBooksResponse>();

  if ('marketName' in request) {
    response.body = await serum.getOrderBook(request.marketName);

    if (!response.body) {
      throw new HttpException(
        StatusCodes.NOT_FOUND,
        `Order book for market ${request.marketName} was not found.`
      );
    }

    response.status = StatusCodes.OK;

    return response;
  }

  if ('marketNames' in request) {
    if (!request.marketNames || !request.marketNames.length) {
      throw new HttpException(
        StatusCodes.BAD_REQUEST,
        `No markets were informed. If you want to get all order books, please do not inform the parameter "marketNames".`
      );
    }

    response.body = await serum.getOrderBooks(request.marketNames);

    if (!response.body || !response.body.size) {
      throw new HttpException(
        StatusCodes.NOT_FOUND,
        `Order books for markets "${request.marketNames.concat(
          ', '
        )}" were not found.`
      );
    }

    const values = Array.from(response.body.values());
    if (values.length != request.marketNames.length) {
      const missing = [];
      for (const [key, value] of response.body) {
        if (!value) missing.push(key);
      }

      throw new HttpException(
        StatusCodes.NOT_FOUND,
        `Order books for markets "${missing.concat(', ')}" were not found.`
      );
    }

    response.status = StatusCodes.OK;

    return response;
  }

  response.body = await serum.getAllOrderBooks();

  if (!response.body || !response.body.size) {
    throw new HttpException(StatusCodes.NOT_FOUND, `No order book was found.`);
  }

  response.status = StatusCodes.OK;

  return response;
}

/**
 * Get the last traded prices for each informed market.
 *
 * @param _solana
 * @param serum
 * @param request
 */
export async function getTickers(
  _solana: Solanaish,
  serum: Serumish,
  request: SerumGetTickersRequest
): Promise<ResponseWrapper<SerumGetTickersResponse>> {
  const response = new ResponseWrapper<SerumGetTickersResponse>();

  if ('marketName' in request) {
    response.body = await serum.getTicker(request.marketName);

    if (!response.body) {
      throw new HttpException(
        StatusCodes.NOT_FOUND,
        `Ticker for market ${request.marketName} was not found.`
      );
    }

    response.status = StatusCodes.OK;

    return response;
  }

  if ('marketNames' in request) {
    if (!request.marketNames || !request.marketNames.length) {
      throw new HttpException(
        StatusCodes.BAD_REQUEST,
        `No markets were informed. If you want to get all tickers, please do not inform the parameter "marketNames".`
      );
    }

    response.body = await serum.getTickers(request.marketNames);

    if (!response.body || !response.body.size) {
      throw new HttpException(
        StatusCodes.NOT_FOUND,
        `Tickers for markets "${request.marketNames.concat(
          ', '
        )}" were not found.`
      );
    }

    const values = Array.from(response.body.values());
    if (values.length != request.marketNames.length) {
      const missing = [];
      for (const [key, value] of response.body) {
        if (!value) missing.push(key);
      }

      throw new HttpException(
        StatusCodes.NOT_FOUND,
        `Tickers for markets "${missing.concat(', ')}" were not found.`
      );
    }

    response.status = StatusCodes.OK;

    return response;
  }

  response.body = await serum.getAllTickers();

  if (!response.body || !response.body.size) {
    throw new HttpException(StatusCodes.NOT_FOUND, `No order book was found.`);
  }

  response.status = StatusCodes.OK;

  return response;
}

/**
 * Get one or more orders.
 *
 * @param _solana
 * @param serum
 * @param request
 */
export async function getOrders(
  _solana: Solanaish,
  serum: Serumish,
  request: SerumGetOrdersRequest
): Promise<ResponseWrapper<SerumGetOrdersResponse>> {
  const response = new ResponseWrapper<SerumGetOrdersResponse>();

  if ('order' in request) {
    response.body = await serum.getOrder(request.order);

    if (!response.body) {
      throw new HttpException(
        StatusCodes.NOT_FOUND,
        `Order "${request.order.clientOrderId}" was not found.`
      );
    }

    response.status = StatusCodes.OK;

    return response;
  }

  if ('orders' in request) {

  }

  return response;
}

/**
 * Create one or more orders.
 *
 * @param _solana
 * @param serum
 * @param request
 */
export async function createOrders(
  _solana: Solanaish,
  serum: Serumish,
  request: SerumPostOrdersRequest
): Promise<ResponseWrapper<SerumPostOrdersResponse>> {
}

/**
 * Cancel one or more orders.
 *
 * @param _solana
 * @param serum
 * @param request
 */
export async function cancelOrders(
  _solana: Solanaish,
  serum: Serumish,
  request: SerumDeleteOrdersRequest
): Promise<ResponseWrapper<SerumDeleteOrdersResponse>> {
}

/**
 * Get all open orders for each informed market.
 *
 * @param _solana
 * @param serum
 * @param request
 */
export async function getOpenOrders(
  _solana: Solanaish,
  serum: Serumish,
  request: SerumGetOpenOrdersRequest
): Promise<ResponseWrapper<SerumGetOpenOrdersResponse>> {
}

/**
 * Cancel all open orders for each informed market.
 *
 * @param _solana
 * @param serum
 * @param request
 */
export async function deleteOpenOrders(
  _solana: Solanaish,
  serum: Serumish,
  request: SerumDeleteOpenOrdersRequest
): Promise<ResponseWrapper<SerumDeleteOpenOrdersResponse>> {
}

/**
 * Get one or more filled orders.
 *
 * @param _solana
 * @param serum
 * @param request
 */
export async function getFilledOrders(
  _solana: Solanaish,
  serum: Serumish,
  request: SerumGetFilledOrdersRequest
): Promise<ResponseWrapper<SerumGetFilledOrdersResponse>> {
}
