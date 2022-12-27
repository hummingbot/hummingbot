import { StatusCodes } from 'http-status-codes';
import { Rippleish } from '../../chains/ripple/ripple';
import { ResponseWrapper } from '../../services/common-interfaces';
import { HttpException } from '../../services/error-handler';
import { RippleDEXish } from './rippledex';
import {
  RippleCancelOrdersRequest,
  RippleCancelOrdersResponse,
  RippleCreateOrdersRequest,
  RippleCreateOrdersResponse,
  RippleGetMarketsRequest,
  RippleGetMarketsResponse,
  RippleGetOpenOrdersRequest,
  RippleGetOpenOrdersResponse,
  RippleGetOrderBooksRequest,
  RippleGetOrderBooksResponse,
  RippleGetTickersRequest,
  RippleGetTickersResponse,
  RippleGetOrdersRequest,
  RippleGetOrdersResponse,
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
  request: RippleGetOrdersRequest
): Promise<ResponseWrapper<RippleGetOrdersResponse>> {
  const response = new ResponseWrapper<any>();

  response.body = await rippledex.getOrders(request.orders);

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
  request: RippleCreateOrdersRequest
): Promise<ResponseWrapper<RippleCreateOrdersResponse>> {
  const response = new ResponseWrapper<RippleCreateOrdersResponse>();

  if ('order' in request) {
    // validateCreateOrderRequest(request.order); TODO: add createOrder validator

    response.body = await rippledex.createOrders(
      [request.order],
      request.waitUntilIncludedInBlock
    );

    response.status = StatusCodes.OK;

    return response;
  }

  if ('orders' in request) {
    // validateCreateOrdersRequest(request.orders); TODO: add createOrders validator

    response.body = await rippledex.createOrders(
      request.orders,
      request.waitUntilIncludedInBlock
    );

    response.status = StatusCodes.OK;

    return response;
  }

  throw new HttpException(
    StatusCodes.BAD_REQUEST,
    `No order(s) was/were informed.`
  );
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
  request: RippleCancelOrdersRequest
): Promise<ResponseWrapper<RippleCancelOrdersResponse>> {
  const response = new ResponseWrapper<RippleCancelOrdersResponse>();

  if ('order' in request) {
    // validateCancelOrderRequest(request.order); TODO: add createOrder validator

    response.body = await rippledex.cancelOrders(
      [request.order],
      request.waitUntilIncludedInBlock
    );

    response.status = StatusCodes.OK;

    return response;
  }

  if ('orders' in request) {
    // validateCancelOrdersRequest(request.orders); TODO: add createOrders validator

    response.body = await rippledex.cancelOrders(
      request.orders,
      request.waitUntilIncludedInBlock
    );

    response.status = StatusCodes.OK;

    return response;
  }

  throw new HttpException(
    StatusCodes.BAD_REQUEST,
    `No order(s) was/were informed.`
  );
}

/**
 * Get open orders of a token pair
 *
 * @param _ripple
 * @param rippledex
 * @param request
 */
export async function getOpenOrders(
  _ripple: Rippleish,
  rippledex: RippleDEXish,
  request: RippleGetOpenOrdersRequest
): Promise<ResponseWrapper<RippleGetOpenOrdersResponse>> {
  const response = new ResponseWrapper<RippleGetOpenOrdersResponse>();

  if ('order' in request) {
    // validateOpenOrderRequest(request.order); TODO: add createOrder validator

    response.body = await rippledex.getOpenOrders({ market: request.order });

    response.status = StatusCodes.OK;

    return response;
  }

  if ('orders' in request) {
    // validateOpenOrdersRequest(request.orders); TODO: add createOrders validator

    response.body = await rippledex.getOpenOrders({ markets: request.orders });

    response.status = StatusCodes.OK;

    return response;
  }

  throw new HttpException(
    StatusCodes.BAD_REQUEST,
    `No order(s) was/were informed.`
  );
}
