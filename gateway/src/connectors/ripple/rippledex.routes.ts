import { Request, Response, Router } from 'express';
import { StatusCodes } from 'http-status-codes';
import { Ripple } from '../../chains/ripple/ripple';
import { verifyRippleIsAvailable } from '../../chains/ripple/ripple-middlewares';
import { validateRippleAddress } from '../../chains/ripple/ripple.validators';
import { asyncHandler } from '../../services/error-handler';
import { RippleDEX } from './RippleDEX';
import { verifyRippleDEXIsAvailable } from './rippledex.middlewares';
import {
  cancelOrders,
  createOrders,
  // getFilledOrders,
  getMarkets,
  getOpenOrders,
  getOrderBooks,
  getOrders,
  getTickers,
} from './rippledex.controllers';
import {
  RippleGetMarketsRequest,
  RippleGetMarketsResponse,
  RippleGetOrderBooksRequest,
  RippleGetOrderBooksResponse,
  RippleGetTickersRequest,
  RippleGetTickersResponse,
} from './rippledex.requests';

export namespace RippleDEXRoutes {
  export const router = Router();

  export const getRipple = async (request: Request) =>
    await Ripple.getInstance(request.body.network);

  export const getRippleDEX = async (request: Request) =>
    await RippleDEX.getInstance(request.body.chain, request.body.network);

  router.use(
    asyncHandler(verifyRippleIsAvailable),
    asyncHandler(verifyRippleDEXIsAvailable)
  );

  // Sample request:
  // {
  //   "chain": "ripple",
  //   "network": "mainnet"
  // }
  router.get(
    '/',
    asyncHandler(
      async (request: Request<any>, response: Response<any, any>) => {
        const rippleDEX = await getRippleDEX(request);

        response.status(StatusCodes.OK).json({
          chain: rippleDEX.chain,
          network: rippleDEX.network,
          connector: rippleDEX.connector,
          connection: rippleDEX.ready(),
          timestamp: Date.now(),
        });
      }
    )
  );

  router.get(
    '/markets',
    asyncHandler(
      async (
        request: Request<any, any, RippleGetMarketsRequest>,
        response: Response<RippleGetMarketsResponse, any>
      ) => {
        const ripple = await getRipple(request);
        const rippleDEX = await getRippleDEX(request);

        const result = await getMarkets(ripple, rippleDEX, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  /**
   * Returns the last traded prices.
   */
  // Sample request:
  // {
  //   "chain": "ripple",
  //   "network": "mainnet",
  //   "base": {
  //       "currency": "USD",
  //       "issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq"
  //   },
  //   "quote": {
  //       "currency": "XRP"
  //   }
  // }
  router.get(
    '/tickers',
    asyncHandler(
      async (
        request: Request<any, any, RippleGetTickersRequest>,
        response: Response<RippleGetTickersResponse, any>
      ) => {
        const ripple = await getRipple(request);
        const rippledex = await getRippleDEX(request);

        const result = await getTickers(ripple, rippledex, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  // Sample request:
  // {
  //   "chain": "ripple",
  //   "network": "mainnet",
  //   "base": {
  //       "currency": "USD",
  //       "issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq"
  //   },
  //   "quote": {
  //       "currency": "XRP"
  //   },
  //   "limit": 5
  // }
  router.get(
    '/orderBooks',
    asyncHandler(
      async (
        request: Request<any, any, RippleGetOrderBooksRequest>,
        response: Response<RippleGetOrderBooksResponse, any>
      ) => {
        const ripple = await getRipple(request);
        const rippledex = await getRippleDEX(request);

        const result = await getOrderBooks(ripple, rippledex, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  // Sample requesT:
  // {
  //   "chain": "ripple",
  //   "network": "mainnet",
  //   "tx": "txhex"
  // }
  router.get(
    '/orders',
    asyncHandler(
      async (request: Request<any, any, any>, response: Response<any, any>) => {
        const ripple = await getRipple(request);
        const rippledex = await getRippleDEX(request);

        validateRippleAddress(request.body);

        const result = await getOrders(ripple, rippledex, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.post(
    '/orders',
    asyncHandler(
      async (request: Request<any, any, any>, response: Response<any, any>) => {
        const ripple = await getRipple(request);
        const rippledex = await getRippleDEX(request);

        validateRippleAddress(request.body);

        const result = await createOrders(ripple, rippledex, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.delete(
    '/orders',
    asyncHandler(
      async (request: Request<any, any, any>, response: Response<any, any>) => {
        const ripple = await getRipple(request);
        const rippledex = await getRippleDEX(request);

        validateRippleAddress(request.body);

        const result = await cancelOrders(ripple, rippledex, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.get(
    '/orders/open',
    asyncHandler(
      async (request: Request<any, any, any>, response: Response<any, any>) => {
        const ripple = await getRipple(request);
        const rippledex = await getRippleDEX(request);

        validateRippleAddress(request.body);

        const result = await getOpenOrders(ripple, rippledex, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );
}
