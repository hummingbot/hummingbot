import { Router, Request, Response } from 'express';
import { asyncHandler } from '../services/error-handler';
import {
  ClobDeleteOpenOrdersRequest,
  ClobDeleteOpenOrdersResponse,
  ClobDeleteOrdersRequest,
  ClobGetFilledOrdersRequest,
  ClobGetFilledOrdersResponse,
  ClobGetOpenOrdersRequest,
  ClobGetOpenOrdersResponse,
  ClobGetOrdersRequest,
  ClobGetMarketsRequest,
  ClobGetMarketsResponse,
  ClobGetOrderBooksRequest,
  ClobGetOrderBooksResponse,
  ClobOrdersResponse,
  ClobPostOrdersRequest,
  ClobGetTickersResponse,
  ClobGetTickersRequest,
} from './clob.requests';
import {
  deleteOrders,
  getFilledOrders,
  getOrders,
  getMarkets,
  getOrderBooks,
  postOrders,
  getTickers,
  getOpenOrders,
  deleteOpenOrders,
} from './clob.controllers';

export namespace ClobRoutes {
  export const router = Router();

  /**
   *
   */
  router.get(
    '/markets',
    asyncHandler(
      async (
        request: Request<unknown, unknown, ClobGetMarketsRequest>,
        response: Response<ClobGetMarketsResponse, any>
      ) => {
        response.status(200).json(await getMarkets(request.body));
      }
    )
  );

  /**
   * Returns the last traded prices.
   */
  router.get(
    '/tickers',
    asyncHandler(
      async (
        request: Request<unknown, unknown, ClobGetTickersRequest>,
        response: Response<ClobGetTickersResponse, any>
      ) => {
        response.status(200).json(await getTickers(request.body));
      }
    )
  );

  /**
   *
   */
  router.get(
    '/orderBooks',
    asyncHandler(
      async (
        request: Request<unknown, unknown, ClobGetOrderBooksRequest>,
        response: Response<ClobGetOrderBooksResponse, any>
      ) => {
        // TODO: 404 if requested market does not exist
        response.status(200).json(await getOrderBooks(request.body));
      }
    )
  );

  /**
   *
   */
  router.get(
    '/orders',
    asyncHandler(
      async (
        request: Request<unknown, unknown, ClobGetOrdersRequest>,
        response: Response<ClobOrdersResponse, any>
      ) => {
        response.status(200).json(await getOrders(request.body));
      }
    )
  );

  /**
   *
   */
  router.post(
    '/orders',
    asyncHandler(
      async (
        request: Request<unknown, unknown, ClobPostOrdersRequest>,
        response: Response<ClobOrdersResponse, any>
      ) => {
        response.status(200).json(await postOrders(request.body));
      }
    )
  );

  /**
   *
   */
  router.delete(
    '/orders',
    asyncHandler(
      async (
        request: Request<unknown, unknown, ClobDeleteOrdersRequest>,
        response: Response<ClobOrdersResponse, any>
      ) => {
        response.status(200).json(await deleteOrders(request.body));
      }
    )
  );

  /**
   *
   */
  router.get(
    '/openOrders',
    asyncHandler(
      async (
        request: Request<unknown, unknown, ClobGetOpenOrdersRequest>,
        response: Response<ClobGetOpenOrdersResponse, any>
      ) => {
        response.status(200).json(await getOpenOrders(request.body));
      }
    )
  );

  /**
   *
   */
  router.delete(
    '/openOrders',
    asyncHandler(
      async (
        request: Request<unknown, unknown, ClobDeleteOpenOrdersRequest>,
        response: Response<ClobDeleteOpenOrdersResponse, any>
      ) => {
        response.status(200).json(await deleteOpenOrders(request.body));
      }
    )
  );

  /**
   *
   */
  router.get(
    '/filledOrders',
    asyncHandler(
      async (
        request: Request<unknown, unknown, ClobGetFilledOrdersRequest>,
        response: Response<ClobGetFilledOrdersResponse, any>
      ) => {
        response.status(200).json(await getFilledOrders(request.body));
      }
    )
  );
}
