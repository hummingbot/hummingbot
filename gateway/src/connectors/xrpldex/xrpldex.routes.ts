import { Request, Response, Router } from 'express';
import { StatusCodes } from 'http-status-codes';
import { XRPL } from '../../chains/xrpl/xrpl';
import { verifyXRPLIsAvailable } from '../../chains/xrpl/xrpl-middlewares';
import { validateXRPLAddress } from '../../chains/xrpl/xrpl.validators';
import { asyncHandler } from '../../services/error-handler';
import { XRPLDEX } from './xrpldex';
import { verifyXRPLDEXIsAvailable } from './xrpldex.middlewares';
import {
  cancelOrders,
  createOrders,
  // getFilledOrders,
  getMarkets,
  getOpenOrders,
  getOrderBooks,
  getOrders,
  getTickers,
} from './xrpldex.controllers';
import {
  XRPLGetMarketsRequest,
  XRPLGetMarketsResponse,
  XRPLGetOrderBooksRequest,
  XRPLGetOrderBooksResponse,
  XRPLGetTickersRequest,
  XRPLGetTickersResponse,
  XRPLCreateOrdersRequest,
  XRPLCreateOrdersResponse,
  XRPLCancelOrdersRequest,
  XRPLCancelOrdersResponse,
  XRPLGetOpenOrdersRequest,
  XRPLGetOpenOrdersResponse,
  XRPLGetOrdersRequest,
  XRPLGetOrdersResponse,
} from './xrpldex.requests';

export namespace XRPLDEXRoutes {
  export const router = Router();

  export const getXRPL = async (request: Request) =>
    await XRPL.getInstance(request.body.network);

  export const getXRPLDEX = async (request: Request) =>
    await XRPLDEX.getInstance(request.body.chain, request.body.network);

  router.use(
    asyncHandler(verifyXRPLIsAvailable),
    asyncHandler(verifyXRPLDEXIsAvailable)
  );

  router.get(
    '/',
    asyncHandler(
      async (request: Request<any>, response: Response<any, any>) => {
        const xrplDEX = await getXRPLDEX(request);

        response.status(StatusCodes.OK).json({
          chain: xrplDEX.chain,
          network: xrplDEX.network,
          connector: xrplDEX.connector,
          connection: xrplDEX.ready(),
          timestamp: Date.now(),
        });
      }
    )
  );

  router.get(
    '/markets',
    asyncHandler(
      async (
        request: Request<any, any, XRPLGetMarketsRequest>,
        response: Response<XRPLGetMarketsResponse, any>
      ) => {
        const xrpl = await getXRPL(request);
        const xrplDEX = await getXRPLDEX(request);

        const result = await getMarkets(xrpl, xrplDEX, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.get(
    '/tickers',
    asyncHandler(
      async (
        request: Request<any, any, XRPLGetTickersRequest>,
        response: Response<XRPLGetTickersResponse, any>
      ) => {
        const xrpl = await getXRPL(request);
        const xrplDEX = await getXRPLDEX(request);

        const result = await getTickers(xrpl, xrplDEX, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.get(
    '/orderBooks',
    asyncHandler(
      async (
        request: Request<any, any, XRPLGetOrderBooksRequest>,
        response: Response<XRPLGetOrderBooksResponse, any>
      ) => {
        const xrpl = await getXRPL(request);
        const xrplDEX = await getXRPLDEX(request);

        const result = await getOrderBooks(xrpl, xrplDEX, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.get(
    '/orders',
    asyncHandler(
      async (
        request: Request<any, any, XRPLGetOrdersRequest>,
        response: Response<XRPLGetOrdersResponse, any>
      ) => {
        const xrpl = await getXRPL(request);
        const xrplDEX = await getXRPLDEX(request);

        validateXRPLAddress(request.body);

        const result = await getOrders(xrpl, xrplDEX, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.post(
    '/orders',
    asyncHandler(
      async (
        request: Request<any, any, XRPLCreateOrdersRequest>,
        response: Response<XRPLCreateOrdersResponse, any>
      ) => {
        const xrpl = await getXRPL(request);
        const xrplDEX = await getXRPLDEX(request);

        validateXRPLAddress(request.body);

        const result = await createOrders(xrpl, xrplDEX, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.delete(
    '/orders',
    asyncHandler(
      async (
        request: Request<any, any, XRPLCancelOrdersRequest>,
        response: Response<XRPLCancelOrdersResponse, any>
      ) => {
        const xrpl = await getXRPL(request);
        const xrplDEX = await getXRPLDEX(request);

        validateXRPLAddress(request.body);

        const result = await cancelOrders(xrpl, xrplDEX, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.get(
    '/orders/open',
    asyncHandler(
      async (
        request: Request<any, any, XRPLGetOpenOrdersRequest>,
        response: Response<XRPLGetOpenOrdersResponse, any>
      ) => {
        const xrpl = await getXRPL(request);
        const xrplDEX = await getXRPLDEX(request);

        validateXRPLAddress(request.body);

        const result = await getOpenOrders(xrpl, xrplDEX, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );
}
