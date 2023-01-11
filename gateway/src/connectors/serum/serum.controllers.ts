import { StatusCodes } from 'http-status-codes';
import { Solanaish } from '../../chains/solana/solana';
import { ResponseWrapper } from '../../services/common-interfaces';
import { HttpException } from '../../services/error-handler';
import './extensions/json';
import { Serumish } from './serum';
import { convert, convertToJsonIfNeeded, Types } from './serum.convertors';
import {
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
  SerumPostSettleFundsRequest,
  SerumPostSettleFundsResponse,
} from './serum.requests';
import {
  Fund,
  IMap,
  Market,
  MarketNotFoundError,
  Order,
  OrderBook,
  OrderNotFoundError,
  Ticker,
} from './serum.types';
import {
  validateCancelAllOrdersRequest,
  validateCancelOrderRequest,
  validateCancelOrdersRequest,
  validateCreateOrderRequest,
  validateCreateOrdersRequest,
  validateGetAllOrdersRequest,
  validateGetFilledOrderRequest,
  validateGetFilledOrdersRequest,
  validateGetMarketRequest,
  validateGetMarketsRequest,
  validateGetOpenOrderRequest,
  validateGetOpenOrdersRequest,
  validateGetOrderBookRequest,
  validateGetOrderBooksRequest,
  validateGetOrderRequest,
  validateGetOrdersRequest,
  validateGetTickerRequest,
  validateGetTickersRequest,
  validateSettleAllFundsRequest,
  validateSettleFundsRequest,
  validateSettleFundsSeveralRequest,
} from './serum.validators';

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
    validateGetMarketRequest(request);

    try {
      response.body = convertToJsonIfNeeded(
        convert<Market, SerumGetMarketsResponse>(
          await serum.getMarket(request.name),
          Types.GetMarketsResponse
        )
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

  if ('names' in request) {
    validateGetMarketsRequest(request);

    try {
      response.body = convertToJsonIfNeeded(
        convert<IMap<string, Market>, SerumGetMarketsResponse>(
          await serum.getMarkets(request.names),
          Types.GetMarketsResponse
        )
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

  response.body = convertToJsonIfNeeded(
    convert<IMap<string, Market>, SerumGetMarketsResponse>(
      await serum.getAllMarkets(),
      Types.GetMarketsResponse
    )
  );

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
    validateGetOrderBookRequest(request);

    try {
      response.body = convertToJsonIfNeeded(
        convert<OrderBook, SerumGetOrderBooksResponse>(
          await serum.getOrderBook(request.marketName),
          Types.GetOrderBooksResponse
        )
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
      response.body = convertToJsonIfNeeded(
        convert<IMap<string, OrderBook>, SerumGetOrderBooksResponse>(
          await serum.getOrderBooks(request.marketNames),
          Types.GetOrderBooksResponse
        )
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

  response.body = convertToJsonIfNeeded(
    convert<IMap<string, OrderBook>, SerumGetOrderBooksResponse>(
      await serum.getAllOrderBooks(),
      Types.GetOrderBooksResponse
    )
  );

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
    validateGetTickerRequest(request);

    try {
      response.body = convertToJsonIfNeeded(
        convert<Ticker, SerumGetTickersResponse>(
          await serum.getTicker(request.marketName),
          Types.GetTickersResponse
        )
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
    validateGetTickersRequest(request);

    try {
      response.body = convertToJsonIfNeeded(
        convert<IMap<string, Ticker>, SerumGetTickersResponse>(
          await serum.getTickers(request.marketNames),
          Types.GetTickersResponse
        )
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

  response.body = convertToJsonIfNeeded(
    convert<IMap<string, Ticker>, SerumGetTickersResponse>(
      await serum.getAllTickers(),
      Types.GetTickersResponse
    )
  );

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
    validateGetOrderRequest(request.order);

    try {
      response.body = convertToJsonIfNeeded(
        convert<Order, SerumGetOrdersResponse>(
          await serum.getOrder(request.order),
          Types.GetOrdersResponse
        )
      );

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
    validateGetOrdersRequest(request.orders);

    try {
      const orders = await serum.getOrders(request.orders);

      if (!orders.size) throw new OrderNotFoundError('No orders found.');

      response.body = convertToJsonIfNeeded(
        convert<IMap<string, Order>, SerumGetOrdersResponse>(
          orders,
          Types.GetOrdersResponse
        )
      );

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

  validateGetAllOrdersRequest(request);

  response.body = convertToJsonIfNeeded(
    convert<IMap<string, IMap<string, Order>>, SerumGetOrdersResponse>(
      await serum.getAllOrders(request.ownerAddress),
      Types.GetFilledOrdersResponse
    )
  );

  response.status = StatusCodes.OK;

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
  request: SerumCreateOrdersRequest
): Promise<ResponseWrapper<SerumCreateOrdersResponse>> {
  const response = new ResponseWrapper<SerumCreateOrdersResponse>();

  if ('order' in request) {
    validateCreateOrderRequest(request.order);

    response.body = convertToJsonIfNeeded(
      convert<Order, SerumCreateOrdersResponse>(
        await serum.createOrder(request.order),
        Types.CreateOrdersResponse
      )
    );

    response.status = StatusCodes.OK;

    return response;
  }

  if ('orders' in request) {
    validateCreateOrdersRequest(request.orders);

    response.body = convertToJsonIfNeeded(
      convert<IMap<string, Order>, SerumCreateOrdersResponse>(
        await serum.createOrders(request.orders),
        Types.CreateOrdersResponse
      )
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
    validateCancelOrderRequest(request.order);

    response.body = convertToJsonIfNeeded(
      convert<Order, SerumCancelOrdersResponse>(
        await serum.cancelOrder(request.order),
        Types.CancelOrdersResponse
      )
    );

    response.status = StatusCodes.OK;

    return response;
  }

  if ('orders' in request) {
    validateCancelOrdersRequest(request.orders);

    response.body = convertToJsonIfNeeded(
      convert<IMap<string, Order>, SerumCancelOrdersResponse>(
        await serum.cancelOrders(request.orders),
        Types.CancelOrdersResponse
      )
    );

    response.status = StatusCodes.OK;

    return response;
  }

  validateCancelAllOrdersRequest(request);

  response.body = convertToJsonIfNeeded(
    convert<IMap<string, Order>, SerumCancelOrdersResponse>(
      await serum.cancelAllOrders(request.ownerAddress),
      Types.CancelOrdersResponse
    )
  );

  response.status = StatusCodes.OK;

  return response;
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
    validateGetOpenOrderRequest(request.order);

    try {
      response.body = convertToJsonIfNeeded(
        convert<Order, SerumGetOpenOrdersResponse>(
          await serum.getOpenOrder(request.order),
          Types.GetOpenOrdersResponse
        )
      );

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
    validateGetOpenOrdersRequest(request.orders);

    try {
      const orders = await serum.getOpenOrders(request.orders);

      if (!orders.size) throw new OrderNotFoundError('No open orders found.');

      response.body = convertToJsonIfNeeded(
        convert<IMap<string, Order>, SerumGetOrdersResponse>(
          orders,
          Types.GetOrdersResponse
        )
      );

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

  validateGetAllOrdersRequest(request);

  response.body = convertToJsonIfNeeded(
    convert<IMap<string, IMap<string, Order>>, SerumGetOpenOrdersResponse>(
      await serum.getAllOpenOrders(request.ownerAddress),
      Types.GetOpenOrdersResponse
    )
  );

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
    validateGetFilledOrderRequest(request.order);

    try {
      response.body = convertToJsonIfNeeded(
        convert<Order, SerumGetFilledOrdersResponse>(
          await serum.getFilledOrder(request.order),
          Types.GetFilledOrdersResponse
        )
      );

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
    validateGetFilledOrdersRequest(request.orders);

    try {
      response.body = convertToJsonIfNeeded(
        convert<IMap<string, Order>, SerumGetFilledOrdersResponse>(
          await serum.getFilledOrders(request.orders),
          Types.GetFilledOrdersResponse
        )
      );

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

  validateGetAllOrdersRequest(request);

  response.body = convertToJsonIfNeeded(
    convert<IMap<string, IMap<string, Order>>, SerumGetFilledOrdersResponse>(
      await serum.getAllFilledOrders(),
      Types.GetFilledOrdersResponse
    )
  );

  response.status = StatusCodes.OK;

  return response;
}

/**
 * Settle funds for one or more markets.
 *
 * @param _solana
 * @param serum
 * @param request
 */
export async function settleFunds(
  _solana: Solanaish,
  serum: Serumish,
  request: SerumPostSettleFundsRequest
): Promise<ResponseWrapper<SerumPostSettleFundsResponse>> {
  const response = new ResponseWrapper<SerumPostSettleFundsResponse>();

  if ('marketName' in request) {
    validateSettleFundsRequest(request);

    try {
      response.body = convertToJsonIfNeeded(
        convert<Fund[], SerumPostSettleFundsResponse>(
          await serum.settleFundsForMarket(
            request.marketName,
            request.ownerAddress
          ),
          Types.PostSettleFundsResponse
        )
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
    validateSettleFundsSeveralRequest(request);

    try {
      response.body = convertToJsonIfNeeded(
        convert<IMap<string, Fund[]>, SerumPostSettleFundsResponse>(
          await serum.settleFundsForMarkets(
            request.marketNames,
            request.ownerAddress
          ),
          Types.PostSettleFundsResponse
        )
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

  validateSettleAllFundsRequest(request);

  response.body = convertToJsonIfNeeded(
    convert<IMap<string, Fund[]>, SerumPostSettleFundsResponse>(
      await serum.settleAllFunds(request.ownerAddress),
      Types.PostSettleFundsResponse
    )
  );

  response.status = StatusCodes.OK;

  return response;
}
