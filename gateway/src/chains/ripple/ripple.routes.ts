import { NextFunction, Request, Response, Router } from 'express';
import { ParamsDictionary } from 'express-serve-static-core';
import { Ripple } from './ripple';
import { verifyRippleIsAvailable } from './ripple-middlewares';
import { asyncHandler } from '../../services/error-handler';
import { balances, poll } from './ripple.controllers';
import {
  RippleBalanceRequest,
  RippleBalanceResponse,
  RipplePollRequest,
  RipplePollResponse,
} from './ripple.requests';
import {
  validateRippleBalanceRequest,
  validateRipplePollRequest,
} from './ripple.validators';

export namespace RippleRoutes {
  export const router = Router();

  export const getRipple = async (request: Request) => {
    const solana = await Ripple.getInstance(request.body.network);
    await solana.init();

    return solana;
  };

  router.use(asyncHandler(verifyRippleIsAvailable));

  router.get(
    '/',
    asyncHandler(async (request: Request, response: Response) => {
      const ripple = await getRipple(request);

      const rpcUrl = ripple.rpcUrl;

      response.status(200).json({
        network: ripple.network,
        rpcUrl: rpcUrl,
        connection: true,
        timestamp: Date.now(),
      });
    })
  );

  // Get all token accounts and balances + solana balance
  router.get(
    '/balances',
    asyncHandler(
      async (
        request: Request<ParamsDictionary, unknown, RippleBalanceRequest>,
        response: Response<RippleBalanceResponse | string>,
        _next: NextFunction
      ) => {
        const ripple = await getRipple(request);

        validateRippleBalanceRequest(request.body);
        response.status(200).json(await balances(ripple, request.body));
      }
    )
  );

  router.post(
    '/poll',
    asyncHandler(
      async (
        request: Request<ParamsDictionary, unknown, RipplePollRequest>,
        response: Response<RipplePollResponse>
      ) => {
        const ripple = await getRipple(request);

        validateRipplePollRequest(request.body);
        response.status(200).json(await poll(ripple, request.body));
      }
    )
  );
}
