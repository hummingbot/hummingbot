import { StatusCodes } from 'http-status-codes';
import { Solanaish } from '../../chains/solana/solana';
import { Serumish } from './serum';
import {
  SerumCancelOpenOrdersRequest,
  SerumCancelOpenOrdersResponse,
  SerumCancelOrdersRequest,
  SerumCancelOrdersResponse,
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
  SerumCreateOrdersRequest,
  SerumCreateOrdersResponse,
} from './serum.requests';
import { ResponseWrapper } from '../../services/common-interfaces';
import { HttpException } from '../../services/error-handler';
import { MarketNotFoundError, OrderNotFoundError } from './serum.types';

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
    if (!request.name) {
      throw new HttpException(
        StatusCodes.BAD_REQUEST,
        `No market was informed. If you want to get a market, please inform the parameter "name".`
      );
    }

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
        // TODO Ask Mike! Should we throw an HttpException here? or would it be ok to throw the original exception?!!!
        throw exception;
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
    try {
      response.body = await serum.getOrderBook(request.marketName);

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
    if (!request.marketNames || !request.marketNames.length) {
      throw new HttpException(
        StatusCodes.BAD_REQUEST,
        `No market names were informed. If you want to get all order books, please do not inform the parameter "marketNames".`
      );
    }

    try {
      response.body = await serum.getOrderBooks(request.marketNames);

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

  response.body = await serum.getAllOrderBooks();

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
    try {
      response.body = await serum.getTicker(request.marketName);

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
    if (!request.marketNames || !request.marketNames.length) {
      throw new HttpException(
        StatusCodes.BAD_REQUEST,
        `No market names were informed. If you want to get all tickers, please do not inform the parameter "marketNames".`
      );
    }

    try {
      response.body = await serum.getTickers(request.marketNames);

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

  response.body = await serum.getAllTickers();

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
    try {
      response.body = await serum.getOrder(request.order);

      response.status = StatusCodes.OK;

      return response;
    } catch (exception) {
      if (exception instanceof OrderNotFoundError) {
        throw new HttpException(StatusCodes.NOT_FOUND, exception.message);
      } else {
        throw exception;
      }
    }
  }

  if ('orders' in request) {
    if (!request.orders || !request.orders.length) {
      throw new HttpException(
        StatusCodes.BAD_REQUEST,
        `No orders were informed.`
      );
    }

    try {
      response.body = await serum.getOrders(request.orders);

      response.status = StatusCodes.OK;

      return response;
    } catch (exception: any) {
      if (exception instanceof OrderNotFoundError) {
        throw new HttpException(StatusCodes.NOT_FOUND, exception.message);
      } else {
        throw exception;
      }
    }
  }

  throw new HttpException(
    StatusCodes.BAD_REQUEST,
    `No order(s) was/were informed.`
  );
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
  request: SerumCreateOrdersRequest
): Promise<ResponseWrapper<SerumCreateOrdersResponse>> {
  const response = new ResponseWrapper<SerumCreateOrdersResponse>();

  if ('order' in request) {
    response.body = await serum.createOrder(request.order);

    response.status = StatusCodes.OK;

    return response;
  }

  if ('orders' in request) {
    if (!request.orders || !request.orders.length) {
      throw new HttpException(
        StatusCodes.BAD_REQUEST,
        `No orders were informed.`
      );
    }

    response.body = await serum.createOrders(request.orders);

    response.status = StatusCodes.OK;

    return response;
  }

  throw new HttpException(
    StatusCodes.BAD_REQUEST,
    `No order(s) was/were informed.`
  );
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
  request: SerumCancelOrdersRequest
): Promise<ResponseWrapper<SerumCancelOrdersResponse>> {
  const response = new ResponseWrapper<SerumCancelOrdersResponse>();

  if ('order' in request) {
    response.body = await serum.cancelOrder(request.order);

    response.status = StatusCodes.OK;

    return response;
  }

  if ('orders' in request) {
    if (!request.orders || !request.orders.length) {
      throw new HttpException(
        StatusCodes.BAD_REQUEST,
        `No orders were informed.`
      );
    }

    response.body = await serum.cancelOrders(request.orders);

    response.status = StatusCodes.OK;

    return response;
  }

  throw new HttpException(
    StatusCodes.BAD_REQUEST,
    `No order(s) was/were informed.`
  );
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
  const response = new ResponseWrapper<SerumGetOpenOrdersResponse>();

  if ('order' in request) {
    try {
      response.body = await serum.getOpenOrder(request.order);

      response.status = StatusCodes.OK;

      return response;
    } catch (exception) {
      if (exception instanceof OrderNotFoundError) {
        throw new HttpException(StatusCodes.NOT_FOUND, exception.message);
      } else {
        throw exception;
      }
    }
  }

  if ('orders' in request) {
    if (!request.orders || !request.orders.length) {
      throw new HttpException(
        StatusCodes.BAD_REQUEST,
        `No orders were informed.`
      );
    }

    try {
      response.body = await serum.getOpenOrders(request.orders);

      response.status = StatusCodes.OK;

      return response;
    } catch (exception: any) {
      if (exception instanceof OrderNotFoundError) {
        throw new HttpException(StatusCodes.NOT_FOUND, exception.message);
      } else {
        throw exception;
      }
    }
  }

  throw new HttpException(
    StatusCodes.BAD_REQUEST,
    `No order(s) was/were informed.`
  );
}

/**
 * Cancel all open orders for each informed market.
 *
 * @param _solana
 * @param serum
 * @param request
 */
export async function cancelOpenOrders(
  _solana: Solanaish,
  serum: Serumish,
  request: SerumCancelOpenOrdersRequest
): Promise<ResponseWrapper<SerumCancelOpenOrdersResponse>> {
  const response = new ResponseWrapper<SerumCancelOpenOrdersResponse>();

  if ('order' in request) {
    response.body = await serum.cancelOrder(request.order);

    response.status = StatusCodes.OK;

    return response;
  }

  if ('orders' in request) {
    if (!request.orders || !request.orders.length) {
      throw new HttpException(
        StatusCodes.BAD_REQUEST,
        `No orders were informed.`
      );
    }

    response.body = await serum.cancelOrders(request.orders);

    response.status = StatusCodes.OK;

    return response;
  }

  response.body = await serum.cancelAllOpenOrders(request);

  response.status = StatusCodes.OK;

  return response;
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
  const response = new ResponseWrapper<SerumGetFilledOrdersResponse>();

  if ('order' in request) {
    try {
      response.body = await serum.getFilledOrder(request.order);

      response.status = StatusCodes.OK;

      return response;
    } catch (exception) {
      if (exception instanceof OrderNotFoundError) {
        throw new HttpException(StatusCodes.NOT_FOUND, exception.message);
      } else {
        throw exception;
      }
    }
  }

  if ('orders' in request) {
    if (!request.orders || !request.orders.length) {
      throw new HttpException(
        StatusCodes.BAD_REQUEST,
        `No orders were informed.`
      );
    }

    try {
      response.body = await serum.getFilledOrders(request.orders);

      response.status = StatusCodes.OK;

      return response;
    } catch (exception: any) {
      if (exception instanceof OrderNotFoundError) {
        throw new HttpException(StatusCodes.NOT_FOUND, exception.message);
      } else {
        throw exception;
      }
    }
  }

  response.body = await serum.getAllFilledOrders();

  response.status = StatusCodes.OK;

  return response;
}
