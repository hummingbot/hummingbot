/* eslint-disable no-inner-declarations */
/* eslint-disable @typescript-eslint/ban-types */
import { Router, Request, Response } from 'express';
import { asyncHandler } from '../services/error-handler';
import {
  ClobDeleteOpenOrdersRequest,
  ClobDeleteOpenOrdersResponse,
  ClobDeleteOrderRequest,
  ClobGetFillsRequest,
  ClobGetFillsResponse,
  ClobGetOpenOrdersRequest,
  ClobGetOpenOrdersResponse,
  ClobGetOrderRequest,
  ClobMarketsRequest,
  ClobMarketsResponse,
  ClobOrderbookRequest,
  ClobOrderbookResponse,
  ClobOrderResponse,
  ClobPostOrderRequest,
  ClobTickerResponse,
} from './clob.requests';
import {
  deleteOrders,
  fills,
  getOrders,
  markets,
  orderbook,
  postOrder,
} from './clob.controllers';

export namespace ClobRoutes {
  export const router = Router();

  router.get(
    '/markets',
    asyncHandler(
      async (
        req: Request<unknown, unknown, ClobMarketsRequest>,
        res: Response<ClobMarketsResponse, any>
      ) => {
        res.status(200).json(await markets(req.body));
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
        req: Request<unknown, unknown, ClobMarketsRequest>,
        res: Response<ClobTickerResponse, any>
      ) => {
        res.status(200).json(await markets(req.body));
      }
    )
  );

  router.get(
    '/orderbooks',
    asyncHandler(
      async (
        req: Request<unknown, unknown, ClobOrderbookRequest>,
        res: Response<ClobOrderbookResponse, any>
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
        req: Request<unknown, unknown, ClobGetOrderRequest>,
        res: Response<ClobOrderResponse, any>
      ) => {
        res.status(200).json(await getOrders(req.body));
      }
    )
  );

  router.post(
    '/order',
    asyncHandler(
      async (
        req: Request<unknown, unknown, ClobPostOrderRequest>,
        res: Response<ClobOrderResponse, any>
      ) => {
        res.status(200).json(await postOrder(req.body));
      }
    )
  );

  router.delete(
    '/order',
    asyncHandler(
      async (
        req: Request<unknown, unknown, ClobDeleteOrderRequest>,
        res: Response<ClobOrderResponse, any>
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
        req: Request<unknown, unknown, ClobGetFillsRequest>,
        res: Response<ClobGetFillsResponse, any>
      ) => {
        res.status(200).json(await fills(req.body));
      }
    )
  );
}
