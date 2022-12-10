import { StatusCodes } from 'http-status-codes';
import { Rippleish } from '../../chains/ripple/ripple';
import { ResponseWrapper } from '../../services/common-interfaces';
import { HttpException } from '../../services/error-handler';
import { RippleDEXish } from './rippledex';
import {
  RippleGetMarketsRequest,
  RippleGetMarketsResponse,
  RippleGetOrderBooksRequest,
  RippleGetOrderBooksResponse,
  RippleGetTickersRequest,
  RippleGetTickersResponse,
} from './rippledex.requests';

import {
  validateGetMarketRequest,
  validateGetMarketsRequest,
  validateGetTickerRequest,
  validateGetTickersRequest,
  validateGetOrderBookRequest,
  validateGetOrderBooksRequest,
} from './rippledex.validators';

import { MarketNotFoundError } from './rippledex.types';

/**
 * Get the mid price of a token pair
 *
 * @param _ripple
 * @param rippledex
 * @param request
 */
export async function getMarkets(
  _ripple: Rippleish,
  rippledex: RippleDEXish,
  request: RippleGetMarketsRequest
): Promise<ResponseWrapper<RippleGetMarketsResponse>> {
  const response = new ResponseWrapper<RippleGetMarketsResponse>();

  if ('name' in request) {
    validateGetMarketRequest(request);

    try {
      response.body = await rippledex.getMarket(request.name);
      response.status = StatusCodes.OK;

      return response;
    } catch (exception) {
      if (exception instanceof MarketNotFoundError) {
        throw new HttpException(StatusCodes.NOT_FOUND, exception.message);
      } else {
        throw exception;
      }
    }
  }

  if ('names' in request) {
    validateGetMarketsRequest(request);

    try {
      response.body = await rippledex.getMarkets(request.names);

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

  throw new HttpException(StatusCodes.NOT_FOUND, 'No market specified.');
}

/**
 * Get the mid price of a token pair
 *
 * @param _ripple
 * @param rippledex
 * @param request
 */
export async function getTickers(
  _ripple: Rippleish,
  rippledex: RippleDEXish,
  request: RippleGetTickersRequest
): Promise<ResponseWrapper<RippleGetTickersResponse>> {
  const response = new ResponseWrapper<RippleGetTickersResponse>();

  if ('marketName' in request) {
    validateGetTickerRequest(request);

    try {
      response.body = await rippledex.getTicker(request.marketName);
      response.status = StatusCodes.OK;

      return response;
    } catch (exception) {
      if (exception instanceof MarketNotFoundError) {
        throw new HttpException(StatusCodes.NOT_FOUND, exception.message);
      } else {
        throw exception;
      }
    }
  }

  if ('marketNames' in request) {
    validateGetTickersRequest(request);

    try {
      response.body = await rippledex.getTickers(request.marketNames);

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

  throw new HttpException(StatusCodes.NOT_FOUND, 'No market specified.');
}

/**
 * Get the order book of a token pair
 *
 * @param _ripple
 * @param rippledex
 * @param request
 */
export async function getOrderBooks(
  _ripple: Rippleish,
  rippledex: RippleDEXish,
  request: RippleGetOrderBooksRequest
): Promise<ResponseWrapper<RippleGetOrderBooksResponse>> {
  const response = new ResponseWrapper<RippleGetOrderBooksResponse>();

  if ('marketName' in request) {
    validateGetOrderBookRequest(request);

    try {
      response.body = await rippledex.getOrderBook(
        request.marketName,
        request.limit
      );
      response.status = StatusCodes.OK;

      return response;
    } catch (exception) {
      if (exception instanceof MarketNotFoundError) {
        throw new HttpException(StatusCodes.NOT_FOUND, exception.message);
      } else {
        throw exception;
      }
    }
  }

  if ('marketNames' in request) {
    validateGetOrderBooksRequest(request);

    try {
      response.body = await rippledex.getOrderBooks(
        request.marketNames,
        request.limit
      );

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

  throw new HttpException(StatusCodes.NOT_FOUND, 'No market specified.');
}

/**
 * Get the detail on the created order
 *
 * @param _ripple
 * @param rippledex
 * @param request
 */
export async function getOrders(
  _ripple: Rippleish,
  rippledex: RippleDEXish,
  request: any
): Promise<ResponseWrapper<any>> {
  const response = new ResponseWrapper<any>();

  response.body = await rippledex.getOrders(request.tx);

  response.status = StatusCodes.OK;

  return response;
}

/**
 * Create an order on order book
 *
 * @param _ripple
 * @param rippledex
 * @param request
 */
export async function createOrders(
  _ripple: Rippleish,
  rippledex: RippleDEXish,
  request: any
): Promise<ResponseWrapper<any>> {
  const response = new ResponseWrapper<any>();

  response.body = await rippledex.createOrders(
    request.address,
    request.base,
    request.quote,
    request.side,
    request.price,
    request.amount
  );

  response.status = StatusCodes.OK;

  return response;
}

/**
 * Cancel an order on order book
 *
 * @param _ripple
 * @param rippledex
 * @param request
 */
export async function cancelOrders(
  _ripple: Rippleish,
  rippledex: RippleDEXish,
  request: any
): Promise<ResponseWrapper<any>> {
  const response = new ResponseWrapper<any>();

  response.body = await rippledex.cancelOrders(
    request.address,
    request.offerSequence
  );

  response.status = StatusCodes.OK;

  return response;
}

/**
 * Get the order book of a token pair
 *
 * @param _ripple
 * @param rippledex
 * @param request
 */
export async function getOpenOrders(
  _ripple: Rippleish,
  rippledex: RippleDEXish,
  request: any
): Promise<ResponseWrapper<any>> {
  const response = new ResponseWrapper<any>();

  response.body = await rippledex.getOpenOrders(request.address);

  response.status = StatusCodes.OK;

  return response;
}
