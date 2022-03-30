/* eslint-disable no-inner-declarations */
/* eslint-disable @typescript-eslint/ban-types */
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
  ClobGetOrderbooksRequest,
  ClobGetOrderbooksResponse,
  ClobOrdersResponse,
  ClobPostOrdersRequest,
  ClobGetTickersResponse,
} from './clob.requests';
import {
  deleteOrders,
  fills,
  getOrders,
  getMarkets,
  orderbook,
  postOrders,
} from './clob.controllers';

export namespace ClobRoutes {
  export const router = Router();

  router.get(
    '/markets',
    asyncHandler(
      async (
        req: Request<unknown, unknown, ClobGetMarketsRequest>,
        res: Response<ClobGetMarketsResponse, any>
      ) => {
        res.status(200).json(await getMarkets(req.body));
      }
    )
  );

  /**
   * Returns the last traded prices.
   */
  router.get(
    '/ticker',
    asyncHandler(
      async (
        req: Request<unknown, unknown, ClobGetMarketsRequest>,
        res: Response<ClobGetTickersResponse, any>
      ) => {
        res.status(200).json(await getMarkets(req.body));
      }
    )
  );

  router.get(
    '/orderbooks',
    asyncHandler(
      async (
        req: Request<unknown, unknown, ClobGetOrderbooksRequest>,
        res: Response<ClobGetOrderbooksResponse, any>
      ) => {
        // TODO: 404 if requested market does not exist
        res.status(200).json(await orderbook(req.body));
      }
    )
  );

  router.get(
    '/order',
    asyncHandler(
      async (
        req: Request<unknown, unknown, ClobGetOrdersRequest>,
        res: Response<ClobOrdersResponse, any>
      ) => {
        res.status(200).json(await getOrders(req.body));
      }
    )
  );

  router.post(
    '/order',
    asyncHandler(
      async (
        req: Request<unknown, unknown, ClobPostOrdersRequest>,
        res: Response<ClobOrdersResponse, any>
      ) => {
        res.status(200).json(await postOrders(req.body));
      }
    )
  );

  router.delete(
    '/order',
    asyncHandler(
      async (
        req: Request<unknown, unknown, ClobDeleteOrdersRequest>,
        res: Response<ClobOrdersResponse, any>
      ) => {
        res.status(200).json(await deleteOrders(req.body));
      }
    )
  );

  router.get(
    '/openOrders',
    asyncHandler(
      async (
        req: Request<unknown, unknown, ClobGetOpenOrdersRequest>,
        res: Response<ClobGetOpenOrdersResponse, any>
      ) => {
        res.status(200).json(await getOrders(req.body));
      }
    )
  );

  router.delete(
    '/openOrders',
    asyncHandler(
      async (
        req: Request<unknown, unknown, ClobDeleteOpenOrdersRequest>,
        res: Response<ClobDeleteOpenOrdersResponse, any>
      ) => {
        res.status(200).json(await deleteOrders(req.body));
      }
    )
  );

  router.get(
    '/fills',
    asyncHandler(
      async (
        req: Request<unknown, unknown, ClobGetFilledOrdersRequest>,
        res: Response<ClobGetFilledOrdersResponse, any>
      ) => {
        res.status(200).json(await fills(req.body));
      }
    )
  );
}
