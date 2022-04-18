import {StatusCodes} from 'http-status-codes';
import {Map as ImmutableMap} from 'immutable';
import {Solanaish} from '../../chains/solana/solana';
import {Serumish} from './serum';
import {
  SerumCancelOpenOrdersRequest,
  SerumCancelOpenOrdersResponse,
  SerumCancelOrdersRequest,
  SerumCancelOrdersResponse,
  SerumCreateOrdersRequest,
  SerumCreateOrdersResponse,
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
} from './serum.requests';
import {ResponseWrapper} from '../../services/common-interfaces';
import {HttpException} from '../../services/error-handler';
import {Market, MarketNotFoundError, Order, OrderBook, OrderNotFoundError, Ticker} from './serum.types';
import {convert, Types} from "./serum.convertors";

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
      response.body = convert<Market, SerumGetMarketsResponse>(await serum.getMarket(request.name), Types.GetMarketsResponse);

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
      response.body = convert<ImmutableMap<string, Market>, SerumGetMarketsResponse>(await serum.getMarkets(request.names), Types.GetMarketsResponse);

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

  response.body = convert<ImmutableMap<string, Market>, SerumGetMarketsResponse>(await serum.getAllMarkets(), Types.GetMarketsResponse);

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
    if (!request.marketName) {
      throw new HttpException(
        StatusCodes.BAD_REQUEST,
        `No market name was informed. If you want to get an order book, please inform the parameter "marketName".`
      );
    }

    try {
      response.body = convert<OrderBook, SerumGetOrderBooksResponse>(await serum.getOrderBook(request.marketName), Types.GetOrderBooksResponse);

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
      response.body = convert<ImmutableMap<string, OrderBook>, SerumGetOrderBooksResponse>(await serum.getOrderBooks(request.marketNames), Types.GetOrderBooksResponse);

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

  response.body = convert<ImmutableMap<string, OrderBook>, SerumGetOrderBooksResponse>(await serum.getAllOrderBooks(), Types.GetOrderBooksResponse);

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
    if (!request.marketName) {
      throw new HttpException(
        StatusCodes.BAD_REQUEST,
        `No market name was informed. If you want to get a ticker, please inform the parameter "marketName".`
      );
    }

    try {
      response.body = convert<Ticker, SerumGetTickersResponse>(await serum.getTicker(request.marketName), Types.GetTickersResponse);

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
      response.body = convert<ImmutableMap<string, Ticker>, SerumGetTickersResponse>(await serum.getTickers(request.marketNames), Types.GetTickersResponse);

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

  response.body = convert<ImmutableMap<string, Ticker>, SerumGetTickersResponse>(await serum.getAllTickers(), Types.GetTickersResponse);

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
      response.body = convert<Order, SerumGetOrdersResponse>(await serum.getOrder(request.order), Types.GetOrdersResponse);

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
      response.body = convert<ImmutableMap<string, Order>, SerumGetOrdersResponse>(await serum.getOrders(request.orders), Types.GetOrdersResponse);

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
    response.body = convert<Order, SerumCreateOrdersResponse>(await serum.createOrder(request.order), Types.CreateOrdersResponse);

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

    response.body = convert<ImmutableMap<string, Order>, SerumCreateOrdersResponse>(await serum.createOrders(request.orders), Types.CreateOrdersResponse);

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
    response.body = convert<Order, SerumCancelOrdersResponse>(await serum.cancelOrder(request.order), Types.CancelOrdersResponse);

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

    response.body = convert<ImmutableMap<string, Order>, SerumCancelOrdersResponse>(await serum.cancelOrders(request.orders), Types.CancelOrdersResponse);

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
      response.body = convert<Order, SerumGetOpenOrdersResponse>(await serum.getOpenOrder(request.order), Types.GetOpenOrdersResponse);

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
      response.body = convert<ImmutableMap<string, Order>, SerumGetOpenOrdersResponse>(await serum.getOpenOrders(request.orders), Types.GetOpenOrdersResponse);

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
    response.body = convert<Order, SerumCancelOpenOrdersResponse>(await serum.cancelOrder(request.order), Types.CancelOpenOrdersResponse);

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

    response.body = convert<ImmutableMap<string, Order>, SerumCancelOpenOrdersResponse>(await serum.cancelOrders(request.orders), Types.CancelOpenOrdersResponse);

    response.status = StatusCodes.OK;

    return response;
  }

  response.body = convert<ImmutableMap<string, Order>, SerumCancelOpenOrdersResponse>(await serum.cancelAllOpenOrders(request), Types.CancelOpenOrdersResponse);

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
      response.body = convert<Order, SerumGetFilledOrdersResponse>(await serum.getFilledOrder(request.order), Types.GetFilledOrdersResponse);

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
      response.body = convert<ImmutableMap<string, Order>, SerumGetFilledOrdersResponse>(await serum.getFilledOrders(request.orders), Types.GetFilledOrdersResponse);

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

  response.body = convert<ImmutableMap<string, Order>, SerumGetFilledOrdersResponse>(await serum.getAllFilledOrders(), Types.GetFilledOrdersResponse);

  response.status = StatusCodes.OK;

  return response;
}
