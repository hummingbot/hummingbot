import { StatusCodes } from 'http-status-codes';
import { XRPLish } from '../../chains/xrpl/xrpl';
import { ResponseWrapper } from '../../services/common-interfaces';
import { HttpException } from '../../services/error-handler';
import { XRPLDEXish } from './xrpldex';
import {
  XRPLCancelOrdersRequest,
  XRPLCancelOrdersResponse,
  XRPLCreateOrdersRequest,
  XRPLCreateOrdersResponse,
  XRPLGetMarketsRequest,
  XRPLGetMarketsResponse,
  XRPLGetOpenOrdersRequest,
  XRPLGetOpenOrdersResponse,
  XRPLGetOrderBooksRequest,
  XRPLGetOrderBooksResponse,
  XRPLGetTickersRequest,
  XRPLGetTickersResponse,
  XRPLGetOrdersRequest,
  XRPLGetOrdersResponse,
} from './xrpldex.requests';

import {
  validateGetMarketRequest,
  validateGetMarketsRequest,
  validateGetTickerRequest,
  validateGetTickersRequest,
  validateGetOrderBookRequest,
  validateGetOrderBooksRequest,
} from './xrpldex.validators';

import { MarketNotFoundError } from './xrpldex.types';

/**
 * Get the mid price of a token pair
 *
 * @param _xrpl
 * @param xrpldex
 * @param request
 */
export async function getMarkets(
  _xrpl: XRPLish,
  xrpldex: XRPLDEXish,
  request: XRPLGetMarketsRequest
): Promise<ResponseWrapper<XRPLGetMarketsResponse>> {
  const response = new ResponseWrapper<XRPLGetMarketsResponse>();

  if ('name' in request) {
    validateGetMarketRequest(request);

    try {
      response.body = await xrpldex.getMarket(request.name);
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
      response.body = await xrpldex.getMarkets(request.names);

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
 * @param _xrpl
 * @param xrpldex
 * @param request
 */
export async function getTickers(
  _xrpl: XRPLish,
  xrpldex: XRPLDEXish,
  request: XRPLGetTickersRequest
): Promise<ResponseWrapper<XRPLGetTickersResponse>> {
  const response = new ResponseWrapper<XRPLGetTickersResponse>();

  if ('marketName' in request) {
    validateGetTickerRequest(request);

    try {
      response.body = await xrpldex.getTicker(request.marketName);
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
      response.body = await xrpldex.getTickers(request.marketNames);

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
 * @param _xrpl
 * @param xrpldex
 * @param request
 */
export async function getOrderBooks(
  _xrpl: XRPLish,
  xrpldex: XRPLDEXish,
  request: XRPLGetOrderBooksRequest
): Promise<ResponseWrapper<XRPLGetOrderBooksResponse>> {
  const response = new ResponseWrapper<XRPLGetOrderBooksResponse>();

  if ('marketName' in request) {
    validateGetOrderBookRequest(request);

    try {
      response.body = await xrpldex.getOrderBook(
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
      response.body = await xrpldex.getOrderBooks(
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
 * @param _xrpl
 * @param xrpldex
 * @param request
 */
export async function getOrders(
  _xrpl: XRPLish,
  xrpldex: XRPLDEXish,
  request: XRPLGetOrdersRequest
): Promise<ResponseWrapper<XRPLGetOrdersResponse>> {
  const response = new ResponseWrapper<any>();

  response.body = await xrpldex.getOrders(request.orders);

  response.status = StatusCodes.OK;

  return response;
}

/**
 * Create an order on order book
 *
 * @param _xrpl
 * @param xrpldex
 * @param request
 */
export async function createOrders(
  _xrpl: XRPLish,
  xrpldex: XRPLDEXish,
  request: XRPLCreateOrdersRequest
): Promise<ResponseWrapper<XRPLCreateOrdersResponse>> {
  const response = new ResponseWrapper<XRPLCreateOrdersResponse>();

  if ('order' in request) {
    // validateCreateOrderRequest(request.order); TODO: add createOrder validator

    response.body = await xrpldex.createOrders(
      [request.order],
      request.waitUntilIncludedInBlock
    );

    response.status = StatusCodes.OK;

    return response;
  }

  if ('orders' in request) {
    // validateCreateOrdersRequest(request.orders); TODO: add createOrders validator

    response.body = await xrpldex.createOrders(
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
 * @param _xrpl
 * @param xrpldex
 * @param request
 */
export async function cancelOrders(
  _xrpl: XRPLish,
  xrpldex: XRPLDEXish,
  request: XRPLCancelOrdersRequest
): Promise<ResponseWrapper<XRPLCancelOrdersResponse>> {
  const response = new ResponseWrapper<XRPLCancelOrdersResponse>();

  if ('order' in request) {
    // validateCancelOrderRequest(request.order); TODO: add createOrder validator

    response.body = await xrpldex.cancelOrders(
      [request.order],
      request.waitUntilIncludedInBlock
    );

    response.status = StatusCodes.OK;

    return response;
  }

  if ('orders' in request) {
    // validateCancelOrdersRequest(request.orders); TODO: add createOrders validator

    response.body = await xrpldex.cancelOrders(
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
 * @param _xrpl
 * @param xrpldex
 * @param request
 */
export async function getOpenOrders(
  _xrpl: XRPLish,
  xrpldex: XRPLDEXish,
  request: XRPLGetOpenOrdersRequest
): Promise<ResponseWrapper<XRPLGetOpenOrdersResponse>> {
  const response = new ResponseWrapper<XRPLGetOpenOrdersResponse>();

  if ('order' in request) {
    // validateOpenOrderRequest(request.order); TODO: add createOrder validator

    response.body = await xrpldex.getOpenOrders({ market: request.order });

    response.status = StatusCodes.OK;

    return response;
  }

  if ('orders' in request) {
    // validateOpenOrdersRequest(request.orders); TODO: add createOrders validator

    response.body = await xrpldex.getOpenOrders({ markets: request.orders });

    response.status = StatusCodes.OK;

    return response;
  }

  throw new HttpException(
    StatusCodes.BAD_REQUEST,
    `No order(s) was/were informed.`
  );
}
