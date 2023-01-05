import { NextFunction, Request, Response, Router } from 'express';
import { ParamsDictionary } from 'express-serve-static-core';
import { XRPL } from './xrpl';
import { verifyXRPLIsAvailable } from './xrpl-middlewares';
import { asyncHandler } from '../../services/error-handler';
import { balances, poll } from './xrpl.controllers';
import {
  XRPLBalanceRequest,
  XRPLBalanceResponse,
  XRPLPollRequest,
  XRPLPollResponse,
} from './xrpl.requests';
import {
  validateXRPLBalanceRequest,
  validateXRPLPollRequest,
} from './xrpl.validators';

export namespace XRPLRoutes {
  export const router = Router();

  export const getXRPL = async (request: Request) => {
    const xrpl = await XRPL.getInstance(request.body.network);
    await xrpl.init();

    return xrpl;
  };

  router.use(asyncHandler(verifyXRPLIsAvailable));

  router.get(
    '/',
    asyncHandler(async (request: Request, response: Response) => {
      const xrpl = await getXRPL(request);

      const rpcUrl = xrpl.rpcUrl;

      response.status(200).json({
        network: xrpl.network,
        rpcUrl: rpcUrl,
        connection: true,
        timestamp: Date.now(),
      });
    })
  );

  router.get(
    '/balances',
    asyncHandler(
      async (
        request: Request<ParamsDictionary, unknown, XRPLBalanceRequest>,
        response: Response<XRPLBalanceResponse | string>,
        _next: NextFunction
      ) => {
        const xrpl = await getXRPL(request);

        validateXRPLBalanceRequest(request.body);
        response.status(200).json(await balances(xrpl, request.body));
      }
    )
  );

  // TODO: change this to GET
  router.get(
    '/poll',
    asyncHandler(
      async (
        request: Request<ParamsDictionary, unknown, XRPLPollRequest>,
        response: Response<XRPLPollResponse>
      ) => {
        const xrpl = await getXRPL(request);

        validateXRPLPollRequest(request.body);
        response.status(200).json(await poll(xrpl, request.body));
      }
    )
  );
}
